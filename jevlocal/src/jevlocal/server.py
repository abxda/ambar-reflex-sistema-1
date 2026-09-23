"""TypeSafe-compatible HTTP API: POST /v1/systemone, GET /v1/models, GET /health.

Request and response bodies follow https://docs.typesafe.ai/api, so the official
SDKs and any Jev client work by pointing their base URL here. One worker thread
owns the GPU; requests that arrive while it is busy are merged into its next batch.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .engine import ContextOverflow, Engine
from .prompts import RequestError, answers, plan_request

RELEASE_DATE = "2026-09-22"


class Job:
    __slots__ = ("plan", "done", "result", "error", "status")

    def __init__(self, plan):
        self.plan = plan
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.status = 200


class Worker(threading.Thread):
    def __init__(self, engine: Engine, served_name: str, max_jobs: int, max_readouts: int, max_queue: int):
        super().__init__(daemon=True, name="jevlocal-gpu")
        self.engine = engine
        self.served_name = served_name
        self.max_jobs = max_jobs
        self.max_readouts = max_readouts
        self.queue: queue.Queue[Job] = queue.Queue(max_queue)

    def submit(self, job: Job) -> None:
        self.queue.put_nowait(job)  # queue.Full -> 529 Overloaded

    def run(self) -> None:
        while True:
            jobs = [self.queue.get()]
            readouts = len(jobs[0].plan.readouts)
            while len(jobs) < self.max_jobs:
                try:
                    job = self.queue.get_nowait()
                except queue.Empty:
                    break
                jobs.append(job)
                readouts += len(job.plan.readouts)
                if readouts >= self.max_readouts:
                    break
            try:
                self._score(jobs)
            except ContextOverflow:
                if len(jobs) == 1:
                    self._fail(jobs[0], 422, "state and questions exceed the server context window")
                else:  # the merged batch did not fit; retry each request on its own
                    for job in jobs:
                        try:
                            self._score([job])
                        except ContextOverflow:
                            self._fail(job, 422, "state and questions exceed the server context window")
                        except Exception as error:  # noqa: BLE001
                            self._fail(job, 500, f"inference failed: {error}")
            except Exception as error:  # noqa: BLE001
                for job in jobs:
                    self._fail(job, 500, f"inference failed: {error}")

    def _score(self, jobs: list[Job]) -> None:
        self.engine.score([r for job in jobs for r in job.plan.readouts])
        for job in jobs:
            job.result = {
                "model": self.served_name,
                "answers": answers(job.plan),
                "usage": {
                    "input_tokens": sum(r.charged for r in job.plan.readouts),
                    "output_tokens": len(job.plan.questions),
                },
            }
            job.done.set()

    @staticmethod
    def _fail(job: Job, status: int, message: str) -> None:
        job.status, job.error = status, message
        job.done.set()


def make_handler(worker: Worker, config: dict):
    api_key = config.get("api_key")
    models_body = json.dumps({
        "models": [
            {"name": name, "description": f"Local System One model ({config['served_name']}, {config['gguf_name']})",
             "release_date": RELEASE_DATE}
            for name in (config["served_name"], "jev-latest")
        ]
    }).encode()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = f"jevlocal/{__version__}"

        def log_message(self, fmt, *args):  # quiet by default
            if config.get("access_log"):
                super().log_message(fmt, *args)

        def _send(self, status: int, body: bytes, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status: int, message: str) -> None:
            self._send(status, json.dumps({"detail": message}).encode())

        def _authorized(self) -> bool:
            if not api_key:
                return True
            header = self.headers.get("Authorization", "")
            if header == f"Bearer {api_key}":
                return True
            self._error(401, "missing or invalid API key")
            return False

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/health":
                body = {"status": "ok", "model": config["served_name"], "gguf": config["gguf_name"],
                        "queue": worker.queue.qsize(), **config["public"]}
                return self._send(200, json.dumps(body).encode())
            if not self._authorized():
                return
            if path == "/v1/models":
                return self._send(200, models_body)
            self._error(404, "not found")

        def do_POST(self):
            started = time.perf_counter()
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            path = self.path.split("?", 1)[0].rstrip("/")
            if path != "/v1/systemone":
                return self._error(404, "not found")
            if not self._authorized():
                return
            try:
                body = json.loads(raw)
                plan = plan_request(body, config["debias"], config["option_style"], config["profile"])
            except json.JSONDecodeError:
                return self._error(422, "body is not valid JSON")
            except RequestError as error:
                return self._error(422, str(error))
            job = Job(plan)
            try:
                worker.submit(job)
            except queue.Full:
                return self._error(529, "server overloaded, retry with backoff")
            job.done.wait()
            if job.error:
                return self._error(job.status, job.error)
            elapsed = (time.perf_counter() - started) * 1000
            self._send(200, json.dumps(job.result).encode(), {"X-Process-Time-Ms": f"{elapsed:.1f}"})

    return Handler


def serve(engine: Engine, *, host: str, port: int, served_name: str, gguf_name: str, debias: str,
          option_style: str, profile: str, api_key: str | None, max_jobs: int, max_readouts: int, max_queue: int,
          access_log: bool, public: dict) -> None:
    worker = Worker(engine, served_name, max_jobs, max_readouts, max_queue)
    worker.start()
    config = dict(served_name=served_name, gguf_name=gguf_name, debias=debias, option_style=option_style, profile=profile,
                  api_key=api_key, access_log=access_log, public=public)
    httpd = ThreadingHTTPServer((host, port), make_handler(worker, config))
    httpd.daemon_threads = True
    print(f"jevlocal {__version__} serving {served_name} on http://{host}:{port}/v1/systemone", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

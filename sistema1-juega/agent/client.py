"""Minimal System One client (stdlib only). Parses the exact response schema captured in
fixtures/systemone_6q.json and fails loudly on anything else."""

from __future__ import annotations

import http.client
import json
import os
import time
from dataclasses import dataclass
from urllib.parse import urlparse


class SchemaError(ValueError):
    pass


@dataclass
class Answer:
    type: str
    value: object              # choice key, noul probability, or score value
    probabilities: dict | None  # choice/score only
    confidence: float          # choice/score from the server; noul derived as |2p-1| (K=2 formula)


def parse_answers(resp: dict, expected: dict) -> dict[str, Answer]:
    if not isinstance(resp, dict) or not {"model", "answers", "usage"} <= resp.keys():
        raise SchemaError(f"response lacks model/answers/usage: {list(resp)[:5]}")
    out = {}
    for key, q in expected.items():
        a = resp["answers"].get(key)
        if not isinstance(a, dict) or a.get("type") != q["type"]:
            raise SchemaError(f"answer {key!r} missing or wrong type")
        if q["type"] == "noul":
            p = float(a["noul"])
            out[key] = Answer("noul", p, None, abs(2 * p - 1))
        elif q["type"] == "choice":
            probs = {k: float(v) for k, v in a["probabilities"].items()}
            if set(probs) != set(q["criteria"]) or a["choice"] not in probs:
                raise SchemaError(f"choice {key!r} options do not match the request")
            out[key] = Answer("choice", a["choice"], probs, float(a["confidence"]))
        else:
            probs = {k: float(v) for k, v in a["probabilities"].items()}
            if len(probs) != len(q["criteria"]):
                raise SchemaError(f"score {key!r} levels do not match the request")
            out[key] = Answer("score", float(a["score"]), probs, float(a["confidence"]))
    return out


class Client:
    """One keep-alive HTTP connection per client (use one client per worker thread)."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 30):
        self.url = urlparse(base_url or os.environ.get("JEV_BASE_URL", "http://127.0.0.1:8765"))
        self.api_key = api_key or os.environ.get("JEV_API_KEY")
        self.timeout = timeout
        self.conn = None

    def _connect(self):
        cls = http.client.HTTPSConnection if self.url.scheme == "https" else http.client.HTTPConnection
        self.conn = cls(self.url.hostname, self.url.port or (443 if self.url.scheme == "https" else 80), timeout=self.timeout)

    def _call(self, method: str, path: str, body: dict | None = None):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        for attempt in range(2):
            if self.conn is None:
                self._connect()
            try:
                self.conn.request(method, path, json.dumps(body).encode() if body is not None else None, headers)
                r = self.conn.getresponse()
                data = r.read()
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}: {data[:200]!r}")
                return json.loads(data), r.getheader("X-Process-Time-Ms")
            except (http.client.HTTPException, ConnectionError, OSError):
                self.conn = None
                if attempt:
                    raise

    def models(self) -> dict:
        return self._call("GET", "/v1/models")[0]

    def system_one(self, body: dict) -> tuple[dict, float, float | None]:
        """-> (raw response, round-trip ms, server-side ms)."""
        t = time.perf_counter()
        resp, server_ms = self._call("POST", "/v1/systemone", body)
        return resp, (time.perf_counter() - t) * 1000, float(server_ms) if server_ms else None

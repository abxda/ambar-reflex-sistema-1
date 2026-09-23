"""jevlocal: self-hosted System One decisions with a TypeSafe Jev-compatible API.

  jevlocal serve     [--host 0.0.0.0] [--port 8765] [--api-key KEY]   HTTP API (POST /v1/systemone)
  jevlocal score     IN.jsonl OUT.jsonl                               Jev request bodies -> answers
  jevlocal selftest                                                   load, answer the docs example, time it

Every option can also be set as an environment variable JEVLOCAL_<NAME> (e.g. JEVLOCAL_PORT).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import __version__


def _env(name: str, default):
    value = os.environ.get(f"JEVLOCAL_{name}")
    if value is None:
        return default
    return type(default)(value) if default is not None else value


def _default_gguf() -> str | None:
    candidates = [os.environ.get("JEVLOCAL_GGUF", "")]
    here = Path(__file__).resolve()
    for parent in list(here.parents)[:6]:
        candidates += [parent / "models" / "Qwen_Qwen3.5-4B-Q8_0.gguf", parent / "models" / "gguf" / "Qwen_Qwen3.5-4B-Q8_0.gguf"]
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def _engine_options() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_argument_group("engine")
    gguf = _default_gguf()
    g.add_argument("--gguf", default=gguf, required=gguf is None, help="GGUF checkpoint (default: bundled Q8_0)")
    g.add_argument("--ctx", type=int, default=_env("CTX", 16384), help="context tokens shared by all branches")
    g.add_argument("--seqs", type=int, default=_env("SEQS", 16), help="max parallel branches (reduced automatically to keep VRAM headroom)")
    g.add_argument("--batch", type=int, default=_env("BATCH", 2048))
    g.add_argument("--ubatch", type=int, default=_env("UBATCH", 2048), help="capped at 512 when the GPU drives a display")
    g.add_argument("--gpu-layers", type=int, default=_env("GPU_LAYERS", 999))
    g.add_argument("--temperature", type=float, default=_env("TEMPERATURE", 1.8),
                   help="logit temperature; 1.8 minimizes NLL on 554 labeled decisions")
    g.add_argument("--debias", choices=["none", "noul", "all"], default=_env("DEBIAS", "none"),
                   help="also score the reversed option order and average (costs one extra branch per question)")
    g.add_argument("--profile", choices=["semif", "reflex"], default=_env("PROFILE", "semif"),
                   help="prompt layout: semif (JSON, default) or reflex (markdown)")
    g.add_argument("--option-style", choices=["key", "desc"], default=_env("OPTION_STYLE", "key"),
                   help="key: show 'option: description' (default); desc: description only (SemIf parity)")
    return p


def _engine(args):
    from .engine import Engine

    started = time.perf_counter()
    engine = Engine(args.gguf, n_ctx=args.ctx, n_seq_max=args.seqs, n_batch=args.batch, n_ubatch=args.ubatch,
                    n_gpu_layers=args.gpu_layers, temperature=args.temperature, profile=args.profile)
    engine.warmup()
    print(f"[jevlocal] {Path(args.gguf).name} ready in {time.perf_counter() - started:.1f}s "
          f"(ctx={engine.n_ctx}, seqs={engine.n_seq_max}, T={args.temperature})", file=sys.stderr, flush=True)
    return engine


EXAMPLE = {
    "state": "Help! My payouts have been failing for 3 days.",
    "model": "jev-latest",
    "questions": {
        "is_urgent": {"type": "noul", "instructions": "Does this convey urgency?",
                      "criteria": {"true": "Explicitly time-sensitive", "false": "No urgency expressed"}},
        "department": {"type": "choice", "instructions": "Which team should handle this?",
                       "criteria": {"billing": "Payments, invoicing, refunds", "technical": "Bugs, outages, integrations",
                                    "sales": "Pricing, upgrades, new accounts"}},
        "frustration": {"type": "score", "instructions": "How frustrated is the customer?",
                        "criteria": ["Calm", "Frustrated", "Very angry"]},
    },
}


def main(argv=None) -> None:
    common = _engine_options()
    parser = argparse.ArgumentParser(prog="jevlocal", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"jevlocal {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", parents=[common], help="run the HTTP API")
    s.add_argument("--host", default=_env("HOST", "127.0.0.1"), help="0.0.0.0 to accept remote clients")
    s.add_argument("--port", type=int, default=_env("PORT", 8765))
    s.add_argument("--served-name", default=_env("SERVED_NAME", "jev-local-qwen3.5-4b"))
    s.add_argument("--api-key", default=os.environ.get("JEVLOCAL_API_KEY"), help="require 'Authorization: Bearer <key>'")
    s.add_argument("--max-jobs", type=int, default=_env("MAX_JOBS", 16), help="requests merged into one GPU batch")
    s.add_argument("--max-readouts", type=int, default=_env("MAX_READOUTS", 128), help="scored prompts per GPU batch")
    s.add_argument("--max-queue", type=int, default=_env("MAX_QUEUE", 1024), help="queued requests before 529")
    s.add_argument("--access-log", action="store_true")
    c = sub.add_parser("score", parents=[common], help="score Jev request bodies from a JSONL file")
    c.add_argument("input")
    c.add_argument("output")
    sub.add_parser("selftest", parents=[common], help="answer the TypeSafe docs example and time it")
    args = parser.parse_args(argv)

    engine = _engine(args)
    from .prompts import answers, plan_request

    if args.command == "serve":
        from .server import serve

        public = {"ctx": engine.n_ctx, "seqs": engine.n_seq_max, "temperature": args.temperature,
                  "debias": args.debias, "option_style": args.option_style, "profile": args.profile,
                  "version": __version__}
        serve(engine, host=args.host, port=args.port, served_name=args.served_name, gguf_name=Path(args.gguf).name,
              debias=args.debias, option_style=args.option_style, profile=args.profile, api_key=args.api_key, max_jobs=args.max_jobs,
              max_readouts=args.max_readouts, max_queue=args.max_queue, access_log=args.access_log, public=public)
    elif args.command == "score":
        with open(args.input) as src, open(args.output, "w") as dst:
            for line in src:
                if not line.strip():
                    continue
                body = json.loads(line)
                plan = plan_request(body, args.debias, args.option_style, args.profile)
                started = time.perf_counter()
                engine.score(plan.readouts)
                out = {"answers": answers(plan), "ms": round((time.perf_counter() - started) * 1000, 2)}
                if "id" in body:
                    out["id"] = body["id"]
                dst.write(json.dumps(out) + "\n")
    else:
        times = []
        for _ in range(10):
            plan = plan_request(EXAMPLE, args.debias, args.option_style, args.profile)
            started = time.perf_counter()
            engine.score(plan.readouts)
            times.append((time.perf_counter() - started) * 1000)
        result = answers(plan)
        print(json.dumps(result, indent=1))
        ok = result["department"]["choice"] == "billing" and result["is_urgent"]["noul"] > 0.5
        print(f"selftest {'OK' if ok else 'UNEXPECTED ANSWERS'}: 3 questions in {sorted(times)[5]:.1f} ms (median of 10)")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

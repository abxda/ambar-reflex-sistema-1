"""In-process latency/throughput of the engine on realistic request shapes."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jevlocal.engine import Engine  # noqa: E402
from jevlocal.prompts import plan_request  # noqa: E402

HERE = Path(__file__).resolve().parent
TICKET = "Help! My payouts have been failing for 3 days."
CHOICE = {"type": "choice", "instructions": "Which team should handle this?",
          "criteria": {"billing": "Payments, invoicing, refunds", "technical": "Bugs, outages, integrations",
                       "sales": "Pricing, upgrades, new accounts"}}
EXAMPLE = {
    "is_urgent": {"type": "noul", "instructions": "Does this convey urgency?",
                  "criteria": {"true": "Explicitly time-sensitive", "false": "No urgency expressed"}},
    "department": CHOICE,
    "frustration": {"type": "score", "instructions": "How frustrated is the customer?",
                    "criteria": ["Calm", "Frustrated", "Very angry"]},
}


def shared_state_case():
    """21 criteria over one ~1.4k-token state (first group of SemIf's shape777 fixture)."""
    rows = []
    for line in open(HERE.parents[1] / "SemIf" / "benchmarks" / "data" / "shape777.jsonl"):
        row = json.loads(line)
        if rows and row["state"] != rows[0]["state"]:
            break
        rows.append(row)
    questions = {r["id"]: {"type": "choice", "instructions": r["question"],
                           "criteria": {o["id"]: o["description"] for o in r["options"]}} for r in rows}
    return {"state": rows[0]["state"], "model": "x", "questions": questions}


def timed(engine, bodies, debias, repeat):
    times, tokens = [], 0
    for _ in range(repeat):
        plans = [plan_request(b, debias) for b in bodies]
        started = time.perf_counter()
        tokens = engine.score([r for p in plans for r in p.readouts])
        times.append((time.perf_counter() - started) * 1000)
    times.sort()
    return {"p50_ms": round(statistics.median(times), 1), "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1),
            "tokens": tokens}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--ubatch", type=int, default=2048)
    ap.add_argument("--batch", type=int, default=4096)
    ap.add_argument("--seqs", type=int, default=32)
    ap.add_argument("--repeat", type=int, default=15)
    ap.add_argument("--min-shared", type=int, default=64)
    ap.add_argument("--out")
    args = ap.parse_args()
    started = time.perf_counter()
    engine = Engine(args.gguf, n_ubatch=args.ubatch, n_batch=args.batch, n_seq_max=args.seqs, min_shared_tokens=args.min_shared)
    load_s = time.perf_counter() - started
    single = {"state": TICKET, "model": "x", "questions": {"d": CHOICE}}
    example = {"state": TICKET, "model": "x", "questions": EXAMPLE}
    shared = shared_state_case()
    tickets = [{"state": f"Ticket #{i}: {TICKET} Order {1000 + i} is affected.", "model": "x", "questions": {"d": CHOICE}}
               for i in range(64)]
    timed(engine, [example], "none", 3)  # warm-up
    result = {"gguf": Path(args.gguf).name, "ubatch": args.ubatch, "min_shared": args.min_shared, "load_s": round(load_s, 1),
              "single_choice": timed(engine, [single], "none", args.repeat),
              "jev_example_3q": timed(engine, [example], "none", args.repeat),
              "jev_example_3q_noul_debias": timed(engine, [example], "noul", args.repeat),
              "shared_state_21q": timed(engine, [shared], "none", max(3, args.repeat // 3))}
    burst = timed(engine, tickets, "none", 3)
    burst["decisions_per_s"] = round(64 / (burst["p50_ms"] / 1000), 1)
    result["burst_64_requests"] = burst
    print(json.dumps(result), flush=True)
    if args.out:
        with open(args.out, "a") as f:
            f.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()

"""Concurrent HTTP load against any /v1/systemone endpoint (local server or TypeSafe).

Each client sends support-ticket style requests (one Choice + one Noul + one Score)
back to back; reports latency percentiles and throughput.
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
import urllib.request

SUBJECTS = ["payouts failing", "charged twice", "cannot log in", "API returns 500", "upgrade pricing",
            "refund request", "webhook timeouts", "invoice missing VAT", "SSO broken", "rate limited"]


def body(i: int, model: str) -> dict:
    subject = SUBJECTS[i % len(SUBJECTS)]
    return {
        "state": f"Ticket {1000 + i} from customer {i % 97}: {subject}. It started {1 + i % 5} days ago "
                 f"and affects {10 * (1 + i % 9)} users. Please advise.",
        "model": model,
        "questions": {
            "team": {"type": "choice", "instructions": "Which team should handle this ticket?",
                     "criteria": {"billing": "Payments, invoicing, refunds", "technical": "Bugs, outages, integrations",
                                  "sales": "Pricing, upgrades, new accounts", "security": "Access, SSO, abuse"}},
            "urgent": {"type": "noul", "instructions": "Is this time-sensitive?"},
            "severity": {"type": "score", "instructions": "How severe is the business impact?",
                         "criteria": ["None", "Minor", "Major", "Critical"]},
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--api-key")
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--clients", type=int, nargs="+", default=[1, 4, 16])
    ap.add_argument("--seconds", type=float, default=15)
    args = ap.parse_args()
    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"
    endpoint = args.url.rstrip("/") + "/v1/systemone"
    for clients in args.clients:
        latencies, errors, lock = [], [0], threading.Lock()
        stop = time.perf_counter() + args.seconds

        def client(cid: int):
            i = cid * 100000
            while time.perf_counter() < stop:
                req = urllib.request.Request(endpoint, json.dumps(body(i, args.model)).encode(), headers)
                started = time.perf_counter()
                try:
                    json.load(urllib.request.urlopen(req, timeout=120))
                    with lock:
                        latencies.append(time.perf_counter() - started)
                except Exception:  # noqa: BLE001
                    with lock:
                        errors[0] += 1
                i += 1

        threads = [threading.Thread(target=client, args=(c,)) for c in range(clients)]
        began = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall = time.perf_counter() - began
        latencies.sort()
        q = lambda p: round(1000 * latencies[min(len(latencies) - 1, int(p * len(latencies)))], 1)
        print(json.dumps({"clients": clients, "requests": len(latencies), "errors": errors[0],
                          "req_per_s": round(len(latencies) / wall, 2), "questions_per_s": round(3 * len(latencies) / wall, 1),
                          "p50_ms": q(0.5), "p95_ms": q(0.95), "p99_ms": q(0.99),
                          "mean_ms": round(1000 * statistics.mean(latencies), 1)}), flush=True)


if __name__ == "__main__":
    main()

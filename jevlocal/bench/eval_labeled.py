"""Accuracy and calibration of a System One endpoint on labeled decision rows.

Rows use the SemIf format: {id, state, question, options: [{id, description}], label}.
Each row becomes a Jev `choice` request, so the same harness scores:

  * the local engine in-process      --gguf models/...gguf
  * any Jev-compatible HTTP endpoint  --url http://127.0.0.1:8765  (or https://api.typesafe.ai)

Optionally compares against reference predictions (SemIf bf16 JSONL) for parity.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load_rows(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def body_for(row, model, as_noul=False):
    if as_noul:  # binary yes/no rows asked as a Noul; label 0 must be "yes"
        return {"state": row["state"], "model": model, "questions": {"q": {"type": "noul", "instructions": row["question"]}}}
    return {
        "state": row["state"],
        "model": model,
        "questions": {"q": {"type": "choice", "instructions": row["question"],
                            "criteria": {o["id"]: o["description"] for o in row["options"]}}},
    }


def run_local(rows, args):
    from jevlocal.engine import Engine
    from jevlocal.prompts import plan_request

    if not hasattr(run_local, "engine"):  # one model load for every dataset
        run_local.engine = Engine(args.gguf, n_ctx=args.ctx, n_seq_max=args.seqs, temperature=1.0, profile=args.profile)
    engine = run_local.engine
    for row in rows[: args.batch]:  # warm-up
        engine.score(plan_request(body_for(row, "local", args.as_noul), args.debias, args.option_style, args.profile).readouts)
    preds, started = [], time.perf_counter()
    for i in range(0, len(rows), args.batch):
        chunk = rows[i : i + args.batch]
        plans = [plan_request(body_for(r, "local", args.as_noul), args.debias, args.option_style, args.profile) for r in chunk]
        engine.score([ro for p in plans for ro in p.readouts])
        for plan in plans:
            runs = [ro.probabilities for ro in plan.readouts]
            preds.append([sum(run[k] for run in runs) / len(runs) for k in range(len(runs[0]))])  # noul: [yes, no]
    return preds, time.perf_counter() - started


def run_http(rows, args):
    preds, started = [], time.perf_counter()
    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"
    for row in rows:
        req = urllib.request.Request(args.url.rstrip("/") + "/v1/systemone",
                                     json.dumps(body_for(row, args.model, args.as_noul)).encode(), headers)
        answer = json.load(urllib.request.urlopen(req, timeout=120))["answers"]["q"]
        if args.as_noul:
            preds.append([answer["noul"], 1 - answer["noul"]])
        else:
            preds.append([answer["probabilities"][o["id"]] for o in row["options"]])
    return preds, time.perf_counter() - started


def temper(p, T):
    w = [max(x, 1e-12) ** (1 / T) for x in p]
    s = sum(w)
    return [x / s for x in w]


def metrics(rows, preds, T=1.0):
    preds = [temper(p, T) for p in preds]
    labels = [r["label"] for r in rows]
    hits = [max(range(len(p)), key=p.__getitem__) == y for p, y in zip(preds, labels)]
    per_class = {}
    for r, h in zip(rows, hits):
        per_class.setdefault(r["options"][r["label"]]["id"], []).append(h)
    nll = -sum(math.log(max(p[y], 1e-12)) for p, y in zip(preds, labels)) / len(rows)
    brier = sum(sum((pk - (k == y)) ** 2 for k, pk in enumerate(p)) for p, y in zip(preds, labels)) / len(rows)
    bins = [[] for _ in range(10)]
    for p, h in zip(preds, hits):
        bins[min(int(max(p) * 10), 9)].append((max(p), h))
    ece = sum(abs(sum(c for c, _ in b) / len(b) - sum(h for _, h in b) / len(b)) * len(b) for b in bins if b) / len(rows)
    return {"n": len(rows), "accuracy": sum(hits) / len(rows),
            "balanced_accuracy": sum(sum(v) / len(v) for v in per_class.values()) / len(per_class),
            "nll": nll, "brier": brier, "ece": ece, "mean_max_prob": sum(max(p) for p in preds) / len(preds)}


def fit_temperature(rows, preds):
    grid = [round(0.5 + 0.05 * i, 2) for i in range(71)]  # 0.5 .. 4.0
    return min(grid, key=lambda T: metrics(rows, preds, T)["nll"])


def parity(rows, preds, ref_path):
    ref = {r["id"]: r for r in load_rows(ref_path)}
    agree, tv, n = 0, 0.0, 0
    for row, p in zip(rows, preds):
        r = ref.get(row["id"])
        if not r:
            continue
        q = [r["probabilities"][r["option_ids"].index(o["id"])] for o in row["options"]]
        agree += max(range(len(p)), key=p.__getitem__) == max(range(len(q)), key=q.__getitem__)
        tv += 0.5 * sum(abs(a - b) for a, b in zip(p, q))
        n += 1
    return {"n": n, "argmax_agreement": agree / n, "mean_total_variation": tv / n} if n else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--gguf")
    ap.add_argument("--url")
    ap.add_argument("--api-key")
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--ref", nargs="*", default=[], help="reference predictions per data file (SemIf format)")
    ap.add_argument("--debias", default="none")
    ap.add_argument("--option-style", default="key")
    ap.add_argument("--profile", default="semif", choices=["semif", "reflex"])
    ap.add_argument("--batch", type=int, default=16, help="rows scored per engine call (local)")
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--seqs", type=int, default=32)
    ap.add_argument("--as-noul", action="store_true", help="ask binary yes/no rows as Noul questions")
    ap.add_argument("--out")
    args = ap.parse_args()
    report = {"config": {k: v for k, v in vars(args).items() if k != "api_key"}, "datasets": {}}
    all_rows, all_preds = [], []
    for i, path in enumerate(args.data):
        rows = [r for r in load_rows(path) if r.get("label") is not None]
        preds, seconds = run_http(rows, args) if args.url else run_local(rows, args)
        entry = {"raw": metrics(rows, preds), "seconds": seconds, "ms_per_row": 1000 * seconds / len(rows)}
        if i < len(args.ref) and args.ref[i]:
            entry["parity_vs_ref"] = parity(rows, preds, args.ref[i])
        report["datasets"][Path(path).name] = entry
        all_rows += rows
        all_preds += preds
        print(Path(path).name, json.dumps(entry), flush=True)
    T = fit_temperature(all_rows, all_preds)
    report["pooled"] = {"raw": metrics(all_rows, all_preds), "fitted_temperature": T,
                        "calibrated": metrics(all_rows, all_preds, T)}
    print("pooled", json.dumps(report["pooled"]), flush=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

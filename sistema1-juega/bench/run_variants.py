"""Pick the question wording by mean progress: N real-time runs per variant, same seed."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from agent.modes import label_run, run_realtime
from bench.gpu_guard import Guard, GpuUnsafe

SEED = 1987


def main(variants=("A", "B", "C", "D"), n=3, factor=None):
    factor = factor or json.loads(Path("runs/calibration.json").read_text())["factor"]
    guard = Guard()
    summary = {}
    for v in variants:
        rows = []
        for i in range(n):
            out = Path(f"runs/variants/{v}-{SEED}-{i}")
            if out.with_suffix(".meta.json").exists():
                meta = json.loads(out.with_suffix(".meta.json").read_text())
            else:
                print(f"[{v} #{i}] gpu {guard.check('pre')}", flush=True)
                meta = run_realtime(SEED, v, out, factor=factor, verbose=False)
                label_run(out)
                print(f"[{v} #{i}] {meta['result']} gpu {guard.check('post')}", flush=True)
                guard.cooldown(60)
            decs = [json.loads(l) for l in open(out.with_suffix(".jsonl"))]
            rows.append({"progress": meta["result"]["progress"], "score": meta["result"]["score"],
                         "stalled": meta["result"]["stalled"],
                         "rtt_ms": statistics.median(d["rtt_ms"] for d in decs if d.get("rtt_ms")) if decs else None,
                         "tokens": statistics.median(d["input_tokens"] for d in decs if d.get("input_tokens")) if decs else None})
        summary[v] = {"runs": rows, "mean_progress": statistics.fmean(r["progress"] for r in rows)}
        print(v, json.dumps(summary[v]["mean_progress"]), flush=True)
    best = max(summary, key=lambda k: summary[k]["mean_progress"])
    Path("runs/variants.json").write_text(json.dumps({"best": best, "factor": factor, "variants": summary}, indent=1))
    print("BEST", best)


if __name__ == "__main__":
    try:
        main()
    except GpuUnsafe as e:
        print("ABORT", e)
        sys.exit(2)

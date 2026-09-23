"""`make benchmark`: every phase of the study, resumable (finished runs are reused), GPU-guarded.

Prerequisite: the System One server is up at $JEV_BASE_URL (bench/server.sh start).
Phases: fixture -> calibration -> variants -> realtime x5 -> turns -> random x5 -> concurrency
        -> labels -> analysis -> report -> videos + screenshots.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

from agent.client import Client, parse_answers
from agent.modes import label_run, run_baseline, run_realtime, run_turns
from agent.questions import KEYS, request_body
from bench import run_variants
from bench.gpu_guard import Guard, GpuUnsafe
from game.core import World
from game.describe import describe

ROOT = Path(__file__).resolve().parents[1]
SEED = 1987
N = 5


def _done(p: Path) -> bool:
    return p.with_suffix(".meta.json").exists()


def fixture():
    c = Client()
    (ROOT / "fixtures" / "models.json").write_text(json.dumps(c.models(), indent=1))
    body = request_body(describe(World(SEED), "es"), "B")
    raw, rtt, _ = c.system_one(body)
    parse_answers(raw, {k: body["questions"][k] for k in KEYS})  # schema check
    (ROOT / "fixtures" / "systemone_6q_start.json").write_text(
        json.dumps({"request": body, "response": raw, "latency_ms": round(rtt, 1)}, ensure_ascii=False, indent=1))
    print(f"[fixture] schema OK, {rtt:.0f} ms, {raw['usage']['input_tokens']} tokens")


def calibration(guard: Guard):
    if (ROOT / "runs" / "calibration.json").exists():
        return
    out = ROOT / "runs" / "calib" / "turns-B-2024"
    guard.check("calibration")
    run_turns(2024, "B", out, every=12, idle_s=0.1, gate=False, guard=guard)
    label_run(out)
    from bench import calibrate
    data = calibrate.pairs([out.with_suffix(".jsonl")])
    f = calibrate.fit(data)
    (ROOT / "runs" / "calibration.json").write_text(json.dumps(
        {"n": len(data), "factor": f, "T_game": round(1.8 / f, 3), "ece_server": calibrate.ece(data, 1.0),
         "ece_game": calibrate.ece(data, f)}, indent=1))
    guard.cooldown(60)


def realtime(guard: Guard, variant: str, factor: float):
    for i in range(N):
        out = ROOT / "runs" / "bench" / "realtime" / f"rt-{variant}-{SEED}-{i}"
        if _done(out):
            continue
        guard.check(f"realtime {i}")
        m = run_realtime(SEED, variant, out, factor=factor, verbose=False, guard=guard)
        label_run(out)
        print(f"[realtime {i}] {m['result']}", flush=True)
        if getattr(guard, "tripped", None):
            raise GpuUnsafe(guard.tripped)
        guard.cooldown(60)


def turns(guard: Guard, variant: str, factor: float):
    """Turn mode is deterministic (same seed, same server answers), so 2 runs verify it; more would be copies."""
    for i in range(2):
        out = ROOT / "runs" / "bench" / "turns" / f"turns-{variant}-{SEED}-{i}"
        if _done(out):
            continue
        guard.check(f"turns {i}")
        m = run_turns(SEED, variant, out, every=8, idle_s=0.1, factor=factor, guard=guard)
        label_run(out)
        print(f"[turns {i}] {m['result']}", flush=True)
        if getattr(guard, "tripped", None):
            raise GpuUnsafe(guard.tripped)
        guard.cooldown(90)


def random_agent():
    for i in range(N):
        out = ROOT / "runs" / "bench" / "random" / f"random-{SEED}-{i}"
        if not _done(out):
            run_baseline(SEED, "random", out, run=i)


def concurrency(guard: Guard, variant: str, factor: float):
    """Two requests in flight vs one: does batching raise the decision rate or just add staleness?"""
    path = ROOT / "runs" / "concurrency.json"
    if path.exists():
        return
    res = {}
    for k in (1, 2):
        out = ROOT / "runs" / "concurrency" / f"inflight{k}"
        guard.check(f"concurrency {k}")
        m = run_realtime(SEED, variant, out, max_inflight=k, factor=factor, verbose=False, max_frames=30 * 60, guard=guard)
        decs = [json.loads(l) for l in open(out.with_suffix(".jsonl"))]
        lat = [d["rtt_ms"] for d in decs if d.get("rtt_ms")]
        res[f"inflight_{k}"] = {"decisions": len(decs), "seconds": m["result"]["seconds"],
                                "decisions_per_s": len(decs) / m["result"]["seconds"],
                                "lat_mean_ms": st.fmean(lat), "lat_p95_ms": sorted(lat)[int(0.95 * (len(lat) - 1))],
                                "frames_per_decision": st.median(d["arr_frame"] - d["req_frame"] for d in decs)}
        guard.cooldown(45)
    path.write_text(json.dumps(res, indent=1))
    print("[concurrency]", json.dumps(res), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-video", action="store_true")
    args = ap.parse_args()
    guard = Guard()
    try:
        guard.check("start")
        fixture()
        calibration(guard)
        factor = json.loads((ROOT / "runs" / "calibration.json").read_text())["factor"]
        run_variants.main(factor=factor)
        best = json.loads((ROOT / "runs" / "variants.json").read_text())["best"]
        print(f"[variants] best = {best}", flush=True)
        realtime(guard, best, factor)
        turns(guard, best, factor)
        random_agent()
        concurrency(guard, best, factor)
    except GpuUnsafe as e:
        print(f"ABORT (GPU safety): {e}", flush=True)
        sys.exit(2)
    from bench import analyze, report
    analyze.main()
    report.main()
    if not args.skip_video:
        from bench import make_videos
        make_videos.main()


if __name__ == "__main__":
    main()

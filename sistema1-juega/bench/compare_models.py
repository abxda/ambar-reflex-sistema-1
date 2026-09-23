"""Same protocol, three System One models (no thinking), one at a time on the GPU:

  1) intelligence without time pressure: the 554 labeled decisions (authored + WANLI + Every) over HTTP
  2) game calibration: turn-based run, seed 2024, argmax (no gating) -> fitted factor
  3) real time: N runs, seed 1987, variant D, the model's own calibration factor

Qwen3.5-4B reuses its published benchmark runs and calibration (same protocol); it only adds step 1.
GPU safety: the server is stopped between models, cooldowns between runs, watchdog aborts on Xid/80 C.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from agent.modes import label_run, run_realtime, run_turns
from bench import calibrate
from bench.gpu_guard import Guard, GpuUnsafe

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
GGUF = REPO / "models" / "gguf"
URL = os.environ.get("JEV_BASE_URL", "http://127.0.0.1:8765")
MODELS = {
    "qwen35-4b": {"gguf": "Qwen_Qwen3.5-4B-Q8_0.gguf", "label": "Qwen3.5-4B Q8_0"},
    "gemma4-e4b": {"gguf": "google_gemma-4-E4B-it-Q6_K.gguf", "label": "Gemma 4 E4B Q6_K"},
    "qwen35-9b": {"gguf": "Qwen_Qwen3.5-9B-Q5_K_M.gguf", "label": "Qwen3.5-9B Q5_K_M"},
}
EVAL_DATA = [REPO / "bench-data" / "authored144.jsonl", REPO / "bench-data" / "wanli256.jsonl",
             REPO / "bench-data" / "every" / "gold154.jsonl"]


def _health():
    try:
        return json.load(urllib.request.urlopen(URL + "/health", timeout=3))
    except Exception:  # noqa: BLE001
        return None


def server(action: str, gguf: Path | None = None) -> None:
    env = dict(os.environ)
    if gguf:
        env["JEVLOCAL_GGUF"] = str(gguf)
    subprocess.run([str(ROOT / "bench" / "server.sh"), action, "semif"], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    if action == "start":
        h = _health()
        if not h or Path(h["gguf"]).name != gguf.name:
            raise RuntimeError(f"server did not come up with {gguf.name}: {h}")
        print(f"[server] {h['gguf']} arch={h.get('arch')} chat={h.get('chat')} ctx={h['ctx']} seqs={h['seqs']}", flush=True)


def evaluate(out: Path) -> dict:
    if out.exists():
        return json.loads(out.read_text())
    cmd = [sys.executable, str(REPO / "jevlocal" / "bench" / "eval_labeled.py"), "--url", URL,
           "--data", *map(str, EVAL_DATA), "--out", str(out)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return json.loads(out.read_text())


def run_model(key: str, n: int, guard: Guard) -> None:
    spec = MODELS[key]
    out = ROOT / "runs" / "models" / key
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.json").write_text(json.dumps(spec, indent=1))
    if _health():
        server("stop")
    guard.check(f"{key} start")
    server("start", GGUF / spec["gguf"])
    try:
        t = time.time()
        ev = evaluate(out / "eval.json")
        print(f"[{key}] eval 554: acc {ev['pooled']['raw']['accuracy']:.3f} ({time.time() - t:.0f}s)", flush=True)
        guard.check(f"{key} eval")
        guard.cooldown(45)
        if key == "qwen35-4b":
            return  # real-time runs and calibration: the published benchmark (same protocol)
        cal_run = out / "calib" / "turns-B-2024"
        if not (out / "calibration.json").exists():
            run_turns(2024, "B", cal_run, every=12, idle_s=0.1, gate=False, guard=guard)
            label_run(cal_run)
            data = calibrate.pairs([cal_run.with_suffix(".jsonl")])
            f = calibrate.fit(data)
            (out / "calibration.json").write_text(json.dumps(
                {"n": len(data), "factor": f, "T_game": round(1.8 / f, 3), "ece_server": calibrate.ece(data, 1.0),
                 "ece_game": calibrate.ece(data, f)}, indent=1))
            print(f"[{key}] calibration factor {f}", flush=True)
            if getattr(guard, "tripped", None):
                raise GpuUnsafe(guard.tripped)
            guard.cooldown(60)
        factor = json.loads((out / "calibration.json").read_text())["factor"]
        for i in range(n):
            run = out / "realtime" / f"rt-D-1987-{i}"
            if run.with_suffix(".meta.json").exists():
                continue
            guard.check(f"{key} realtime {i}")
            m = run_realtime(1987, "D", run, factor=factor, verbose=False, guard=guard)
            label_run(run)
            print(f"[{key}] realtime {i}: {m['result']}", flush=True)
            if getattr(guard, "tripped", None):
                raise GpuUnsafe(guard.tripped)
            guard.cooldown(60)
    finally:
        server("stop")
        guard.cooldown(30)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    ap.add_argument("-n", type=int, default=3)
    args = ap.parse_args()
    guard = Guard()
    try:
        for key in args.models:
            run_model(key, args.n, guard)
    except GpuUnsafe as e:
        print("ABORT (GPU safety):", e, flush=True)
        sys.exit(2)


if __name__ == "__main__":
    main()

"""`make system2`: Sistema 1 vs Sistema 2. Runs the generative baseline on Ollama (qwen3.5:4b) with the
same questions. Refuses to run while the System One server holds VRAM (never kills user processes)."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from agent import system2
from agent.modes import label_run, run_realtime, run_turns
from bench.gpu_guard import Guard, GpuUnsafe, gpu_stats

ROOT = Path(__file__).resolve().parents[1]
SEED = 1987


def _up(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(n_realtime: int = 3):
    if _up("http://127.0.0.1:8765/health"):
        print("System One server is running (VRAM in use). Stop it first: bench/server.sh stop")
        sys.exit(1)
    if not _up("http://127.0.0.1:11434/api/tags"):
        print("Ollama is not reachable at 127.0.0.1:11434")
        sys.exit(1)
    guard = Guard()
    print("gpu", gpu_stats())
    # warm-up (loads the model) and schema smoke test
    rec = system2.ask(None, "Soldado en suelo, arma N, vidas 3, avance 0%. Terreno: plano. Amenazas: ninguna.", "B")
    print("[system2] warm-up:", rec["rtt_ms"], "ms", rec["tag"], rec["parse_error"], repr(rec["system2_text"][:120]))
    try:
        for i in range(n_realtime):
            out = ROOT / "runs" / "bench" / "system2_realtime" / f"s2rt-{SEED}-{i}"
            if out.with_suffix(".meta.json").exists():
                continue
            guard.check(f"s2 realtime {i}")
            m = run_realtime(SEED, "B", out, asker=system2.ask, mode="system2_realtime", verbose=False, guard=guard)
            label_run(out)
            print(f"[system2 realtime {i}] {m['result']}", flush=True)
            guard.cooldown(60)
        out = ROOT / "runs" / "bench" / "system2_turns" / f"s2turns-{SEED}-0"
        if not out.with_suffix(".meta.json").exists():
            guard.check("s2 turns")
            m = run_turns(SEED, "B", out, every=8, idle_s=0.1, asker=system2.ask, mode="system2_turns", guard=guard)
            label_run(out)
            print(f"[system2 turns] {m['result']}", flush=True)
    except GpuUnsafe as e:
        print("ABORT (GPU safety):", e)
    finally:  # unload the model from VRAM
        body = json.dumps({"model": system2.MODEL, "keep_alive": 0}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate", body,
                                                          {"Content-Type": "application/json"}), timeout=30)
        except Exception:  # noqa: BLE001
            pass
        print("gpu after unload", gpu_stats())


if __name__ == "__main__":
    main()

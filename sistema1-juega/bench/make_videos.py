"""Best real-time run -> 1080p60 landscape, 1080x1920 vertical, 30-60 s highlights, 4 screenshots."""

from __future__ import annotations

import json
from pathlib import Path

from bench.render_video import render
from game.core import FPS

ROOT = Path(__file__).resolve().parents[1]


def best_run(cfg: str = "realtime") -> Path:
    metas = sorted((ROOT / "runs" / "bench" / cfg).glob("*.meta.json"))
    if not metas:
        metas = sorted((ROOT / "runs" / "first").glob("*.meta.json"))
    best = max(metas, key=lambda p: (json.loads(p.read_text())["result"]["progress"], json.loads(p.read_text())["result"]["score"]))
    return best.with_name(best.name.replace(".meta.json", ""))


def key_moments(run: Path) -> dict:
    meta = json.loads(run.with_suffix(".meta.json").read_text())
    decs = [json.loads(l) for l in open(run.with_suffix(".jsonl")) if "raw" in l]
    decs = [d for d in decs if "raw" in d]
    hi = max(decs, key=lambda d: d["conf"])                       # highest calibrated confidence
    doubt = next((d for d in decs if d["tag"] == "FALLBACK"), None) or next((d for d in decs if d["tag"] == "DUDA"), hi)
    ev = meta["events"]
    kill = next((f for f, n in ev if n == "explode"), None)
    death = next((f for f, n in ev if n == "die"), None)
    boss = next((f for f, n in ev if n == "boss"), None)
    jump = next((d["arr_frame"] for d in decs if d["action"]["jump"]), None)
    return {"high_conf": hi["arr_frame"], "doubt": doubt["arr_frame"], "kill": kill, "death": death,
            "boss": boss, "jump": jump, "frames": meta["frames"], "hi_conf_value": hi["conf"], "doubt_tag": doubt["tag"]}


def highlight_segments(m: dict, target_s: int = 45) -> list:
    total = m["frames"]
    if total <= target_s * FPS:
        return [(0, total)]
    points = [p for p in (m["high_conf"], m["doubt"], m["jump"], m["kill"], m["death"], m["boss"]) if p is not None]
    segs = sorted((max(0, p - 4 * FPS), min(total, p + 5 * FPS)) for p in points)
    merged = []
    for a, b in segs:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    if m["boss"] is not None:  # finish on the boss fight if it happened
        merged.append((m["boss"], min(total, m["boss"] + 12 * FPS)))
    out, used = [], 0
    for a, b in merged:
        b = min(b, a + (target_s * FPS - used))
        if b > a:
            out.append((a, b))
            used += b - a
        if used >= target_s * FPS:
            break
    if used < 30 * FPS:  # pad to at least 30 s with the opening
        out.insert(0, (0, min(total, 30 * FPS - used)))
    return out


def highlight_clips(m: dict, target_s: int = 45) -> list:
    """Key moments at normal speed; if the run is short, add 0.5x replays of the high-confidence and the
    FALLBACK/DUDA decisions (with captions) so the cut lands in 30-60 s."""
    clips = [(a, b, 1.0, None) for a, b in highlight_segments(m, target_s)]
    length = sum(b - a for a, b, _, _ in clips) / FPS
    if length < 30:
        hi, lo = m["high_conf"], m["doubt"]
        clips.append((max(0, hi - 60), min(m["frames"], hi + 90), 0.5, f"ALTA CONFIANZA: {m['hi_conf_value']:.2f}"))
        clips.append((max(0, lo - 60), min(m["frames"], lo + 90), 0.5, f"{m['doubt_tag']}: CONFIANZA BAJA"))
    return clips


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", help="run to render, e.g. runs/bench/realtime/rt-D-1987-2 (default: best real-time run)")
    ap.add_argument("--out-dir", default=str(ROOT), help="writes <out-dir>/video/*.mp4 and <out-dir>/screenshots/*.png")
    args = ap.parse_args(argv)
    run = Path(args.run).resolve() if args.run else best_run()
    if not run.with_suffix(".meta.json").exists():
        raise SystemExit(f"run not found: {run}.meta.json")
    out = Path(args.out_dir).resolve()
    m = key_moments(run)
    (out / "video").mkdir(parents=True, exist_ok=True)
    (out / "screenshots").mkdir(parents=True, exist_ok=True)
    shots = {}
    names = [("01_inicio", min(m["frames"] - 1, 4 * FPS)), ("02_alta_confianza", m["high_conf"] + 2),
             ("03_" + m["doubt_tag"].lower(), m["doubt"] + 2), ("04_accion", (m["boss"] or m["kill"] or m["death"] or m["frames"] // 2) + 20)]
    for name, f in names:
        shots[min(f, m["frames"] - 1)] = str(out / "screenshots" / f"{name}.png")
    print("[video] best run:", run.name, json.dumps(m))
    render(run, out / "video" / "sistema1_1080p60.mp4", "landscape", shots=shots)
    render(run, out / "video" / "sistema1_vertical_1080x1920.mp4", "vertical")
    render(run, out / "video" / "sistema1_momentos_clave.mp4", "landscape", clips=highlight_clips(m),
           title_s=2.0, outro_s=4.0)
    (out / "video" / "video_meta.json").write_text(json.dumps({"run": run.name, "moments": m}, indent=1))


if __name__ == "__main__":
    main()

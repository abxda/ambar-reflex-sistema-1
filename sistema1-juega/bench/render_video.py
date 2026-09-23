"""Headless render of a logged run: split screen (1920x1080) or vertical (1080x1920), title and
outro cards, chiptune + SFX, H.264/AAC via ffmpeg. Deterministic replay -> exact frames."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from agent.modes import replay  # noqa: E402
from game import font  # noqa: E402
from game.audio import SR, render_track  # noqa: E402
from game.core import FPS  # noqa: E402
from game.render import draw_world, upscale  # noqa: E402
from hud.panel import AMBER, BG, BRIGHT, DIM, RunView, draw_overlay, draw_panel, watermark  # noqa: E402

GAME_NAME = "ÁMBAR REFLEX"
LAYOUTS = {
    "landscape": {"size": (1920, 1080), "game": pygame.Rect(64, 60, 1024, 960), "panel": pygame.Rect(1136, 24, 760, 1032)},
    "vertical": {"size": (1080, 1920), "game": pygame.Rect(28, 60, 1024, 960), "panel": pygame.Rect(28, 1040, 1024, 852)},
}


def card(canvas: pygame.Surface, lines: list, t: float) -> None:
    canvas.fill(BG)
    W, H = canvas.get_size()
    y = H // 2 - sum(sc * 12 for _, sc, _ in lines) // 2
    for text, sc, col in lines:
        x = (W - font.width(text, sc)) // 2
        vis = text[: max(0, int(len(text) * min(1.0, t * 2.5)))] if sc >= 5 else text
        font.draw(canvas, vis, x, y, col, sc)
        y += sc * 12
    watermark(canvas, W - font.width("@abxda", 4) - 40, H - 80, 4)


def compose(canvas, layout, world, view, frame, game_surf):
    L = LAYOUTS[layout]
    canvas.fill((0, 0, 0))
    draw_world(game_surf, world)
    big = upscale(game_surf, 4, crt=True)
    canvas.blit(big, L["game"].topleft)
    draw_overlay(canvas, L["game"], world, view, frame)
    watermark(canvas, L["game"].right - font.width("@abxda", 4) - 16, L["game"].bottom - 56, 4)
    last = view.last
    flash = (last is not None and frame - last["arr_frame"] < 4)
    draw_panel(canvas, L["panel"], view, world, frame, 1.0 if flash else 0.0)


class Writer:
    def __init__(self, path: Path, size, audio: Path):
        self.proc = subprocess.Popen(
            ["nice", "-n", "10", "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "-", "-i", str(audio),
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(path)],
            stdin=subprocess.PIPE)
        self.frames = 0

    def write(self, canvas):
        self.proc.stdin.write(pygame.image.tobytes(canvas, "RGB"))
        self.frames += 1

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")


def _wav(path: Path, samples) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(samples.tobytes())


def summary(meta: dict, decisions: list) -> dict:
    lat = sorted(d["rtt_ms"] for d in decisions if d.get("rtt_ms"))
    r = meta["result"]
    return {"progress": r["progress"], "score": r["score"], "kills": r["kills"], "seconds": r["seconds"],
            "decisions": len(lat), "lat_mean": sum(lat) / len(lat) if lat else 0,
            "lat_p95": lat[int(0.95 * (len(lat) - 1))] if lat else 0,
            "fallback": 100 * sum(d["tag"] == "FALLBACK" for d in decisions) / max(1, len(decisions))}


def render(run: Path, out: Path, layout: str = "landscape", segments: list | None = None,
           title_s: float = 3.0, outro_s: float = 5.0, shots: dict | None = None, outro_lines: list | None = None,
           clips: list | None = None) -> Path:
    """clips: [(start_frame, end_frame, speed, caption)], rendered in order; speed 0.5 = slow-motion replay
    (each frame shown twice, music only). `segments` = clips at normal speed without captions."""
    import numpy as np

    pygame.init()
    meta = json.loads(run.with_suffix(".meta.json").read_text())
    decisions = [json.loads(l) for l in open(run.with_suffix(".jsonl"))]
    L = LAYOUTS[layout]
    canvas = pygame.Surface(L["size"])
    game_surf = pygame.Surface((256, 240))
    total = meta["frames"]
    clips = clips or [(a, b, 1.0, None) for a, b in (segments or [(0, total)])]
    s = summary(meta, decisions)
    full = render_track(total, meta["events"])
    music = render_track(total * 3, [], music_vol=0.6)
    pieces, cursor = [np.zeros((int(title_s * SR), 2), np.int16)], 0
    for a, b, speed, _ in clips:
        if speed == 1.0:
            pieces.append(full[int(a / FPS * SR):int(b / FPS * SR)])
        else:
            n = int((b - a) / FPS / speed * SR)
            pieces.append(music[cursor:cursor + n])
            cursor += n
    pieces.append(np.zeros((int(outro_s * SR), 2), np.int16))
    tmp = Path(tempfile.mkdtemp())
    _wav(tmp / "audio.wav", np.concatenate(pieces))
    writer = Writer(out, L["size"], tmp / "audio.wav")
    subtitle = "JUGADO EN TIEMPO REAL POR SISTEMA 1" if meta["mode"] == "realtime" else "JUGADO POR SISTEMA 1 (POR TURNOS)"
    title = [(GAME_NAME, 7, BRIGHT), ("", 2, BG), (subtitle, 3, AMBER),
             ("QWEN3.5-4B LOCAL · DECISIONES TIPADAS · 0 TOKENS GENERADOS", 2, DIM), ("", 2, BG), ("@abxda", 3, AMBER)]
    for i in range(int(title_s * FPS)):
        card(canvas, title, i / FPS)
        writer.write(canvas)
    for a, b, speed, caption in clips:
        view = RunView(decisions, "jev-local")

        def on_frame(world, applied, current):
            f = world.frame
            view.advance(f)
            if a <= f < b:
                compose(canvas, layout, world, view, f, game_surf)
                if caption:
                    g = L["game"]
                    band = pygame.Surface((g.width, 64), pygame.SRCALPHA)
                    band.fill((8, 6, 2, 200))
                    canvas.blit(band, (g.x, g.y + 150))
                    font.draw(canvas, caption, g.x + 16, g.y + 158, BRIGHT, 3)
                    font.draw(canvas, f"REPETICIÓN {speed:g}×", g.x + 16, g.y + 190, AMBER, 2)
                for _ in range(int(round(1 / speed))):
                    writer.write(canvas)
                if shots and f in shots and speed == 1.0:
                    pygame.image.save(canvas, shots[f])

        replay(meta, on_frame)
    lines = outro_lines or [
        ("RESULTADO", 6, BRIGHT), ("", 2, BG),
        (f"AVANCE {s['progress']:.0f}%   PUNTAJE {s['score']}   BAJAS {s['kills']}", 3, AMBER),
        (f"{s['decisions']} DECISIONES · LATENCIA MEDIA {s['lat_mean']:.0f} MS · P95 {s['lat_p95']:.0f} MS", 2, AMBER),
        (f"FALLBACK {s['fallback']:.0f}% · 0 TOKENS GENERADOS", 2, AMBER), ("", 2, BG),
        ("EL FORMATO ESTÁ GARANTIZADO; LA CORRECCIÓN NO.", 2, DIM), ("", 2, BG), ("@abxda", 3, AMBER)]
    for i in range(int(outro_s * FPS)):
        card(canvas, lines, 1.0)
        writer.write(canvas)
    writer.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("out")
    ap.add_argument("--layout", default="landscape", choices=list(LAYOUTS))
    ap.add_argument("--segments", default="", help="a:b,c:d frame ranges")
    args = ap.parse_args()
    segs = [tuple(int(v) for v in p.split(":")) for p in args.segments.split(",") if p] or None
    print(render(Path(args.run), Path(args.out), args.layout, segs))

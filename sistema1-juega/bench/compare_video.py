"""Stacked comparison video (1080x1920): the same level (seed 1987), three System One models without
thinking, replayed in sync from their logs. Row = game (x2) + live mini panel (latency, tag, probabilities,
JSON flow). A model that loses freezes with its result while the others keep playing.

  .venv/bin/python -m bench.compare_video
      -> video/comparacion_modelos_vertical_1080x1920.mp4 and video/comparacion_modelos_horizontal_1920x1080.mp4
"""

from __future__ import annotations

import json
import os
import statistics as st
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from agent.modes import apply  # noqa: E402
from bench.render_video import Writer, _wav, card, model_label  # noqa: E402
from game import font  # noqa: E402
from game.audio import SR, render_track  # noqa: E402
from game.core import DIR_VEC, FPS, IDLE, Action, World  # noqa: E402
from game.render import draw_world, upscale  # noqa: E402
from hud.panel import AMBER, BG, BRIGHT, DIM, FAINT, RED, TAG_COLOR, TAG_TEXT, RunView, draw_json_stream, watermark  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 1920
ORDER = ["qwen35-4b", "gemma4-e4b", "qwen35-9b"]
MOVE = {1: "AVANZA", -1: "RETROCEDE", 0: "QUIETO"}


def run_dir(key: str) -> Path:
    return ROOT / "runs" / ("bench" if key == "qwen35-4b" else f"models/{key}") / "realtime"


def best_run(key: str) -> Path:
    metas = sorted(run_dir(key).glob("*.meta.json"))
    best = max(metas, key=lambda p: (json.loads(p.read_text())["result"]["progress"], json.loads(p.read_text())["result"]["score"]))
    return best.with_name(best.name.replace(".meta.json", ""))


class Player:
    """Step-by-step replay of one logged run (same frame contract as agent.modes.replay)."""

    def __init__(self, run: Path):
        self.meta = json.loads(run.with_suffix(".meta.json").read_text())
        self.decisions = [json.loads(l) for l in open(run.with_suffix(".jsonl"))]
        self.world = World(self.meta["seed"])
        self.tl, self.k, self.current = self.meta["timeline"], 0, IDLE
        self.view = RunView(self.decisions, model_label(self.meta))
        self.label = model_label(self.meta)
        self.done = False
        self.frozen = None

    def step(self):
        w = self.world
        if self.done or w.over or w.frame >= self.meta["frames"]:
            self.done = True
            return
        while self.k < len(self.tl) and self.tl[self.k][0] == w.frame:
            rearm = self.tl[self.k][2] if len(self.tl[self.k]) > 2 else True
            self.current = apply(w, Action(**self.tl[self.k][1])) if rearm else Action(**self.tl[self.k][1])
            self.k += 1
        self.view.advance(w.frame)
        w.step(self.current)


def _bar(s, x, y, w, h, p, label, win):
    s.fill(FAINT, (x, y, w, h))
    s.fill(AMBER if win else DIM, (x, y, int(w * max(0.0, min(1.0, p))), h))
    lw = font.width(label, 2)
    s.fill(BG, (x + 3, y + 3, lw + 8, h - 6))                 # own dark plate: label always readable
    font.draw(s, label, x + 7, y + (h - 18) // 2 + 2, BRIGHT if win else AMBER, 2)
    txt = f"{p:.2f}"
    tw = font.width(txt, 2)
    s.fill(BG, (x + w - tw - 10, y + 3, tw + 8, h - 6))
    font.draw(s, txt, x + w - tw - 6, y + (h - 18) // 2 + 2, BRIGHT if win else AMBER, 2)


def draw_cell(canvas, p: Player, cell: pygame.Rect, game_surf, horizontal: bool):
    """One model: amber header band with its name, the game (x2) and a live mini panel."""
    canvas.fill((10, 17, 26), cell)
    pygame.draw.rect(canvas, (62, 80, 91), cell, 2)
    w = p.world
    canvas.fill(AMBER, (cell.x, cell.y, cell.width, 52))          # model header band: who is playing
    name_sc = 4 if font.width(p.label, 4) < cell.width - (300 if not horizontal else 40) else 3
    font.draw(canvas, p.label, cell.x + 14, cell.y + (8 if name_sc == 4 else 14), BG, name_sc)
    prog = f"AVANCE {w.progress():.0f}%"
    if horizontal:
        game = pygame.Rect(cell.x + (cell.width - 512) // 2, cell.y + 64, 512, 480)
        font.draw(canvas, prog, cell.right - font.width(prog, 2) - 12, cell.y + 60 + 482, AMBER, 2)
    else:
        game = pygame.Rect(cell.x + 10, cell.y + 60, 512, 480)
        font.draw(canvas, prog, cell.right - font.width(prog, 3) - 14, cell.y + 14, BG, 3)
    if not p.done or p.frozen is None:
        draw_world(game_surf, w)
        frame_img = upscale(game_surf, 2, crt=True)
        if p.done:
            p.frozen = frame_img.copy()   # the game-over frame stays on screen
    else:
        frame_img = p.frozen
    canvas.blit(frame_img, game.topleft)
    if p.done:
        shade = pygame.Surface(game.size, pygame.SRCALPHA)
        shade.fill((8, 6, 2, 140))
        canvas.blit(shade, game.topleft)
        font.draw(canvas, "GAME OVER", game.x + (512 - font.width("GAME OVER", 5)) // 2, game.y + 170, RED, 5)
        font.draw(canvas, prog, game.x + (512 - font.width(prog, 3)) // 2, game.y + 250, BRIGHT, 3)
        sec = f"{p.meta['result']['seconds']:.1f} S DE JUEGO"
        font.draw(canvas, sec, game.x + (512 - font.width(sec, 2)) // 2, game.y + 296, AMBER, 2)
    watermark(canvas, game.right - font.width("@abxda", 2) - 8, game.bottom - 26, 2)
    # mini panel
    if horizontal:
        x, y, pw, bottom = cell.x + 14, game.bottom + 30, cell.width - 28, cell.bottom - 12
    else:
        x, y, pw, bottom = game.right + 16, cell.y + 60, cell.right - game.right - 30, cell.bottom - 14
    m = p.view.metrics(w.frame)
    d = p.view.last
    font.draw(canvas, f"LATENCIA {m['lat_now']:.0f} MS", x, y, BRIGHT, 2)
    font.draw(canvas, f"MEDIA {m['lat_mean']:.0f} MS · {m['n']} DECISIONES", x, y + 24, DIM, 2)
    y += 56
    if d is None:
        font.draw(canvas, "ESPERANDO...", x, y, DIM, 2)
        return
    a = d["raw"]["answers"]
    act = d["action"]
    font.draw(canvas, TAG_TEXT[d["tag"]], x, y, TAG_COLOR[d["tag"]], 3)
    font.draw(canvas, f"{MOVE[act['move']]} {act['aim']}{' DISP' if act['shoot'] else ''}{' SALTA' if act['jump'] else ''}",
              x + (0 if not horizontal else 200), y + (34 if not horizontal else 6), AMBER, 2)
    y += 64 if not horizontal else 40
    mv = a["move"]
    bars = [(mv["probabilities"]["avanzar"], "AVANZAR", mv["choice"] == "avanzar"),
            (a["jump"]["noul"], "SALTAR", a["jump"]["noul"] >= 0.5),
            (a["shoot"]["noul"], "DISPARAR", a["shoot"]["noul"] >= 0.5),
            (a["aim"]["probabilities"][a["aim"]["choice"]], f"APUNTAR {a['aim']['choice']}", True)]
    for pr, lab, win in bars:
        _bar(canvas, x, y, pw, 30, pr, lab, win)
        y += 36
    y += 8
    if bottom - y > 40:
        draw_json_stream(canvas, pygame.Rect(x, y, pw, bottom - y), p.view, w.frame)


def outro_lines(summary: list) -> list:
    lines = [("¿QUIÉN DECIDIÓ MEJOR?", 5, BRIGHT), ("", 2, BG)]
    for s in summary:
        lines.append((s["label"], 3, AMBER))
        lines.append((f"AVANCE {s['progress']:.0f}%  ·  {s['lat']:.0f} MS/DECISIÓN  ·  EXACTITUD {s['acc']:.0f}%", 2, BRIGHT))
        lines.append(("", 1, BG))
    lines += [("MISMA PARTIDA · SIN PENSAMIENTO · 0 TOKENS GENERADOS", 2, DIM),
              ("EXACTITUD = 554 DECISIONES ETIQUETADAS, SIN PRESIÓN DE TIEMPO", 2, DIM), ("", 2, BG), ("@abxda", 3, AMBER)]
    return lines


def main():
    pygame.init()
    keys = [k for k in ORDER if list(run_dir(k).glob("*.meta.json"))]
    players = [Player(best_run(k)) for k in keys]
    summary = []
    for k, p in zip(keys, players):
        lat = [d["rtt_ms"] for d in p.decisions if d.get("rtt_ms")]
        ev = ROOT / "runs" / "models" / k / "eval.json"
        acc = 100 * json.loads(ev.read_text())["pooled"]["raw"]["accuracy"] if ev.exists() else float("nan")
        summary.append({"key": k, "label": p.label, "progress": p.meta["result"]["progress"], "lat": st.fmean(lat), "acc": acc,
                        "run": p.meta.get("variant"), "frames": p.meta["frames"]})
    total = max(p.meta["frames"] for p in players) + 2 * FPS
    title_s, outro_s = 3.0, 7.0
    music = render_track(int((title_s + total / FPS + outro_s) * FPS), [], music_vol=0.7)
    tmp = Path(tempfile.mkdtemp())
    _wav(tmp / "audio.wav", music)
    sizes = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
    names = {"vertical": "comparacion_modelos_vertical_1080x1920.mp4", "horizontal": "comparacion_modelos_horizontal_1920x1080.mp4"}
    writers = {k: Writer(ROOT / "video" / names[k], sizes[k], tmp / "audio.wav") for k in sizes}
    canvases = {k: pygame.Surface(sizes[k]) for k in sizes}
    title = [("¿QUIÉN DECIDE MEJOR?", 5, BRIGHT), ("", 2, BG), ("ÁMBAR REFLEX · SISTEMA 1 SIN PENSAMIENTO", 2, AMBER), ("", 2, BG)]
    title += [(s["label"], 3, AMBER) for s in summary] + [("", 2, BG), ("MISMA PARTIDA (SEMILLA 1987) · MISMA POLÍTICA", 2, DIM), ("@abxda", 3, AMBER)]
    for i in range(int(title_s * FPS)):
        for k in sizes:
            card(canvases[k], title, i / FPS)
            writers[k].write(canvases[k])
    game_surf = pygame.Surface((256, 240))
    n = len(players)
    for f in range(total):
        for p in players:
            p.step()
        for k, (cw, ch) in sizes.items():
            c = canvases[k]
            c.fill((6, 10, 14))
            font.draw(c, "¿QUIÉN DECIDE MEJOR?", 32, 28 if k == "horizontal" else 40, BRIGHT, 4 if k == "horizontal" else 5)
            sub = "SISTEMA 1 · SIN PENSAMIENTO · MISMA PARTIDA"
            font.draw(c, sub, 34 if k == "vertical" else 32 + font.width("¿QUIÉN DECIDE MEJOR?  ", 4),
                      104 if k == "vertical" else 40, AMBER, 2)
            clock = f"T = {f / FPS:5.1f} S"
            font.draw(c, clock, cw - 32 - font.width(clock, 2), 104 if k == "vertical" else 40, DIM, 2)
            for i, p in enumerate(players):
                if k == "vertical":
                    cell = pygame.Rect(16, 150 + i * 580, cw - 32, 560)
                else:
                    colw = (cw - 32 - 16 * (n - 1)) // n
                    cell = pygame.Rect(16 + i * (colw + 16), 84, colw, ch - 84 - 16)
                draw_cell(c, p, cell, game_surf, k == "horizontal")
            watermark(c, cw - font.width("@abxda", 3) - 30, ch - 34, 3)
            writers[k].write(c)
    lines = outro_lines(sorted(summary, key=lambda s: -s["progress"]))
    for i in range(int(outro_s * FPS)):
        for k in sizes:
            card(canvases[k], lines, 1.0)
            writers[k].write(canvases[k])
    for wtr in writers.values():
        wtr.close()
    (ROOT / "video" / "comparacion_modelos.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

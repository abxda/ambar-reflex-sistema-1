"""Amber terminal panel + decision overlay. Everything shown comes from the run log (raw server
answers and measured latencies) at the frame it actually arrived."""

from __future__ import annotations

import math
import statistics

import pygame

from game import font
from game.core import DIR_VEC, DIRS, FPS

AMBER = (255, 176, 0)
DIM = (184, 137, 65)
FAINT = (52, 36, 0)
BRIGHT = (255, 224, 140)
RED = (255, 84, 60)
ORANGE = (255, 136, 32)
BG = (8, 6, 2)
TAG_COLOR = {"ACTUA": BRIGHT, "DUDA": ORANGE, "FALLBACK": RED}
TAG_TEXT = {"ACTUA": "ACTÚA", "DUDA": "DUDA", "FALLBACK": "FALLBACK"}
MOVE_TXT = {"avanzar": "AVANZAR", "retroceder": "RETROCEDER", "quieto": "QUIETO"}
WATERMARK = "@abxda"


def watermark(surface: pygame.Surface, x: int, y: int, scale: int = 4, alpha: int = 102) -> None:
    font.draw(surface, WATERMARK, x, y, (255, 255, 255), scale, alpha)


class RunView:
    """Per-frame view of a logged run: which decisions have arrived, and running metrics."""

    def __init__(self, decisions: list, model: str):
        self.decs = sorted([d for d in decisions if "raw" in d], key=lambda d: d["arr_frame"])
        self.model = model
        self.k = 0
        self.arrived: list = []

    def advance(self, frame: int) -> None:
        while self.k < len(self.decs) and self.decs[self.k]["arr_frame"] <= frame:
            self.arrived.append(self.decs[self.k])
            self.k += 1

    @property
    def last(self):
        return self.arrived[-1] if self.arrived else None

    def metrics(self, frame: int) -> dict:
        a = self.arrived
        lat = [d["rtt_ms"] for d in a if d.get("rtt_ms")]
        n = len(a)
        return {
            "n": n,
            "lat_now": lat[-1] if lat else 0.0,
            "lat_mean": statistics.fmean(lat) if lat else 0.0,
            "lat_p95": sorted(lat)[int(0.95 * (len(lat) - 1))] if lat else 0.0,
            "dps": n / max(frame / FPS, 1e-6) if frame else 0.0,
            "fallback": 100.0 * sum(d["tag"] == "FALLBACK" for d in a) / n if n else 0.0,
            "duda": 100.0 * sum(d["tag"] == "DUDA" for d in a) / n if n else 0.0,
            "lat_series": lat[-48:],
        }


def _bar(s, x, y, w, h, p, color, label, value_txt, sc=2, win=False):
    s.fill(FAINT, (x, y, w, h))
    s.fill(color if win else DIM, (x, y, int(w * max(0.0, min(1.0, p))), h))
    for threshold in (.5, .9):
        s.fill(BG, (x + int(w * threshold), y, 1, 4))
        s.fill(BG, (x + int(w * threshold), y + h - 4, 1, 4))
    if win:
        pygame.draw.rect(s, BRIGHT, (x, y, w, h), 1)
    s.fill(BG, (x + 3, y + 3, font.width(label, sc) + 6, h - 6))
    font.draw(s, label, x + 6, y + (h - 9 * sc) // 2 + sc, BRIGHT if win else AMBER, sc)
    tw = font.width(value_txt, sc)
    tx = x + w - tw - 6
    s.fill(BG, (tx - 4, y + 3, tw + 8, h - 6))  # own dark plate: always readable over the fill
    font.draw(s, value_txt, tx, y + (h - 9 * sc) // 2 + sc, BRIGHT if win else AMBER, sc)


def draw_panel(s: pygame.Surface, rect: pygame.Rect, view: RunView, world, frame: int, flash: float) -> None:
    x0, y0, W, H = rect
    s.fill(BG, rect)
    pygame.draw.rect(s, AMBER if flash > 0 else DIM, rect, 3)
    pad = 20
    x, y = x0 + pad, y0 + pad
    font.draw(s, "SISTEMA 1 JUEGA", x, y, BRIGHT, 4)
    y += 44
    font.draw(s, f"MODELO {view.model}  ·  QWEN3.5-4B Q8 LOCAL", x, y, DIM, 2)
    y += 24
    font.draw(s, "0 TOKENS GENERADOS  ·  1 PETICIÓN = 6 PREGUNTAS", x, y, AMBER, 2)
    y += 34
    d = view.last
    bw = W - 2 * pad
    if d is None:
        font.draw(s, "ESPERANDO PRIMERA DECISIÓN...", x, y, AMBER, 2)
        watermark(s, x0 + W - font.width(WATERMARK, 3) - pad, y0 + H - 40, 3)
        return
    ans = d["raw"]["answers"]
    tag = d["tag"]
    # move
    font.draw(s, "MOVER", x, y, BRIGHT, 2)
    font.draw(s, f"CONF {ans['move']['confidence']:.2f}", x + bw - font.width("CONF 0.00", 2), y, AMBER, 2)
    y += 22
    col = (bw - 12) // 3
    for i, key in enumerate(("avanzar", "retroceder", "quieto")):
        p = ans["move"]["probabilities"][key]
        _bar(s, x + i * (col + 6), y, col, 30, p, AMBER, MOVE_TXT[key][:6], f"{p:.2f}", 2, key == ans["move"]["choice"])
    y += 40
    # nouls
    for key, label in (("jump", "SALTAR"), ("crouch", "AGACHARSE"), ("shoot", "DISPARAR")):
        p = ans[key]["noul"]
        _bar(s, x, y, bw, 28, p, AMBER, f"{label}  P(SÍ)", f"{p:.2f}", 2, p >= 0.5)
        y += 34
    y += 6
    # aim rose + danger gauge side by side
    rose_r = 54 if H < 900 else 80
    cx, cy = x + rose_r + 24, y + rose_r + 40
    font.draw(s, "APUNTAR", x, y, BRIGHT, 2)
    probs = ans["aim"]["probabilities"]
    best = ans["aim"]["choice"]
    pygame.draw.circle(s, FAINT, (cx, cy), rose_r, 1)
    for dname in DIRS:
        dx, dy = DIR_VEC[dname]
        p = probs[dname]
        L = 14 + (rose_r - 14) * p
        c = BRIGHT if dname == best else DIM
        pygame.draw.line(s, c, (cx, cy), (cx + dx * L, cy + dy * L), 6 if dname == best else 3)
        tx, ty = cx + dx * (rose_r + 14), cy + dy * (rose_r + 14)
        font.draw(s, dname, int(tx - font.width(dname, 2) / 2), int(ty - 7), AMBER if dname == best else DIM, 2)
    font.draw(s, f"{best} {probs[best]:.2f}", cx - 30, cy + rose_r + 28, AMBER, 2)
    # danger gauge
    gx, gy, gr = x + bw * 3 // 4, cy + 20, rose_r
    font.draw(s, "PELIGRO", gx - gr, y, BRIGHT, 2)
    danger = d["danger"]
    for i in range(31):
        a = math.pi * (1 - i / 30)
        c = AMBER if i / 30 <= danger else FAINT
        if i > 20:
            c = RED if i / 30 <= danger else (60, 16, 8)
        pygame.draw.line(s, c, (gx + math.cos(a) * (gr - 16), gy - math.sin(a) * (gr - 16)),
                         (gx + math.cos(a) * gr, gy - math.sin(a) * gr), 4)
    a = math.pi * (1 - danger)
    pygame.draw.line(s, BRIGHT, (gx, gy), (gx + math.cos(a) * (gr - 6), gy - math.sin(a) * (gr - 6)), 4)
    pygame.draw.circle(s, BRIGHT, (gx, gy), 6)
    font.draw(s, f"{danger:.2f}", gx - 24, gy + 14, AMBER, 2)
    font.draw(s, "SEGURO / CRÍTICO", gx - 90, gy + 38, DIM, 2)
    y = cy + rose_r + 60
    # tag
    font.draw(s, TAG_TEXT[tag], x, y, TAG_COLOR[tag], 3)
    font.draw(s, f"CONF. CALIBRADA MÍN {d['conf']:.2f}", x + 230, y + 6, AMBER, 2)
    y += 40
    # metrics
    m = view.metrics(frame)
    rows = [("PUNTAJE", f"{world.score}"), ("VIDAS", f"{max(0, world.lives)}"), ("NIVEL", f"{world.progress():.0f}%"),
            ("DECISIONES", f"{m['n']}"), ("LAT ACTUAL", f"{m['lat_now']:.0f} MS"), ("LAT MEDIA", f"{m['lat_mean']:.0f} MS"),
            ("LAT P95", f"{m['lat_p95']:.0f} MS"), ("DECISIONES/S", f"{m['dps']:.1f}"), ("FALLBACK", f"{m['fallback']:.0f}%")]
    cw = bw // 3
    for i, (k, v) in enumerate(rows):
        rx, ry = x + (i % 3) * cw, y + (i // 3) * 42
        font.draw(s, k, rx, ry, DIM, 2)
        font.draw(s, v, rx, ry + 20, BRIGHT, 2)
    y += 3 * 42 + 6
    # latency sparkline
    series = m["lat_series"]
    sh = 32 if H < 900 else 50
    font.draw(s, "LATENCIA (MS)", x, y, DIM, 2)
    y += 20
    s.fill(FAINT, (x, y, bw, sh))
    if len(series) > 1:
        hi = max(max(series), 1.0)
        pts = [(x + i * (bw - 1) / (len(series) - 1), y + sh - 2 - (v / hi) * (sh - 6)) for i, v in enumerate(series)]
        pygame.draw.lines(s, AMBER, False, pts, 2)
        font.draw(s, f"{hi:.0f}", x + bw - font.width(f"{hi:.0f}", 2) - 4, y + 3, BRIGHT, 2)
    y += sh + 12
    # scrolling log
    font.draw(s, "LOG", x, y, DIM, 2)
    y += 22
    lines = max(0, (y0 + H - 50 - y) // 20)
    for rec in (view.arrived[-lines:] if lines else []):
        act = rec["action"]
        mv = {1: "AVZ", -1: "RET", 0: "QTO"}[act["move"]]
        parts = f"{rec['arr_frame'] / FPS:6.1f}S {mv} {act['aim']:<2} {'DISP' if act['shoot'] else '----'} " \
                f"{'SALTA' if act['jump'] else '-----'} {'AGACH' if act['crouch'] else '-----'} " \
                f"C{rec['conf']:.2f} {TAG_TEXT[rec['tag']]}"
        font.draw(s, parts, x, y, TAG_COLOR[rec["tag"]], 2 if bw > 700 else 1)
        y += 20
    watermark(s, x0 + W - font.width(WATERMARK, 3) - pad, y0 + H - 40, 3)


def draw_overlay(s: pygame.Surface, game_rect: pygame.Rect, world, view: RunView, frame: int, scale: int = 4) -> None:
    """Fan of 8 aim arrows (opacity = server probability) + move arrow, fading over 0.4 s."""
    d = view.last
    if d is None or world.dead_timer:
        return
    age = frame - d["arr_frame"]
    fade = max(0.0, 1.0 - age / (0.4 * FPS))
    if fade <= 0:
        return
    ans = d["raw"]["answers"]
    ox = game_rect.x + (world.px - world.cam) * scale
    oy = game_rect.y + (world.py - 14) * scale
    layer = pygame.Surface(game_rect.size, pygame.SRCALPHA)
    lx, ly = ox - game_rect.x, oy - game_rect.y
    probs = ans["aim"]["probabilities"]
    for dname in DIRS:
        dx, dy = DIR_VEC[dname]
        p = probs[dname]
        alpha = int(255 * p * fade)
        if alpha < 6:
            continue
        L = 120
        ex, ey = lx + dx * L, ly + dy * L
        w = 8 if dname == ans["aim"]["choice"] else 5
        pygame.draw.line(layer, (*AMBER, alpha), (lx + dx * 40, ly + dy * 40), (ex, ey), w)
        hx, hy = -dy, dx
        pygame.draw.polygon(layer, (*AMBER, alpha), [(ex + dx * 18, ey + dy * 18), (ex + hx * 12, ey + hy * 12), (ex - hx * 12, ey - hy * 12)])
    mp = ans["move"]["probabilities"]
    for key, sgn in (("avanzar", 1), ("retroceder", -1)):
        alpha = int(255 * mp[key] * fade)
        if alpha < 6:
            continue
        y = ly - 150
        pygame.draw.line(layer, (*BRIGHT, alpha), (lx, y), (lx + sgn * 90, y), 8)
        pygame.draw.polygon(layer, (*BRIGHT, alpha), [(lx + sgn * 112, y), (lx + sgn * 88, y - 16), (lx + sgn * 88, y + 16)])
    a = int(255 * mp["quieto"] * fade)
    if a >= 6:
        pygame.draw.rect(layer, (*BRIGHT, a), (lx - 10, ly - 160, 20, 20), 4)
    s.blit(layer, game_rect.topleft)

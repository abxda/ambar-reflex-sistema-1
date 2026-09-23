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
    badge = f" MODELO: {view.model} · SIN PENSAMIENTO "
    s.fill(AMBER, (x - 2, y - 3, font.width(badge, 2) + 4, 24))
    font.draw(s, badge, x, y, BG, 2)
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
    # live JSON stream of the real /v1/systemone calls (replaces the plain text log; keeps its data)
    draw_json_stream(s, pygame.Rect(x, y, bw, y0 + H - 46 - y), view, frame)
    watermark(s, x0 + W - font.width(WATERMARK, 3) - pad, y0 + H - 40, 3)


JSON_KEY, JSON_STR, JSON_NUM, JSON_PUNCT = BRIGHT, AMBER, (108, 165, 175), DIM
SCROLL_FRAMES = 10  # a new call slides in over 1/6 s


def _json_lines(rec: dict, max_chars: int) -> list:
    """One call as short, colored JSON lines: [(text, color), ...] per line. Values are the logged ones
    (request `state` and the server's raw answers), rounded to 2 decimals for width only."""
    a = rec["raw"]["answers"]
    act = rec["action"]
    mv = {1: "AVZ", -1: "RET", 0: "QTO"}[act["move"]]
    what = " ".join(t for t, on in ((mv, True), (act["aim"], True), ("DISP", act["shoot"]),
                                    ("SALTA", act["jump"]), ("AGACH", act["crouch"])) if on)
    state = rec.get("state", "")
    usage = rec["raw"].get("usage", {})

    def kv(k, v, last=False):
        seg = [(f'"{k}"', JSON_KEY), (": ", JSON_PUNCT)]
        if isinstance(v, str):
            seg.append((f'"{v}"', JSON_STR))
        elif isinstance(v, dict):
            seg.append(("{", JSON_PUNCT))
            items = list(v.items())
            for i, (kk, vv) in enumerate(items):
                seg += kv(kk, vv, i == len(items) - 1)
            seg.append(("}", JSON_PUNCT))
        else:
            seg.append((f"{v:.2f}" if isinstance(v, float) else str(v), JSON_NUM))
        if not last:
            seg.append((", ", JSON_PUNCT))
        return seg

    c = lambda k: {"choice": a[k]["choice"], "confidence": float(a[k]["confidence"])}
    n = lambda k: {"noul": float(a[k]["noul"])}
    tag = rec["tag"]
    head = f"→ {rec['req_frame'] / FPS:4.1f}S POST "
    room = max_chars - len(head) - 13
    state_txt = state if len(state) <= room else state[: max(4, room - 1)] + "…"
    return [
        [],  # separator above each call
        [(head, DIM), ("{", JSON_PUNCT)] + kv("state", state_txt, True) + [("}", JSON_PUNCT)],
        [(f"← {rec['rtt_ms']:.0f} MS · 200 OK · ", DIM), (f"{TAG_TEXT[tag]} ", TAG_COLOR[tag]), (what, TAG_COLOR[tag])],
        [("{", JSON_PUNCT)] + kv("move", c("move")),
        [(" ", JSON_PUNCT)] + kv("aim", c("aim")),
        [(" ", JSON_PUNCT)] + kv("jump", n("jump")) + kv("crouch", n("crouch")),
        [(" ", JSON_PUNCT)] + kv("shoot", n("shoot")) + kv("danger", {"score": float(a["danger"]["score"])}),
        [(" ", JSON_PUNCT)] + kv("usage", {"input_tokens": usage.get("input_tokens", 0),
                                           "output_tokens": usage.get("output_tokens", 0)}, True) + [("}", JSON_PUNCT)],
    ]


def _json_lines_compact(rec: dict, max_chars: int) -> list:
    """Two lines per call for short boxes (vertical layout): request state, then response values."""
    a = rec["raw"]["answers"]
    tag = rec["tag"]
    head = f"→ {rec['req_frame'] / FPS:4.1f}S "
    room = max_chars - len(head) - 13
    st = rec.get("state", "")
    st = st if len(st) <= room else st[: max(4, room - 1)] + "…"
    num = lambda v: (f"{float(v):.2f}", JSON_NUM)
    resp = [(f"← {rec['rtt_ms']:.0f}MS ", TAG_COLOR[tag]), ("{", JSON_PUNCT)]
    for i, (k, v) in enumerate((("move", a["move"]["choice"]), ("aim", a["aim"]["choice"]), ("jump", a["jump"]["noul"]),
                                ("crouch", a["crouch"]["noul"]), ("shoot", a["shoot"]["noul"]))):
        resp += [(f'"{k}"', JSON_KEY), (":", JSON_PUNCT)]
        resp.append((f'"{v}"', JSON_STR) if isinstance(v, str) else num(v))
        resp.append((",", JSON_PUNCT) if i < 4 else ("}", JSON_PUNCT))
    return [[(head, DIM), ("{", JSON_PUNCT), ('"state"', JSON_KEY), (": ", JSON_PUNCT), (f'"{st}"', JSON_STR),
             ("}", JSON_PUNCT)], resp]


def draw_json_stream(s: pygame.Surface, rect: pygame.Rect, view: RunView, frame: int) -> None:
    """Scrolling feed of the last calls, newest at the bottom; slides up when a response arrives."""
    sc = 2 if rect.width >= 600 else 1
    lh = 10 * sc
    font.draw(s, "FLUJO /v1/systemone", rect.x, rect.y, BRIGHT, sc)
    sub_x = rect.x + font.width("FLUJO /v1/systemone  ", sc)
    if sub_x + font.width("JSON REAL · PETICIÓN → RESPUESTA", sc) <= rect.right:
        font.draw(s, "JSON REAL · PETICIÓN → RESPUESTA", sub_x, rect.y, DIM, sc)
    elif sub_x + font.width("JSON REAL", sc) <= rect.right:
        font.draw(s, "JSON REAL", sub_x, rect.y, DIM, sc)
    box = pygame.Rect(rect.x, rect.y + lh + 6, rect.width, rect.height - lh - 6)
    if box.height < lh * 2:
        return
    s.fill((6, 10, 14), box)
    pygame.draw.rect(s, FAINT, box, 1)
    inner = box.inflate(-12, -8)
    max_chars = inner.width // (6 * sc)
    recent = view.arrived[-4:]
    if not recent:
        font.draw(s, "ESPERANDO PRIMERA LLAMADA...", inner.x, inner.y, DIM, sc)
        return
    fmt = _json_lines if inner.height // lh >= 6 else _json_lines_compact
    lines = [ln for rec in recent for ln in fmt(rec, max_chars)]
    last_block = len(fmt(recent[-1], max_chars))
    t = min(1.0, (frame - recent[-1]["arr_frame"]) / SCROLL_FRAMES)
    lag = (1 - (1 - t) ** 3) * last_block - last_block   # -last_block .. 0 lines: new call slides up
    clip = s.get_clip()
    s.set_clip(inner)
    n = len(lines)
    for k, segs in enumerate(lines):
        # bottom-anchored: the newest line rests on the bottom edge once the slide finishes
        yy = int(inner.bottom - (n - k) * lh - lag * lh)
        if yy + lh < inner.top or yy > inner.bottom:
            continue
        xx = inner.x
        for text, color in segs:
            room = inner.right - xx
            if room <= 0:
                break
            xx = font.draw(s, text[: max(0, room // (6 * sc))], xx, yy, color, sc)
    s.set_clip(clip)
    # a fresh response briefly lights the frame
    if frame - recent[-1]["arr_frame"] < 6:
        pygame.draw.rect(s, TAG_COLOR[recent[-1]["tag"]], box, 2)


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

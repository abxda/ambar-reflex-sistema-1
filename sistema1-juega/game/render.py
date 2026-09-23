"""Draw the world at 256x240 (8-bit look) and upscale x4 with nearest-neighbor (+ optional CRT)."""

from __future__ import annotations

import math

import pygame

from . import font
from . import level as L
from . import sprites as S
from .core import DIR_VEC, World

THEMES = {  # sky bands top->bottom, far silhouettes, mid structures, ground top, ground body, ground dither
    "REFINERIA": ([(252, 188, 116), (240, 140, 80), (200, 92, 64), (136, 60, 72)], (112, 52, 64), (72, 40, 56),
                  (236, 180, 100), (168, 112, 56), (132, 84, 40)),
    "CANON": ([(120, 88, 180), (160, 96, 168), (208, 112, 128), (236, 152, 112)], (84, 48, 104), (120, 56, 64),
              (212, 140, 96), (152, 80, 56), (112, 56, 44)),
    "REACTOR": ([(8, 24, 40), (12, 40, 56), (16, 56, 72), (20, 72, 80)], (24, 48, 64), (32, 72, 88),
                (120, 200, 200), (48, 88, 104), (32, 64, 80)),
    "NUCLEO": ([(24, 8, 32), (40, 12, 48), (64, 16, 56), (96, 24, 56)], (56, 20, 64), (80, 28, 72),
               (200, 120, 220), (72, 40, 96), (52, 28, 72)),
}


def _hash(n: int) -> float:
    n = (n * 374761393 + 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


def _background(s: pygame.Surface, w: World, theme):
    sky, far, mid = theme[0], theme[1], theme[2]
    band = L.SCREEN_H // len(sky) // 2
    for i, c in enumerate(sky):
        s.fill(c, (0, i * band, L.SCREEN_W, band + 1))
    s.fill(sky[-1], (0, len(sky) * band, L.SCREEN_W, L.SCREEN_H))
    # far silhouettes (parallax 0.2): mesas / ridges
    off = w.cam * 0.2
    for i in range(-1, 12):
        k = int(off // 32) + i
        x = k * 32 - off
        h = 40 + int(_hash(k) * 50)
        s.fill(far, (int(x), 150 - h, 33, h + 60))
    # mid structures (parallax 0.5): towers, tanks, pipes
    off = w.cam * 0.5
    for i in range(-1, 8):
        k = int(off // 48) + i
        x = int(k * 48 - off)
        r = _hash(k * 7 + 3)
        if r < 0.45:
            h = 50 + int(r * 80)
            s.fill(mid, (x + 10, 175 - h, 10, h))
            s.fill(mid, (x + 6, 175 - h, 18, 4))
            if (w.frame // 20 + k) % 3 == 0:
                s.fill((252, 96, 48), (x + 13, 171 - h, 4, 3))
        elif r < 0.75:
            pygame.draw.ellipse(s, mid, (x + 4, 140, 34, 40))
            s.fill(mid, (x + 4, 160, 34, 20))


def _terrain(s: pygame.Surface, w: World, theme):
    top, body, dith = theme[3], theme[4], theme[5]
    c0 = int(w.cam) // L.TILE
    for c in range(c0, c0 + L.SCREEN_W // L.TILE + 2):
        gy = L.GROUND[c] if 0 <= c < len(L.GROUND) else L.FLOOR
        x = c * L.TILE - int(w.cam)
        if gy is None:
            continue
        s.fill(body, (x, gy, L.TILE, L.SCREEN_H - gy))
        s.fill(top, (x, gy, L.TILE, 3))
        for yy in range(gy + 6, L.SCREEN_H, 6):
            for xx in range(0, L.TILE, 4):
                if (xx // 4 + yy // 6 + c) % 2 == 0:
                    s.fill(dith, (x + xx, yy, 2, 2))
        s.fill((0, 0, 0), (x, gy + 3, L.TILE, 1)) if False else None
    for x0, y0, wd in L.PLATFORMS:
        x = x0 - int(w.cam)
        if -wd < x < L.SCREEN_W:
            s.fill((96, 96, 112), (x, y0, wd, 4))
            s.fill((180, 180, 196), (x, y0, wd, 1))
            for xx in range(0, wd, 8):
                pygame.draw.line(s, (64, 64, 80), (x + xx, y0 + 4), (x + xx + 4, y0 + 8))
            s.fill((64, 64, 80), (x, y0 + 8, wd, 1))


def _player(s: pygame.Surface, w: World):
    if w.dead_timer or (w.invuln and (w.frame // 3) % 2):
        return
    flip = w.facing < 0
    if not w.on_ground:
        grid = S.PLAYER_BALL
    elif w.crouching:
        grid = S.PLAYER_CROUCH
    elif abs(w.px - getattr(w, "_last_px", w.px)) > 0.1:
        grid = S.PLAYER_RUN[(w.frame // 6) % 2]
    else:
        grid = S.PLAYER_STAND
    w._last_px = w.px
    spr = S.sprite(grid, flip)
    x = int(w.px - w.cam) - spr.get_width() // 2
    y = int(w.py) - spr.get_height() - (4 if not w.on_ground else 0)
    s.blit(spr, (x, y))
    # gun: points in the aim direction
    gx, gy = w.gun()
    dx, dy = DIR_VEC[w.aim]
    sx, sy = gx - w.cam - dx * 6, gy - dy * 6
    pygame.draw.line(s, S.PAL["g"], (sx, sy), (sx + dx * 8, sy + dy * 8), 3)
    pygame.draw.line(s, S.PAL["G"], (sx, sy), (sx + dx * 8, sy + dy * 8), 1)
    if w.shield:
        r = 16 + (w.frame // 4) % 2
        pygame.draw.circle(s, (80, 208, 248), (int(w.px - w.cam), int(w.py) - 12), r, 1)


def _enemies(s: pygame.Surface, w: World):
    for e in w.enemies:
        x, y = int(e.x - w.cam), int(e.y)
        if e.kind == "soldier":
            grid = S.SOLDIER_WALK if (e.vx and (w.frame // 8) % 2) else S.SOLDIER
            spr = S.sprite(grid, e.dir == "E", (80, 80, 200) if e.shooter else None)
            s.blit(spr, (x - spr.get_width() // 2, y - spr.get_height()))
            if e.shooter:
                sgn = 1 if e.dir == "E" else -1
                pygame.draw.line(s, S.PAL["g"], (x + 2 * sgn, y - 15), (x + 9 * sgn, y - 15), 2)
        elif e.kind == "turret":
            s.fill((72, 72, 88), (x - 8, y - 8, 16, 8))
            s.fill((140, 140, 148), (x - 8, y - 8, 16, 1))
            pygame.draw.circle(s, (104, 104, 120), (x, y - 8), 7)
            pygame.draw.circle(s, (200, 48, 24) if (w.frame // 10) % 2 else (120, 24, 16), (x, y - 9), 2)
            dx, dy = DIR_VEC[e.dir]
            pygame.draw.line(s, (40, 40, 52), (x, y - 8), (x + dx * 12, y - 8 + dy * 12), 3)
        elif e.kind == "drone":
            spr = S.sprite(S.DRONE)
            s.blit(spr, (x - 7, y - 10))
            if (w.frame // 2) % 2:
                pygame.draw.line(s, (220, 220, 220), (x - 9, y - 11), (x - 3, y - 11))
                pygame.draw.line(s, (220, 220, 220), (x + 3, y - 11), (x + 9, y - 11))
        elif e.kind == "mine":
            spr = S.sprite(S.MINE, (w.frame // 6) % 2 == 0)
            s.blit(spr, (x - 5, y - 7))
        elif e.kind == "cannon":
            s.fill((88, 40, 104), (x - 9, y - 14, 30, 14))
            s.fill((168, 80, 224), (x - 9, y - 14, 30, 2))
            s.fill((40, 20, 48), (x - 20, y - 9, 12, 4))
            if e.hp <= 3 and (w.frame // 4) % 2:
                s.fill((252, 136, 32), (x - 2, y - 10, 4, 4))
        elif e.kind == "core":
            s.fill((56, 24, 72), (x - 14, y - 34, 40, 40))
            s.fill((120, 60, 150), (x - 14, y - 34, 40, 2))
            col = (252, 64, 96) if e.dir == "open" else (96, 96, 120)
            r = 9 + ((w.frame // 5) % 2 if e.dir == "open" else 0)
            pygame.draw.circle(s, col, (x, y - 15), r)
            pygame.draw.circle(s, (252, 220, 240) if e.dir == "open" else (140, 140, 160), (x - 2, y - 17), 3)
    for p in w.pickups:
        x, y = int(p.x - w.cam), int(p.y + 3 * math.sin(w.frame / 12))
        spr = S.sprite(S.PICKUP)
        s.blit(spr, (x - 6, y - 12))
        font.draw(s, p.dir, x - 2, y - 11, (16, 14, 32))


def _shots_fx(s: pygame.Surface, w: World):
    for sh in w.pshots:
        pygame.draw.circle(s, (252, 252, 200), (int(sh.x - w.cam), int(sh.y)), 2)
    for sh in w.eshots:
        c = {"high": (252, 96, 96), "aimed": (252, 160, 64), "bomb": (252, 220, 96), "orb": (252, 64, 200)}.get(sh.kind, (252, 96, 96))
        pygame.draw.circle(s, c, (int(sh.x - w.cam), int(sh.y)), sh.r)
        pygame.draw.circle(s, (255, 255, 255), (int(sh.x - w.cam), int(sh.y)), 1)
    for x, y, t, kind in w.fx:
        cx, cy = int(x - w.cam), int(y)
        if kind == "boom":
            r = 3 + t // 2
            pygame.draw.circle(s, (252, 224, 96) if t < 8 else (252, 136, 32), (cx, cy), r)
            if t > 6:
                pygame.draw.circle(s, (120, 40, 24), (cx, cy), max(1, r - 4))
        else:
            pygame.draw.circle(s, (255, 255, 255), (cx, cy), 2 if t < 4 else 1)


def _hud(s: pygame.Surface, w: World):
    for i in range(max(0, w.lives)):
        s.fill((0, 168, 160), (8 + i * 9, 8, 6, 9))
        s.fill((248, 184, 0), (9 + i * 9, 10, 4, 2))
    font.draw(s, f"{w.score:07d}", 96, 8, (252, 252, 252))
    font.draw(s, f"ARMA {w.weapon}", 196, 8, (252, 224, 96))
    sec = L.section_at(w.px)
    first = next((x for x, n in L.SECTIONS if n == sec), 0)
    if abs(w.px - first) < 90 or w.frame < 120:
        font.draw(s, sec, (L.SCREEN_W - font.width(sec)) // 2, 40, (252, 252, 252))
    if w.cleared:
        font.draw(s, "NUCLEO NEUTRALIZADO", 70, 100, (252, 224, 96))
    elif w.over:
        font.draw(s, "FIN DE LA MISION", 80, 100, (252, 96, 96))


def draw_world(s: pygame.Surface, w: World) -> None:
    theme = THEMES[L.section_at(w.cam + 128)]
    _background(s, w, theme)
    _terrain(s, w, theme)
    _enemies(s, w)
    _player(s, w)
    _shots_fx(s, w)
    _hud(s, w)


_scan: dict = {}


def upscale(src: pygame.Surface, factor: int = 4, crt: bool = True) -> pygame.Surface:
    out = pygame.transform.scale(src, (src.get_width() * factor, src.get_height() * factor))
    if crt:
        key = out.get_size()
        if key not in _scan:
            ov = pygame.Surface(key, pygame.SRCALPHA)
            for y in range(factor - 1, key[1], factor):
                ov.fill((0, 0, 0, 70), (0, y, key[0], 1))
            _scan[key] = ov
        out.blit(_scan[key], (0, 0))
    return out

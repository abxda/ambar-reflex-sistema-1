"""Original military arcade art, 256x240, nearest-neighbor CRT.

Experience: the recorded firefight leads; telemetry remains truthful.
World: dusk refinery, blue steel, copper sky, amber instruments.
Silhouettes: bare arms, teal combat vest, red hostile armor, machined weapons.
Depth: distant ridges, refinery silhouettes, pipework, riveted foreground.
Boundary: drawing reads the simulation; animation never changes its state.
"""

from __future__ import annotations

import math
from weakref import WeakKeyDictionary

import pygame

from . import font
from . import level as L
from . import sprites as S
from .core import DIR_VEC, World

THEMES = {  # sky bands top->bottom, far silhouettes, mid structures, ground top, ground body, ground dither
    "REFINERIA": ([(32, 38, 65), (94, 60, 77), (178, 91, 83), (236, 149, 105)], (85, 66, 82), (33, 46, 61),
                  (170, 183, 174), (42, 56, 67), (26, 37, 50)),
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
    # Pixel-dithered band transitions and a sun behind the refinery stacks.
    for i in range(1, len(sky)):
        for yy in range(i * band - 5, i * band + 5):
            for xx in range((yy % 2) * 2, L.SCREEN_W, 4):
                if (yy - i * band + 5) < ((xx // 4) % 5) * 2:
                    s.fill(sky[i - 1], (xx, yy, 2, 1))
    sunx = int(201 - w.cam * .08) % 320
    pygame.draw.circle(s, (250, 183, 119), (sunx, 79), 19)
    for yy in range(79, 100, 4):
        s.fill(sky[2], (sunx - 20, yy, 40, 1))
    # far silhouettes (parallax 0.2): mesas / ridges
    off = w.cam * 0.2
    for i in range(-1, 12):
        k = int(off // 32) + i
        x = k * 32 - off
        h = 40 + int(_hash(k) * 50)
        pygame.draw.polygon(s, far, [(int(x), 160), (int(x), 150-h+17),
                                    (int(x)+12, 150-h), (int(x)+25, 154-h),
                                    (int(x)+38, 125), (int(x)+38, 180)])
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
            for yy in range(178 - h, 172, 12):
                s.fill((61, 67, 78), (x + 11, yy, 2, 7))
                s.fill((78, 72, 79), (x + 10, yy + 8, 10, 1))
            # Deterministic exhaust, behind the active playfield.
            for j in range(4):
                drift = (w.frame // 8 + j * 6) % 24
                pygame.draw.circle(s, far, (x + 15 + drift // 3, 170-h-drift), 2+j)
            if (w.frame // 20 + k) % 3 == 0:
                s.fill((252, 96, 48), (x + 13, 171 - h, 4, 3))
        elif r < 0.75:
            pygame.draw.ellipse(s, mid, (x + 4, 140, 34, 40))
            s.fill(mid, (x + 4, 160, 34, 20))
            pygame.draw.arc(s, (69, 76, 86), (x+7, 144, 28, 18), 0, math.pi, 1)
            for xx in range(x + 10, x + 35, 8):
                s.fill((51, 65, 77), (xx, 153, 1, 26))
            s.fill((79, 80, 86), (x+4, 169, 34, 2))
        else:
            pygame.draw.line(s, mid, (x+8, 180), (x+8, 100), 3)
            pygame.draw.line(s, mid, (x+36, 180), (x+36, 100), 3)
            for yy in range(104, 180, 16):
                pygame.draw.line(s, mid, (x+8, yy), (x+36, yy+16), 2)
                pygame.draw.line(s, mid, (x+36, yy), (x+8, yy+16), 2)
            pygame.draw.line(s, mid, (x, 99), (x+46, 99), 4)
    # Near service conduits travel at a third parallax speed.
    off = int(w.cam * .75)
    for base in range(off // 96 - 1, off // 96 + 4):
        x = base * 96 - off
        s.fill((23, 34, 47), (x, 177, 96, 7))
        s.fill((63, 80, 91), (x, 177, 96, 1))
        s.fill((96, 105, 106), (x+14, 175, 3, 11))
        s.fill((19, 29, 42), (x+19, 157, 37, 20))
        for xx in range(x+23, x+52, 5):
            s.fill((52, 67, 77), (xx, 161, 2, 11))


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
        s.fill((13, 22, 32), (x, gy + 3, L.TILE, 3))
        for xx in range(0, L.TILE, 8):
            s.fill((221, 158, 62) if (c + xx // 8) % 2 else dith, (x+xx, gy+4, 5, 2))
        for yy in range(gy + 9, L.SCREEN_H, 16):
            s.fill(dith, (x, yy, L.TILE-1, 15))
            s.fill(body, (x+1, yy+1, L.TILE-3, 1))
            s.fill((90, 107, 113), (x+2, yy+3, 1, 1))
            s.fill((10, 19, 30), (x+2, yy+5, 1, 1))
            for xx in range(5, L.TILE-2, 4):
                s.fill((18, 28, 40), (x+xx, yy+5, 2, 6))
    for x0, y0, wd in L.PLATFORMS:
        x = x0 - int(w.cam)
        if -wd < x < L.SCREEN_W:
            s.fill((96, 96, 112), (x, y0, wd, 4))
            s.fill((180, 180, 196), (x, y0, wd, 1))
            for xx in range(0, wd, 8):
                pygame.draw.line(s, (64, 64, 80), (x + xx, y0 + 4), (x + xx + 4, y0 + 8))
            s.fill((64, 64, 80), (x, y0 + 8, wd, 1))
            for xx in range(2, wd-2, 12):
                s.fill((233, 165, 65), (x+xx, y0+2, 4, 2))
                s.fill((200, 206, 188), (x+xx, y0, 1, 1))


_poses = WeakKeyDictionary()


def _player(s: pygame.Surface, w: World):
    previous = _poses.get(w)
    moving = previous is not None and abs(w.px - previous[1]) > .1
    if previous is not None and previous[0] == w.frame:
        moving = previous[2]
    _poses[w] = (w.frame, w.px, moving)
    if w.dead_timer or (w.invuln and (w.frame // 3) % 2):
        return
    flip = w.facing < 0
    if not w.on_ground:
        grid = S.PLAYER_BALL
    elif w.crouching:
        grid = S.PLAYER_CROUCH
    elif moving:
        grid = S.PLAYER_RUN[(w.frame // 5) % 4]
    else:
        grid = S.PLAYER_STAND
    spr = S.sprite(grid, flip)
    x = int(w.px - w.cam) - spr.get_width() // 2
    y = int(w.py) - spr.get_height() - (4 if not w.on_ground else 0)
    s.blit(spr, (x, y))
    # gun: points in the aim direction
    gx, gy = w.gun()
    dx, dy = DIR_VEC[w.aim]
    sx, sy = gx - w.cam - dx * 6, gy - dy * 6
    pygame.draw.line(s, S.PAL["K"], (sx-dx*3, sy-dy*3), (sx + dx * 10, sy + dy * 10), 5)
    pygame.draw.line(s, S.PAL["g"], (sx, sy), (sx + dx * 10, sy + dy * 10), 3)
    pygame.draw.line(s, S.PAL["G"], (sx, sy-1), (sx + dx * 8, sy + dy * 8-1), 1)
    # Only real newly emitted projectiles light the muzzle.
    if any(abs(sh.x-gx) < 13 and abs(sh.y-gy) < 13 for sh in w.pshots):
        mx, my = int(gx-w.cam+dx*6), int(gy+dy*6)
        pygame.draw.polygon(s, S.PAL["O"], [(mx+dx*7,my+dy*7), (mx-dy*3,my+dx*3),
                                             (mx-dx*2,my-dy*2), (mx+dy*3,my-dx*3)])
        pygame.draw.circle(s, S.PAL["Y"], (mx,my), 2)
        s.fill(S.PAL["W"], (mx,my,1,1))
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
        pygame.draw.line(s, (211, 133, 52), (int(sh.x-w.cam-sh.vx), int(sh.y-sh.vy)),
                         (int(sh.x-w.cam), int(sh.y)), 2)
        pygame.draw.circle(s, (252, 252, 200), (int(sh.x - w.cam), int(sh.y)), 2)
    for sh in w.eshots:
        c = {"high": (252, 96, 96), "aimed": (252, 160, 64), "bomb": (252, 220, 96), "orb": (252, 64, 200)}.get(sh.kind, (252, 96, 96))
        pygame.draw.circle(s, c, (int(sh.x - w.cam), int(sh.y)), sh.r)
        pygame.draw.circle(s, (255, 255, 255), (int(sh.x - w.cam), int(sh.y)), 1)
    for x, y, t, kind in w.fx:
        cx, cy = int(x - w.cam), int(y)
        if kind == "boom":
            r = 4 + min(t, 12)
            for j in range(7):
                a = j * math.tau / 7 + _hash(int(x)+j) * .8
                rr = r * .6
                pos = (int(cx+math.cos(a)*rr), int(cy+math.sin(a)*rr-t*.16))
                pygame.draw.circle(s, (71, 49, 56), pos, max(2, 7-t//5))
                if t < 17:
                    pygame.draw.circle(s, (198, 61, 38), pos, max(1, 6-t//4))
                    pygame.draw.circle(s, (255, 154, 48), pos, max(1, 4-t//5))
            if t < 12:
                pygame.draw.circle(s, (255, 217, 107), (cx,cy), max(1, 9-t//2))
                pygame.draw.circle(s, (255, 250, 216), (cx,cy), max(1, 6-t//2))
            for j in range(9):
                a = j * math.tau / 9
                rr = 4 + t * (1+_hash(j+int(x)))
                ex, ey = cx+math.cos(a)*rr, cy+math.sin(a)*rr+t*t*.022
                pygame.draw.line(s, (255, 194, 76) if t < 13 else (155, 89, 62),
                                 (int(ex),int(ey)), (int(ex-math.cos(a)*3),int(ey-math.sin(a)*3)))
        else:
            pygame.draw.circle(s, (255, 255, 255), (cx, cy), 2 if t < 4 else 1)


def _hud(s: pygame.Surface, w: World):
    s.fill((12, 20, 31), (0, 0, 256, 25))
    s.fill((80, 100, 110), (0, 24, 256, 1))
    font.draw(s, "1P", 8, 17, (240, 164, 67))
    font.draw(s, "PUNTAJE", 96, 17, (139, 159, 168))
    font.draw(s, "EQUIPO", 196, 17, (139, 159, 168))
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

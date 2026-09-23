"""Frame -> compact, deterministic text `state` for System One (no screenshots).

Convention: dx > 0 = ahead; enemies: dy relative to the firing line (0 = a horizontal shot hits);
projectiles: height above the feet (crouch dodges 12-22, jump dodges < 10).
Only on-screen entities, nearest first, at most MAX_THREATS threats.
"""

from __future__ import annotations

from . import level as L
from .core import World

MAX_THREATS = 6

NAMES = {
    "es": {"soldier": "soldado", "shooter": "tirador", "turret": "torreta", "drone": "dron", "mine": "mina",
           "cannon": "cañón", "core": "núcleo", "high": "bala alta", "aimed": "bala", "bomb": "bomba",
           "orb": "orbe", "p": "bala propia"},
    "en": {"soldier": "soldier", "shooter": "gunner", "turret": "turret", "drone": "drone", "mine": "mine",
           "cannon": "cannon", "core": "core", "high": "high bullet", "aimed": "bullet", "bomb": "bomb",
           "orb": "orb", "p": "own bullet"},
}
TXT = {
    "es": {"ground": "en suelo", "air": "en el aire", "crouch": "agachado", "weapon": "arma", "lives": "vidas",
           "prog": "avance", "pit": "hoyo", "step": "escalón", "plat": "plataforma", "ahead": "adelante",
           "comes": "viene", "none": "ninguna", "height": "altura",
           "threats": "Amenazas (px; dx+ adelante; dy = arriba(+)/abajo(-) de la línea de tiro, 0 = en la mira; altura sobre el suelo)",
           "terrain": "Terreno", "flat": "plano", "shield": "escudo", "boss": "jefe", "respawn": "reapareciendo",
           "core_open": "núcleo expuesto", "core_shut": "núcleo blindado"},
    "en": {"ground": "on ground", "air": "airborne", "crouch": "crouching", "weapon": "weapon", "lives": "lives",
           "prog": "progress", "pit": "pit", "step": "step", "plat": "platform", "ahead": "ahead",
           "comes": "incoming", "none": "none", "height": "height",
           "threats": "Threats (px; dx+ ahead; dy = above(+)/below(-) the firing line, 0 = in the sights; height above ground)",
           "terrain": "Terrain", "flat": "flat", "shield": "shield", "boss": "boss", "respawn": "respawning",
           "core_open": "core exposed", "core_shut": "core armored"},
}


def _terrain(w: World, t: dict, x: float) -> str:
    out = []
    feet = w.py
    for d in range(8, 72, 4):
        g = L.ground_at(x + d)
        if g is None:
            out.append(f"{t['pit']} {d}px {t['ahead']}")
            break
        if g < feet - 6:
            out.append(f"{t['step']} +{int(feet - g)}px {d}px {t['ahead']}")
            break
    for x0, y0, wd in L.PLATFORMS:
        if x0 + wd > x - 8 and x0 < x + 80 and y0 < feet - 4:
            out.append(f"{t['plat']} {int(feet - y0)}px arriba {max(0, int(x0 - x))}px {t['ahead']}"
                       if t is TXT["es"] else f"{t['plat']} {int(feet - y0)}px up {max(0, int(x0 - x))}px {t['ahead']}")
            break
    return "; ".join(out) if out else t["flat"]


def _velocity(e, w: World) -> float:
    if e.kind == "soldier":
        return e.vx
    if e.kind == "mine":
        return -0.9 if w.px < e.x else 0.9
    if e.kind == "drone":
        return -0.7
    return 0.0


def describe(w: World, lang: str = "es", lookahead: int = 0, player_vx: float = 0.0) -> str:
    """lookahead > 0: dead-reckon enemies/projectiles (and the player) that many frames ahead,
    so the answer matches the world when it arrives (latency compensation)."""
    t, n = TXT[lang], NAMES[lang]
    if w.dead_timer:
        return f"{t['respawn']}."
    stance = t["crouch"] if w.crouching and w.on_ground else (t["ground"] if w.on_ground else t["air"])
    head = (f"Soldado {stance}, {t['weapon']} {w.weapon}, {t['lives']} {w.lives}, {t['prog']} {w.progress():.0f}%"
            if lang == "es" else
            f"Soldier {stance}, {t['weapon']} {w.weapon}, {t['lives']} {w.lives}, {t['prog']} {w.progress():.0f}%")
    if w.shield:
        head += f", {t['shield']}"
    feet_x, feet_y = w.px + player_vx * lookahead, w.py
    saved = w.aim
    w.aim = "E"
    gun_y = w.gun()[1]          # the firing line of a horizontal shot
    w.aim = saved
    items = []
    for e in w.enemies:
        if not (w.cam - 4 < e.x < w.cam + L.SCREEN_W + 4):
            continue
        ex = e.x + _velocity(e, w) * lookahead
        top, bottom = e.y - e.h, e.y
        # dy relative to the firing line: 0 when a horizontal shot would cross the target
        dy = 0 if top <= gun_y <= bottom else int(gun_y - (bottom if gun_y > bottom else top))
        dx = int(ex - feet_x)
        name = n["shooter"] if e.kind == "soldier" and e.shooter else n[e.kind]
        extra = ""
        if e.kind in ("soldier", "mine") and (e.x - feet_x) * (e.vx if e.kind == "soldier" else -1) < 0:
            extra = f" {t['comes']}"
        if e.kind == "core":
            extra = f" ({t['core_open'] if e.dir == 'open' else t['core_shut']})"
        items.append((abs(dx) + abs(dy), f"{name} dx{dx:+d} dy{dy:+d}{extra}"))
    for sh in w.eshots:
        dx = int(sh.x + sh.vx * lookahead - feet_x)
        h = int(feet_y - (sh.y + sh.vy * lookahead))  # height above the soldier's feet
        comes = (dx * sh.vx < 0) or (h > 0 and sh.vy > 0)
        items.append((abs(dx) + abs(h) - 20, f"{n[sh.kind]} dx{dx:+d} {t['height']}{h:+d}{' ' + t['comes'] if comes else ''}"))
    items.sort(key=lambda it: it[0])
    threats = "; ".join(txt for _, txt in items[:MAX_THREATS]) or t["none"]
    return f"{head}. {t['terrain']}: {_terrain(w, t, feet_x)}. {t['threats']}: {threats}."

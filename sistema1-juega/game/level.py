"""The single level, authored in code: terrain, one-way platforms, spawns, pickups.

Theme (original): desert refinery -> canyon -> reactor core, boss machine at the end.
Coordinates: pixels, y grows downwards, ground height is the y of the walkable surface.
"""

from __future__ import annotations

TILE = 16
SCREEN_W, SCREEN_H = 256, 240
FLOOR = 200          # default ground surface y
PIT = None           # no ground: falling means death
LEVEL_W = 4352       # 272 columns
BOSS_X = 4096        # camera locks here for the boss arena (arena = 4096..4352)

SECTIONS = [(0, "REFINERIA"), (1408, "CANON"), (2688, "REACTOR"), (BOSS_X, "NUCLEO")]


def _ground() -> list:
    cols = [FLOOR] * (LEVEL_W // TILE)

    def seg(c0, c1, y):
        for c in range(c0, c1):
            cols[c] = y

    # refinery: flat with two small pits and a raised deck
    seg(22, 24, PIT)
    seg(30, 38, 184)
    seg(52, 55, PIT)
    seg(64, 72, 176)
    # canyon: steps, wider pits bridged by platforms
    seg(88, 91, PIT)
    seg(92, 100, 184)
    seg(100, 104, 168)
    seg(110, 113, PIT)
    seg(120, 128, 184)
    seg(134, 137, PIT)
    seg(146, 152, 176)
    seg(158, 161, PIT)
    # reactor: flat corridors, one long pit with platforms
    seg(176, 182, PIT)
    seg(196, 204, 184)
    seg(214, 217, PIT)
    seg(236, 239, PIT)
    return cols


GROUND = _ground()

# one-way platforms (x, y, width): can be landed on from above, passed from below
PLATFORMS = [
    (440, 150, 64), (840, 140, 48),
    (1400, 150, 80), (1744, 136, 64), (2128, 144, 64), (2512, 140, 64),
    (2800, 150, 96), (3120, 144, 48), (3400, 136, 64), (3760, 150, 64),
    (4180, 150, 48),
]

# spawns: (trigger_x, kind, x, y, params) -- fire when the camera's right edge passes trigger_x
SPAWNS = [
    # refinery
    (300, "soldier", 300, None, {}), (380, "soldier", 390, None, {"shooter": True}),
    (520, "turret", 540, None, {}), (600, "soldier", 620, None, {}),
    (700, "mine", 710, None, {}), (760, "soldier", 770, None, {"shooter": True}),
    (900, "drone", 910, 90, {}), (980, "soldier", 990, None, {}),
    (1060, "turret", 1090, 176, {}), (1150, "soldier", 1160, None, {"shooter": True}),
    (1250, "mine", 1260, None, {}), (1330, "drone", 1340, 80, {}),
    # canyon
    (1460, "soldier", 1480, None, {"shooter": True}), (1560, "drone", 1570, 70, {}),
    (1620, "turret", 1640, 168, {}), (1700, "mine", 1710, None, {}),
    (1800, "soldier", 1810, None, {}), (1880, "drone", 1890, 100, {}),
    (1950, "turret", 1990, 184, {}), (2050, "soldier", 2060, None, {"shooter": True}),
    (2180, "mine", 2190, None, {}), (2260, "drone", 2270, 80, {}),
    (2340, "soldier", 2350, None, {"shooter": True}), (2420, "turret", 2450, 176, {}),
    (2560, "drone", 2570, 90, {}), (2620, "soldier", 2630, None, {}),
    # reactor
    (2760, "turret", 2780, None, {}), (2860, "soldier", 2870, None, {"shooter": True}),
    (2950, "mine", 2960, None, {}), (3040, "drone", 3050, 80, {}),
    (3160, "turret", 3190, 184, {}), (3240, "soldier", 3250, None, {"shooter": True}),
    (3330, "mine", 3340, None, {}), (3440, "drone", 3450, 70, {}),
    (3520, "soldier", 3530, None, {}), (3600, "turret", 3620, None, {}),
    (3700, "soldier", 3710, None, {"shooter": True}), (3820, "drone", 3830, 90, {}),
    (3900, "mine", 3910, None, {}), (3960, "soldier", 3970, None, {"shooter": True}),
]

# pickups: (x, y, kind)  S=spread  R=rapid  B=barrier
PICKUPS = [(600, 150, "S"), (1760, 110, "R"), (2830, 125, "B"), (3780, 125, "S")]

# random reinforcements: soldiers entering from the right edge while in these x ranges
REINFORCE = [(200, 1300, 150), (1500, 2600, 130), (2700, 4000, 110)]  # (x0, x1, mean frames)


def ground_at(x: float):
    c = int(x) // TILE
    if c < 0:
        return FLOOR
    if c >= len(GROUND):
        return FLOOR
    return GROUND[c]


def section_at(x: float) -> str:
    name = SECTIONS[0][1]
    for x0, n in SECTIONS:
        if x >= x0:
            name = n
    return name

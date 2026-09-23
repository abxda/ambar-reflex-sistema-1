"""Original pixel art, drawn as character grids for this project (no third-party assets)."""

from __future__ import annotations

import pygame

PAL = {
    "K": (16, 14, 32), "T": (0, 168, 160), "D": (0, 96, 112), "V": (248, 184, 0), "W": (252, 252, 252),
    "G": (140, 140, 148), "g": (84, 84, 96), "R": (200, 48, 24), "r": (120, 24, 16), "B": (228, 196, 144),
    "b": (160, 124, 72), "Y": (252, 224, 96), "O": (252, 136, 32), "C": (80, 208, 248), "P": (168, 80, 224),
}

PLAYER_STAND = [
    "....KKKK....", "...KTTTTK...", "..KTTTTTTK..", "..KTVVVVDK..", "..KTVVVVDK..", "...KTTTDK...",
    "....KDDK....", "..KKTTTTKK..", ".KTTTTTTTTK.", ".KTDTTTTDTK.", ".KTDTTTTDTK.", ".KTDTTTTDTK.",
    "..KKTTTTKK..", "...KDDDDK...", "...KTTTTK...", "...KTKKTK...", "...KTK.KTK..", "...KTK.KTK..",
    "..KTTK.KTK..", "..KTK..KTK..", "..KTK..KTTK.", "..KDK..KDK..", ".KDDK..KDDK.", ".KKKK..KKKK.",
]
_LEGS_A = ["...KTTTTK...", "..KTK.KTK...", ".KTK...KTK..", ".KTK....KTK.", "KTK.....KTK.",
           "KTK......KTK", "KDK......KDK", "KDDK.....KDD", "KKKK.....KKK"]
_LEGS_B = ["...KTTTTK...", "...KTKKTK...", "....KTTK....", "....KTTK....", "...KTK.K....",
           "...KTK.KTK..", "...KDK.KDK..", "..KDDK.KDDK.", "..KKKK.KKKK."]
PLAYER_RUN = [PLAYER_STAND[:15] + _LEGS_A, PLAYER_STAND[:15] + _LEGS_B]
PLAYER_CROUCH = [
    "....KKKK....", "...KTTTTK...", "..KTVVVVDK..", "..KTVVVVDK..", "..KKTTTTKK..", ".KTTTTTTTTK.",
    ".KTDTTTTDTK.", "KTTTKKKKTTTK", "KTK......KTK", "KDK......KDK", "KDDK....KDDK", "KKKK....KKKK",
]
PLAYER_BALL = [
    "....KKKK....", "..KKTTTTKK..", ".KTTVVVVTTK.", ".KTVVVVVVTK.", "KTTTTTTTTTTK", "KTDTTTTTTDTK",
    "KTDTTTTTTDTK", "KTTTTTTTTTTK", ".KTTDDDDTTK.", ".KTTTTTTTTK.", "..KKTTTTKK..", "....KKKK....",
]
SOLDIER = [
    "...KKKK...", "..KbbbbK..", ".KbbbbbbK.", ".KBRRRRBK.", ".KBBBBBBK.", "..KBBBBK..", "..KKbbKK..",
    ".KbbbbbbK.", "KbbRbbRbbK", "KbbbbbbbbK", "KbbRbbRbbK", ".KbbbbbbK.", "..KrrrrK..", "..KbbbbK..",
    "..KbKKbK..", "..KbK.KbK.", "..KbK.KbK.", ".KbbK.KbK.", ".KbK..KbK.", ".KrK..KrK.", "KrrK..KrrK",
    "KKKK..KKKK",
]
SOLDIER_WALK = [
    "...KKKK...", "..KbbbbK..", ".KbbbbbbK.", ".KBRRRRBK.", ".KBBBBBBK.", "..KBBBBK..", "..KKbbKK..",
    ".KbbbbbbK.", "KbbRbbRbbK", "KbbbbbbbbK", "KbbRbbRbbK", ".KbbbbbbK.", "..KrrrrK..", "..KbbbbK..",
    "..KbKKbK..", ".KbK..KbK.", ".KbK...KbK", "KbK....KbK", "KbK.....Kb", "KrK.....Kr", "KrrK....Kr",
    "KKKK....KK",
]
DRONE = [
    "..KKKKKKKKKK..", ".KGGGGGGGGGGK.", "KGgggRRRRgggGK", "KGgggRYYRgggGK", ".KGGGGGGGGGGK.",
    "..KgKKKKKKgK..", ".KgK......KgK.", "KKK........KKK",
]
MINE = [
    "...KKKK...", "..KRYYRK..", ".KgRRRRgK.", "KggggggggK", "KgKgKgKggK", "KggggggggK", ".KKKKKKKK.",
]
PICKUP = [
    "..KKKKKKKK..", ".KWWWWWWWWK.", "KWCCCCCCCCWK", "KWC......CWK", "KWC......CWK", "KWC......CWK",
    "KWC......CWK", "KWC......CWK", "KWC......CWK", "KWCCCCCCCCWK", ".KWWWWWWWWK.", "..KKKKKKKK..",
]

_cache: dict = {}


def sprite(grid: list[str], flip: bool = False, tint: tuple | None = None) -> pygame.Surface:
    key = (id(grid), flip, tint)
    if key in _cache:
        return _cache[key]
    h, w = len(grid), max(len(r) for r in grid)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch in PAL:
                c = PAL[ch]
                if tint and ch != "K":
                    c = tuple(min(255, (a + b) // 2) for a, b in zip(c, tint))
                surf.set_at((x, y), c)
    if flip:
        surf = pygame.transform.flip(surf, True, False)
    _cache[key] = surf
    return surf

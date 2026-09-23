"""Original pixel art, drawn as character grids for this project (no third-party assets)."""

from __future__ import annotations

import pygame

PAL = {
    "K": (16, 14, 32), "T": (0, 168, 160), "D": (0, 96, 112), "V": (248, 184, 0), "W": (252, 252, 252),
    "G": (140, 140, 148), "g": (84, 84, 96), "R": (200, 48, 24), "r": (120, 24, 16), "B": (228, 196, 144),
    "b": (160, 124, 72), "Y": (252, 224, 96), "O": (252, 136, 32), "C": (80, 208, 248), "P": (168, 80, 224),
}
PAL.update({"s": (164, 83, 52), "S": (237, 163, 99), "H": (255, 213, 147),
            "N": (28, 51, 73), "n": (51, 91, 116), "L": (108, 165, 175),
            "T": (40, 125, 137), "D": (23, 66, 82), "G": (170, 187, 190),
            "g": (69, 89, 106), "K": (12, 18, 29)})

PLAYER_STAND = [
    ".....KKKK.....", "....KgggGK....", "....KRRRRRK...", "...RRKSHSK....",
    "..RK.KSHKK....", ".....KsSK.....", "...KKsSsKK....", "..KTLSSSDTK...",
    ".KHLTDSTDHsK..", ".KSSDTDTHSSK..", ".KsSTDDSHsSK..", "..KSTDDSsKK...",
    "...KTVVTDK....", "...KNNnnNK....", "...KnNnnNK....", "...KnNKNnK....",
    "...KnNKKnK....", "..KnNK.KnNK...", "..KnNK.KNnK...", "..KLNK.KNLK...",
    "..KNNK..KNK...", "..KggK..KgK...", ".KgggK..KggK..", ".KKKKK..KKKK..",
]
_LEGS_A = ["...KnNKNnK....", "..KnNK.KnnK...", ".KnNK...KnNK..", ".KLNK....KNnK.",
           "KNNK.....KNLK.", "KggK......KgK.", "KggK......KggK", "KgggK.....KKKK", "KKKKK........."]
_LEGS_B = ["...KnNKnNK....", "....KnNnK.....", "....KnNnK.....", "....KLNNK.....",
           "....KNNK......", "....KnNK......", "....KggK......", "...KgggK......", "...KKKKK......"]
PLAYER_RUN = [PLAYER_STAND[:15] + legs for legs in
              (_LEGS_A, _LEGS_B, [row[::-1] for row in _LEGS_A], _LEGS_B)]
PLAYER_CROUCH = [
    ".....KgggGK...", "....KRRRRRK...", "...RRKSHSK....", ".....KsSK.....",
    "..KKTLSSDTKK..", ".KHSTDSTHSSK..", ".KSSTDDSssK...", "..KTVVTDKK....",
    ".KnnNNnnnNK...", "KnNLKKKNNLK...", "KggK...KgggK..", "KKKK...KKKKK..",
]
PLAYER_BALL = [
    "....KgggGK....", "...KRRRRRK....", "..RRKSHSK.....", "....KsSSK.....",
    "..KTLSSDTKK...", ".KHSTDSTHSSK..", ".KSSTDDSssK...", "..KTVVTDKK....",
    "..KnnNNnnNK...", ".KnNLKKNNnK...", ".KggK..KLNK...", ".KKKK..KggK...",
    "........KKK...",
]
SOLDIER = [
    "...KKKKK....", "..KrRRRRK...", ".KrRBOBRRK..", ".KKKKRRKKK..",
    "..KsHSK.....", "..KsSsK.....", ".KKrRrKK....", "KrBRrRBbK...",
    "KsRrGrRHSK..", "KsRrGrRssK..", ".KrrGrRKK...", ".KrRrRrK....",
    "..KVVVK.....", "..KbBbK.....", "..KbKKbK....", "..KbK.KbK...",
    ".KbBK.KbK...", ".KbK..KbBK..", ".KrK..KrrK..", ".KgK..KggK..",
    "KggK..KgggK.", "KKKK..KKKKK.",
]
SOLDIER_WALK = SOLDIER[:14] + ["..KbKKbK....", ".KbK..KbK...", "KbBK...KbK..", "KbK....KbBK.",
                                    "KrK.....KrK.", "KgK.....KgK.", "KggK....KggK", "KKKK....KKKK"]
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

"""Human baseline: play with the keyboard; the run is logged exactly like the agent's (replayable).

Controls: arrows = move/aim (8 directions: combine with up/down), Z or SPACE = jump,
X = shoot, DOWN (without left/right) = crouch, ESC = quit. Crouch + left/right aims diagonally down.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pygame

from agent.modes import _finish
from game.core import FPS, IDLE, Action, World
from game.render import draw_world, upscale
from hud.panel import watermark

ROOT = Path(__file__).resolve().parents[1]


def read_keys(keys, facing: int) -> Action:
    left, right, up, down = keys[pygame.K_LEFT], keys[pygame.K_RIGHT], keys[pygame.K_UP], keys[pygame.K_DOWN]
    move = (1 if right else 0) - (1 if left else 0)
    horiz = "E" if (right or (not left and facing > 0)) else "W"
    if up and (left or right):
        aim = "N" + horiz
    elif up:
        aim = "N"
    elif down and (left or right):
        aim = "S" + horiz
    elif down:
        aim = horiz  # crouching shoots straight ahead
    else:
        aim = horiz
    return Action(move=move, jump=bool(keys[pygame.K_z] or keys[pygame.K_SPACE]),
                  crouch=bool(down and not (left or right)), aim=aim, shoot=bool(keys[pygame.K_x]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=1987)
    ap.add_argument("--run", type=int, default=None, help="run index (default: next free)")
    args = ap.parse_args()
    out_dir = ROOT / "runs" / "human"
    k = args.run if args.run is not None else len(list(out_dir.glob("*.meta.json"))) if out_dir.exists() else 0
    out = out_dir / f"human-{args.seed}-{k}"
    pygame.init()
    screen = pygame.display.set_mode((1024, 960))
    pygame.display.set_caption(f"Ámbar Reflex — partida humana #{k} (semilla {args.seed}) — @abxda")
    clock = pygame.time.Clock()
    world, surf = World(args.seed), pygame.Surface((256, 240))
    current, timeline = IDLE, []
    while not world.over:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                world.over = True
        a = read_keys(pygame.key.get_pressed(), world.facing)
        if a != current:
            current = a  # the world's own latch handles key edges; no re-arm (rearm=False in the log)
            timeline.append([world.frame, asdict(current), False])
        world.step(current)
        draw_world(surf, world)
        big = upscale(surf, 4)
        watermark(big, 1024 - 170, 960 - 56, 4)
        screen.blit(big, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)
    meta = _finish(world, {"mode": "human", "seed": args.seed}, [], timeline, out)
    print(json.dumps(meta["result"]))
    pygame.quit()


if __name__ == "__main__":
    main()

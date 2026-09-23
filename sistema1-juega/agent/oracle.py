"""Ground truth from the simulator: exact line-of-fire and counterfactual rollouts.

The world is deterministic and cheap to clone (~0.01 ms/frame), so labels are not guesses:
  shoot  -> an enemy is aligned with one of the 8 firing directions (raycast from the gun)
  jump   -> jumping now avoids damage that holding the current course would take within 30 frames
  crouch -> same, for crouching
"""

from __future__ import annotations

import math
from dataclasses import replace

from game import level as L
from game.core import DIR_VEC, DIRS, Action, World

HORIZON = 30
TARGETS = ("soldier", "turret", "drone", "mine", "cannon", "core")


def _ray_hits(world: World, ox: float, oy: float, d: str, crouch: bool):
    dx, dy = DIR_VEC[d]
    best = None
    for e in world.enemies:
        if e.kind not in TARGETS or (e.kind == "core" and e.dir != "open"):
            continue
        x0, y0, x1, y1 = e.box()
        # sample the ray every 3 px up to the screen edge
        for k in range(4, 280, 3):
            x, y = ox + dx * k, oy + dy * k
            if not (world.cam - 4 < x < world.cam + L.SCREEN_W + 4 and -4 < y < L.SCREEN_H + 4):
                break
            if x0 - 2 < x < x1 + 2 and y0 - 2 < y < y1 + 2:
                if best is None or k < best[0]:
                    best = (k, e.kind)
                break
    return best


def line_of_fire(world: World) -> dict:
    """{direction: (distance, kind)} for every direction with an enemy in line (from the current stance)."""
    out = {}
    saved = world.aim
    for d in DIRS:
        world.aim = d
        gx, gy = world.gun()
        hit = _ray_hits(world, gx, gy, d, world.crouching)
        if hit:
            out[d] = hit
    world.aim = saved
    return out


def rollout_damage(world: World, action: Action, frames: int = HORIZON) -> bool:
    w = world.snapshot()
    lives, hits = w.lives, w.hits_taken
    first = action
    hold = replace(action, jump=action.jump)  # jump stays latched: edge fires only once
    for i in range(frames):
        w.step(first if i == 0 else hold)
        if w.hits_taken > hits or w.lives < lives or w.over:
            return True
    return False


def labels(world: World, course: Action) -> dict:
    """Labels for the decision taken at this state. `course` = what the agent would do otherwise."""
    base = replace(course, jump=False, crouch=False, shoot=False)
    dmg_base = rollout_damage(world, base)
    dmg_jump = rollout_damage(world, replace(base, jump=True))
    dmg_crouch = rollout_damage(world, replace(base, crouch=True, move=0))
    lof = line_of_fire(world)
    return {
        "shoot": any(world.cam - 4 < e.x < world.cam + L.SCREEN_W + 4 and e.kind in TARGETS
                     and not (e.kind == "core" and e.dir != "open") for e in world.enemies),
        "aligned": bool(lof),
        "lof_dirs": sorted(lof),
        "best_aim": min(lof, key=lambda d: lof[d][0]) if lof else None,
        "jump": dmg_base and not dmg_jump,
        "crouch": dmg_base and not dmg_crouch,
        "threatened": dmg_base,
    }


def heuristic_action(world: World) -> Action:
    """Reference bot with oracle access (used to tune difficulty, not as a System One baseline)."""
    lof = line_of_fire(world)
    aim = min(lof, key=lambda d: lof[d][0]) if lof else "E"
    base = Action(move=1, aim=aim, shoot=True)
    if world.dead_timer:
        return base
    # pits ahead: jump at the edge
    ahead = L.ground_at(world.px + 10)
    if world.on_ground and ahead is None:
        return replace(base, jump=True)
    if rollout_damage(world, replace(base, shoot=False), 24):
        for alt in (replace(base, jump=True), replace(base, crouch=True, move=0), replace(base, move=0),
                    replace(base, move=-1), replace(base, move=-1, jump=True)):
            if not rollout_damage(world, replace(alt, shoot=False), 24):
                return alt
    # step up onto higher ground
    step = L.ground_at(world.px + 10)
    if world.on_ground and step is not None and step < world.py - 8:
        return replace(base, jump=True)
    return base

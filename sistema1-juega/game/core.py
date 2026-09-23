"""Deterministic 60 Hz simulation. No pygame here: the world can run headless, be cloned for
counterfactual rollouts (oracle) and be replayed frame-exactly for video."""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass

from . import level as L

FPS = 60
TIME_LIMIT = 4 * 60 * FPS
STALL_LIMIT = 45 * FPS   # no new progress for 45 s ends the run (stalled agent)
DIRS = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
DIR_VEC = {d: (math.cos(i * math.pi / 4), -math.sin(i * math.pi / 4)) for i, d in enumerate(DIRS)}

GRAVITY = 0.24
JUMP_V = -5.2
RUN = 1.6
STAND_H, CROUCH_H, BALL_H = 24, 12, 14


@dataclass(frozen=True)
class Action:
    move: int = 0          # -1 back, 0 stay, 1 advance
    jump: bool = False     # edge-triggered: jumps once per decision
    crouch: bool = False
    aim: str = "E"
    shoot: bool = False


IDLE = Action()


class Ent:
    __slots__ = ("kind", "x", "y", "vx", "vy", "hp", "t", "shooter", "dir", "alive", "w", "h", "base")

    def __init__(self, kind, x, y, hp=1, w=10, h=20, **kw):
        self.kind, self.x, self.y, self.hp, self.w, self.h = kind, float(x), float(y), hp, w, h
        self.vx = self.vy = 0.0
        self.t = 0
        self.shooter = kw.get("shooter", False)
        self.dir = kw.get("dir", "W")
        self.base = kw.get("base", float(y))
        self.alive = True

    def box(self):  # x = center, y = bottom
        return (self.x - self.w / 2, self.y - self.h, self.x + self.w / 2, self.y)


class Shot:
    __slots__ = ("x", "y", "vx", "vy", "r", "kind", "alive", "dmg")

    def __init__(self, x, y, vx, vy, r=2, kind="bullet", dmg=1):
        self.x, self.y, self.vx, self.vy, self.r, self.kind, self.dmg = x, y, vx, vy, r, kind, dmg
        self.alive = True


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class World:
    def __init__(self, seed: int = 1987):
        self.seed = seed
        self.rng = random.Random(seed)
        self.frame = 0
        self.cam = 0.0
        self.boss_lock = False
        # player
        self.px, self.py = 40.0, float(L.FLOOR)
        self.pvx = self.pvy = 0.0
        self.on_ground = True
        self.facing = 1
        self.crouching = False
        self.aim = "E"
        self.weapon = "N"
        self.shield = 0
        self.invuln = 90
        self.dead_timer = 0
        self.lives = 3
        self.fire_cd = 0
        self.jump_latch = False
        self.max_x = self.px
        self.score = 0
        self.kills = 0
        self.hits_taken = 0
        self.cleared = False
        self.over = False
        self.stalled = False
        self.progress_frame = 0
        self.end_timer = 0
        self.enemies: list[Ent] = []
        self.eshots: list[Shot] = []
        self.pshots: list[Shot] = []
        self.pickups = [Ent("pickup", x, y, w=12, h=12, dir=k) for x, y, k in L.PICKUPS]
        self.spawns = sorted(L.SPAWNS, key=lambda s: s[0])
        self.fx: list[list] = []            # [x, y, t, kind] visual effects (deterministic)
        self.events: list[tuple] = []       # (frame, name) for audio / highlights

    # ---------------------------------------------------------------- helpers
    def snapshot(self) -> "World":
        return copy.deepcopy(self)

    def pbox(self):
        h = CROUCH_H if self.crouching and self.on_ground else (BALL_H if not self.on_ground else STAND_H)
        top = self.py - h - (4 if not self.on_ground else 0)
        return (self.px - 5, top, self.px + 5, top + h)

    def gun(self):
        if self.crouching and self.on_ground and self.aim in ("E", "W", "NE", "NW", "SE", "SW"):
            return self.px + 7 * (1 if "E" in self.aim else -1), self.py - 7
        dx, dy = DIR_VEC[self.aim]
        return self.px + dx * 8, self.py - 16 + dy * 8

    def progress(self) -> float:
        if self.cleared:
            return 100.0
        return min(99.0, 100.0 * (self.max_x - 40) / (L.BOSS_X + 160 - 40))

    def _event(self, name):
        self.events.append((self.frame, name))

    # ---------------------------------------------------------------- step
    def step(self, a: Action) -> None:
        if self.over:
            return
        self.frame += 1
        if self.frame >= TIME_LIMIT:
            self.over = True
            return
        if self.cleared:
            self.end_timer += 1
            if self.end_timer > 150:
                self.over = True
            self._update_fx()
            return
        self._player(a)
        if self.over:
            return
        self._camera()
        self._spawn()
        self._enemies()
        self._shots()
        self._pickups()
        self._update_fx()

    def _player(self, a: Action):
        if self.dead_timer:
            self.dead_timer -= 1
            if self.dead_timer == 0:
                if self.lives <= 0:
                    self.over = True
                    return
                x = self.cam + 48
                while L.ground_at(x) is None:   # never respawn above a pit
                    x += 8
                self.px, self.py = x, 40.0
                self.pvx = self.pvy = 0.0
                self.on_ground = False
                self.invuln = 120
            return
        self.invuln = max(0, self.invuln - 1)
        self.shield = max(0, self.shield - 1)
        self.aim = a.aim
        if a.move:
            self.facing = a.move
        elif a.aim in ("E", "NE", "SE"):
            self.facing = 1
        elif a.aim in ("W", "NW", "SW"):
            self.facing = -1
        self.crouching = a.crouch and self.on_ground
        speed = 0 if self.crouching else RUN
        nx = self.px + a.move * speed
        # walls: cannot step up more than 8 px, cannot leave the camera, cannot pass the arena wall
        gy_next = L.ground_at(nx + 5 * a.move)
        if gy_next is not None and gy_next < self.py - 8 and self.on_ground:
            nx = self.px
        nx = max(self.cam + 6, min(nx, (L.BOSS_X + 200) if self.boss_lock else L.LEVEL_W - 8))
        self.px = nx
        # jump (edge-triggered by the decision)
        if a.jump and not self.jump_latch and self.on_ground and not self.crouching:
            self.pvy = JUMP_V
            self.on_ground = False
            self._event("jump")
        self.jump_latch = a.jump
        # gravity and landing
        self.pvy = min(self.pvy + GRAVITY, 5.0)
        ny = self.py + self.pvy
        landed = False
        gy = L.ground_at(self.px)
        if gy is not None and self.py <= gy + 1 and ny >= gy:
            ny, landed = gy, True
        if not landed and self.pvy >= 0:
            for x0, y0, w in L.PLATFORMS:
                if x0 <= self.px <= x0 + w and self.py <= y0 + 1 and ny >= y0:
                    ny, landed = y0, True
                    break
        self.py = ny
        if landed:
            self.pvy = 0.0
            self.on_ground = True
        else:
            self.on_ground = False
        if self.py > L.SCREEN_H + 30:
            self._die(force=True)
            return
        if self.px > self.max_x + 0.5:
            self.max_x = self.px
            self.progress_frame = self.frame
        elif self.frame - self.progress_frame > STALL_LIMIT and not self.boss_lock:
            self.stalled = self.over = True
            return
        # fire
        self.fire_cd = max(0, self.fire_cd - 1)
        limit = 6 if self.weapon == "R" else 4
        if a.shoot and self.fire_cd == 0 and len(self.pshots) < limit * (3 if self.weapon == "S" else 1):
            gx, gy2 = self.gun()
            base = math.atan2(-DIR_VEC[self.aim][1], DIR_VEC[self.aim][0])
            spread = (-0.26, 0.0, 0.26) if self.weapon == "S" else (0.0,)
            for d in spread:
                ang = base + d
                self.pshots.append(Shot(gx, gy2, 4.2 * math.cos(ang), -4.2 * math.sin(ang), r=2, kind="p"))
            self.fire_cd = 5 if self.weapon == "R" else 10
            self._event("shoot")

    def _die(self, force=False):
        if self.dead_timer or self.over or (not force and (self.invuln or self.shield)):
            return
        self.lives -= 1
        self.hits_taken += 1
        self.weapon = "N"
        self.dead_timer = 70
        self.fx.append([self.px, self.py - 12, 0, "boom"])
        self._event("die")

    def _camera(self):
        if self.boss_lock:
            return
        target = self.px - 96
        self.cam = max(self.cam, min(target, L.LEVEL_W - L.SCREEN_W))
        if self.cam >= L.BOSS_X:
            self.cam = float(L.BOSS_X)
            self.boss_lock = True
            self._spawn_boss()

    def _spawn(self):
        right = self.cam + L.SCREEN_W
        while self.spawns and right >= self.spawns[0][0]:
            _, kind, x, y, params = self.spawns.pop(0)
            self._make(kind, max(x, right + 6) if kind in ("soldier", "mine") else x, y, params)
        if not self.boss_lock and not self.dead_timer:
            for x0, x1, mean in L.REINFORCE:
                if x0 <= self.px <= x1 and self.rng.random() < 1.0 / mean:
                    self._make("soldier", right + 8, None, {"shooter": self.rng.random() < 0.35})

    def _make(self, kind, x, y, params):
        gy = L.ground_at(x) if y is None else y
        if gy is None:
            return
        if kind == "soldier":
            e = Ent("soldier", x, gy, hp=1, w=10, h=22, shooter=params.get("shooter", False))
            e.t = self.rng.randrange(40)
        elif kind == "turret":
            e = Ent("turret", x, gy, hp=4, w=16, h=16)
            e.t = self.rng.randrange(60)
        elif kind == "drone":
            e = Ent("drone", x, gy, hp=1, w=14, h=10, base=gy)
            e.t = self.rng.randrange(90)
        elif kind == "mine":
            e = Ent("mine", x, gy, hp=1, w=10, h=7)
        else:
            return
        self.enemies.append(e)

    def _spawn_boss(self):
        bx = L.BOSS_X
        self.enemies.append(Ent("cannon", bx + 228, 104, hp=10, w=18, h=14))
        self.enemies.append(Ent("cannon", bx + 228, 172, hp=10, w=18, h=14))
        self.enemies.append(Ent("core", bx + 236, 146, hp=24, w=22, h=30))
        self._event("boss")

    def _aimed(self, e, speed, oy=0.0, quantize=True):
        dx, dy = self.px - e.x, (self.py - 14) - (e.y - e.h / 2 + oy)
        ang = math.atan2(-dy, dx)
        if quantize:
            ang = round(ang / (math.pi / 4)) * (math.pi / 4)
        return speed * math.cos(ang), -speed * math.sin(ang)

    def _enemies(self):
        for e in self.enemies:
            if not e.alive:
                continue
            e.t += 1
            on_screen = self.cam - 8 < e.x < self.cam + L.SCREEN_W + 8
            if e.kind == "soldier":
                if e.shooter and on_screen and abs(e.x - self.px) < 190:
                    e.vx = 0.0
                    e.dir = "W" if self.px < e.x else "E"
                    if e.t % 95 == 0:
                        sgn = -1 if self.px < e.x else 1
                        self.eshots.append(Shot(e.x + 6 * sgn, e.y - 17, 2.0 * sgn, 0.0, r=2, kind="high"))
                else:
                    e.vx = -0.8 if self.px < e.x else 0.8
                    e.dir = "W" if e.vx < 0 else "E"
                nx = e.x + e.vx
                gy = L.ground_at(nx)
                if e.vy or gy is None:          # falling (into a pit, or off a ledge)
                    e.vy = min(e.vy + GRAVITY, 5)
                    e.y += e.vy
                    if gy is not None and e.y >= gy:
                        e.y, e.vy = gy, 0.0
                elif gy < e.y - 8:
                    nx = e.x                     # a step too tall: wait below it
                elif gy > e.y:
                    e.vy = 0.5                   # walked off a ledge
                else:
                    e.y = gy
                e.x = nx
            elif e.kind == "mine":
                if on_screen:
                    e.x += -0.9 if self.px < e.x else 0.9
                    gy = L.ground_at(e.x)
                    if gy is None:
                        e.y += 3
                    else:
                        e.y = gy
            elif e.kind == "turret":
                if on_screen:
                    vx, vy = self._aimed(e, 1.6)
                    ang = math.atan2(-vy, vx)
                    e.dir = DIRS[int(round(ang / (math.pi / 4))) % 8]
                    if e.t % 80 == 0:
                        gx, gy2 = e.x + DIR_VEC[e.dir][0] * 10, e.y - 8 + DIR_VEC[e.dir][1] * 10
                        self.eshots.append(Shot(gx, gy2, vx, vy, r=2, kind="aimed"))
            elif e.kind == "drone":
                e.x -= 0.7
                e.y = e.base + 18 * math.sin(e.t / 22.0)
                if on_screen and e.t % 110 == 0:
                    self.eshots.append(Shot(e.x, e.y + 2, 0.0, 1.6, r=2, kind="bomb"))
            elif e.kind == "cannon":
                if e.t % 70 == 0:
                    vx, vy = self._aimed(e, 1.8)
                    self.eshots.append(Shot(e.x - 10, e.y - 7, vx, vy, r=2, kind="aimed"))
            elif e.kind == "core":
                cannons = [c for c in self.enemies if c.kind == "cannon" and c.alive]
                if e.t % 110 == 0:
                    vx, vy = self._aimed(e, 1.5, quantize=False)
                    for d in (-0.3, 0.0, 0.3):
                        ang = math.atan2(-vy, vx) + d
                        self.eshots.append(Shot(e.x - 12, e.y - 15, 1.5 * math.cos(ang), -1.5 * math.sin(ang), r=3, kind="orb"))
                e.dir = "open" if not cannons else "shut"
            # contact damage
            if not self.dead_timer and _overlap(e.box(), self.pbox()) and e.kind in ("soldier", "mine", "drone"):
                self._die()
                if e.kind == "mine":
                    self._kill(e, score=False)
            if e.x < self.cam - 40 or e.y > L.SCREEN_H + 40:
                e.alive = False
        self.enemies = [e for e in self.enemies if e.alive]

    def _kill(self, e, score=True):
        e.alive = False
        self.fx.append([e.x, e.y - e.h / 2, 0, "boom"])
        self._event("explode")
        if score:
            self.kills += 1
            self.score += {"soldier": 100, "drone": 200, "turret": 300, "mine": 50, "cannon": 500, "core": 5000}[e.kind]
        if e.kind == "core":
            self.cleared = True
            for c in self.enemies:
                if c.alive and c is not e:
                    c.alive = False
            self.eshots.clear()
            self._event("clear")

    def _shots(self):
        for s in self.pshots:
            s.x += s.vx
            s.y += s.vy
            if not (self.cam - 8 < s.x < self.cam + L.SCREEN_W + 8 and -8 < s.y < L.SCREEN_H + 8):
                s.alive = False
                continue
            for e in self.enemies:
                if not e.alive or e.kind == "pickup":
                    continue
                b = e.box()
                if b[0] - s.r < s.x < b[2] + s.r and b[1] - s.r < s.y < b[3] + s.r:
                    s.alive = False
                    if e.kind == "core" and e.dir != "open":
                        self.fx.append([s.x, s.y, 0, "spark"])
                        break
                    e.hp -= 1
                    self.fx.append([s.x, s.y, 0, "spark"])
                    if e.hp <= 0:
                        self._kill(e)
                    else:
                        self._event("hit")
                    break
        self.pshots = [s for s in self.pshots if s.alive]
        pb = self.pbox()
        for s in self.eshots:
            s.x += s.vx
            s.y += s.vy
            if not (self.cam - 16 < s.x < self.cam + L.SCREEN_W + 16 and -16 < s.y < L.SCREEN_H + 16):
                s.alive = False
                continue
            gy = L.ground_at(s.x)
            if s.kind == "bomb" and gy is not None and s.y >= gy:
                s.alive = False
                self.fx.append([s.x, gy, 0, "spark"])
                continue
            if not self.dead_timer and pb[0] - s.r < s.x < pb[2] + s.r and pb[1] - s.r < s.y < pb[3] + s.r:
                s.alive = False
                if self.shield:
                    self.fx.append([s.x, s.y, 0, "spark"])
                else:
                    self._die()
        self.eshots = [s for s in self.eshots if s.alive]

    def _pickups(self):
        pb = self.pbox()
        for p in self.pickups:
            if p.alive and not self.dead_timer and _overlap(p.box(), pb):
                p.alive = False
                if p.dir == "B":
                    self.shield = 600
                else:
                    self.weapon = p.dir
                self.score += 500
                self._event("pickup")
        self.pickups = [p for p in self.pickups if p.alive]

    def _update_fx(self):
        for f in self.fx:
            f[2] += 1
        self.fx = [f for f in self.fx if f[2] < (24 if f[3] == "boom" else 8)]

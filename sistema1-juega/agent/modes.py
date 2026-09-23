"""Play the game with System One (real time or turns) or a baseline, log every decision,
then label decisions with the simulator oracle.

Frame contract (shared by live play and replay): at frame F, decisions that arrived are applied
first (the jump latch is re-armed), then a new request may be issued with describe(world at F),
then the world steps to F+1.
"""

from __future__ import annotations

import json
import queue
import random
import threading
import time
from dataclasses import asdict
from pathlib import Path

from game.core import FPS, IDLE, Action, World
from game.describe import describe

from .client import Client, parse_answers
from .oracle import heuristic_action, labels
from .policy import POLICY, decide
from .questions import KEYS, VARIANTS, request_body

ROOT = Path(__file__).resolve().parents[1]


def apply(world: World, action: Action) -> Action:
    world.jump_latch = False  # a fresh decision may jump again
    return action


def _act(a: Action) -> dict:
    return asdict(a)


def server_info() -> dict:
    """/health of the System One server (which model played), or {} for offline baselines."""
    import os
    import urllib.request

    try:
        url = os.environ.get("JEV_BASE_URL", "http://127.0.0.1:8765").rstrip("/") + "/health"
        return json.load(urllib.request.urlopen(url, timeout=3))
    except Exception:  # noqa: BLE001
        return {}


def _finish(world: World, meta: dict, decisions: list, timeline: list, out: Path) -> dict:
    meta.setdefault("policy", POLICY)
    if meta.get("mode") in ("realtime", "turns"):
        meta.setdefault("server", server_info())
    meta.update(frames=world.frame, timeline=timeline, events=world.events, result={
        "progress": round(world.progress(), 2), "score": world.score, "lives": max(0, world.lives),
        "kills": world.kills, "deaths": world.hits_taken, "cleared": world.cleared, "stalled": world.stalled,
        "seconds": round(world.frame / FPS, 2)})
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out.with_suffix(".jsonl"), "w") as f:
        for d in decisions:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    out.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    return meta


def _ask(client: Client, state: str, variant: str, factor: float = 1.0, gate: bool = True) -> dict:
    body = request_body(state, variant)
    raw, rtt, server_ms = client.system_one(body)
    ans = parse_answers(raw, {k: body["questions"][k] for k in KEYS})
    dec = decide(ans, factor=factor) if gate else decide(ans, low=-1.0, factor=factor)
    return {"raw": raw, "rtt_ms": round(rtt, 2), "server_ms": server_ms, "action": _act(dec.action),
            "tag": dec.tag, "tags": dec.tags, "conf": round(dec.confidence, 4), "danger": round(dec.danger, 4),
            "input_tokens": raw["usage"]["input_tokens"]}


def run_realtime(seed: int, variant: str, out: Path, max_inflight: int = 1, verbose: bool = True,
                 max_frames: int | None = None, factor: float = 1.0, asker=None, mode: str = "realtime",
                 guard=None) -> dict:
    """60 FPS wall clock, never paused. The current action is held until the next answer arrives."""
    asker = asker or _ask
    world = World(seed)
    lang = VARIANTS[variant]["lang"]
    jobs: queue.Queue = queue.Queue()
    results: queue.Queue = queue.Queue()

    def worker():
        client = Client()
        while True:
            job = jobs.get()
            if job is None:
                return
            i, frame, state = job
            try:
                rec = asker(client, state, variant, factor)
            except Exception as error:  # noqa: BLE001 -- a failed call is logged as a fallback
                rec = {"error": str(error), "action": _act(Action(aim="E", shoot=True)), "tag": "FALLBACK",
                       "tags": {}, "conf": 0.0, "danger": 0.0, "rtt_ms": None, "server_ms": None, "input_tokens": 0}
            rec.update(i=i, req_frame=frame, state=state, variant=variant)
            results.put(rec)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max_inflight)]
    for t in threads:
        t.start()
    current, inflight, n = IDLE, 0, 0
    decisions, timeline = [], []
    late = 0
    comp = VARIANTS[variant].get("lookahead", False)
    lat_frames = 24  # running median of observed latency (frames), used for compensation
    t0 = time.perf_counter()
    while not world.over and (max_frames is None or world.frame < max_frames):
        while True:
            try:
                rec = results.get_nowait()
            except queue.Empty:
                break
            inflight -= 1
            rec["arr_frame"] = world.frame
            current = apply(world, Action(**rec["action"]))
            timeline.append([world.frame, rec["action"]])
            decisions.append(rec)
            recent = sorted(d["arr_frame"] - d["req_frame"] for d in decisions[-9:])
            lat_frames = recent[len(recent) // 2]
        if inflight < max_inflight and not world.dead_timer:
            ahead = lat_frames if comp else 0
            jobs.put((n, world.frame, describe(world, lang, ahead, current.move * 1.6 if ahead else 0.0)))
            n += 1
            inflight += 1
        world.step(current)
        target = t0 + world.frame / FPS
        now = time.perf_counter()
        if now < target:
            time.sleep(target - now)
        elif now - target > 1 / FPS:
            late += 1
        if guard is not None and world.frame % 60 == 0 and guard.poll():
            break
        if verbose and world.frame % 600 == 0:
            print(f"  [{world.frame / FPS:5.1f}s] progreso {world.progress():5.1f}% vidas {world.lives} "
                  f"decisiones {len(decisions)}", flush=True)
    for _ in threads:
        jobs.put(None)
    decisions.sort(key=lambda d: d["i"])
    meta = {"mode": mode, "seed": seed, "variant": variant, "max_inflight": max_inflight, "factor": factor,
            "late_frames": late, "wall_s": round(time.perf_counter() - t0, 2)}
    return _finish(world, meta, decisions, timeline, out)


def run_turns(seed: int, variant: str, out: Path, every: int = 8, idle_s: float = 0.05, factor: float = 1.0,
              gate: bool = True, asker=None, mode: str = "turns", guard=None) -> dict:
    """The world waits for every answer (quality without time pressure). idle_s caps GPU duty cycle."""
    asker = asker or _ask
    world, client = World(seed), Client()
    lang = VARIANTS[variant]["lang"]
    current, decisions, timeline = IDLE, [], []
    while not world.over:
        if world.frame % every == 0 and not world.dead_timer:
            state = describe(world, lang)
            rec = asker(client, state, variant, factor, gate)
            rec.update(i=len(decisions), req_frame=world.frame, arr_frame=world.frame, state=state, variant=variant)
            current = apply(world, Action(**rec["action"]))
            timeline.append([world.frame, rec["action"]])
            decisions.append(rec)
            time.sleep(idle_s)
            if guard is not None and guard.poll():
                break
        world.step(current)
    meta = {"mode": mode, "seed": seed, "variant": variant, "every": every, "factor": factor, "gate": gate}
    return _finish(world, meta, decisions, timeline, out)


def run_baseline(seed: int, kind: str, out: Path, every: int = 8, run: int = 0) -> dict:
    """kind = random (uniform over the same action space) or heuristic (oracle bot, reference only)."""
    world = World(seed)
    rng = random.Random(seed * 7919 + 1 + run)  # a different random agent per run, same level
    current, decisions, timeline = IDLE, [], []
    while not world.over:
        if world.frame % every == 0:
            if kind == "random":
                a = Action(move=rng.choice((-1, 0, 1)), jump=rng.random() < 0.5, crouch=rng.random() < 0.5,
                           aim=rng.choice(("E", "NE", "N", "NW", "W", "SW", "S", "SE")), shoot=rng.random() < 0.5)
            else:
                a = heuristic_action(world)
            current = apply(world, a)
            timeline.append([world.frame, _act(a)])
            decisions.append({"i": len(decisions), "req_frame": world.frame, "arr_frame": world.frame,
                              "action": _act(a), "tag": "ACTUA", "conf": None})
        world.step(current)
    return _finish(world, {"mode": kind, "seed": seed, "every": every, "run": run}, decisions, timeline, out)


def replay(meta: dict, on_frame=None) -> World:
    """Re-simulate a logged run frame-exactly. on_frame(world, applied_this_frame) is called before each step."""
    world = World(meta["seed"])
    tl = meta["timeline"]
    k, current = 0, IDLE
    while not world.over and world.frame < meta["frames"]:
        applied = []
        while k < len(tl) and tl[k][0] == world.frame:
            rearm = tl[k][2] if len(tl[k]) > 2 else True
            current = apply(world, Action(**tl[k][1])) if rearm else Action(**tl[k][1])
            applied.append(k)
            k += 1
        if on_frame:
            on_frame(world, applied, current)
        world.step(current)
    return world


def label_run(path: Path) -> dict:
    """Add oracle labels (at the request frame) and 30-frame outcomes (after arrival) to a logged run."""
    meta = json.loads(path.with_suffix(".meta.json").read_text())
    decisions = [json.loads(l) for l in open(path.with_suffix(".jsonl"))]
    by_req: dict[int, list] = {}
    for d in decisions:
        by_req.setdefault(d["req_frame"], []).append(d)
    hits, kills = {}, {}

    def on_frame(world, applied, current):
        hits[world.frame], kills[world.frame] = world.hits_taken, world.kills
        for d in by_req.get(world.frame, []):
            d["labels"] = labels(world, current)

    end = replay(meta, on_frame)
    if end.frame != meta["frames"] or end.score != meta["result"]["score"]:
        raise RuntimeError(f"replay diverged: frames {end.frame} vs {meta['frames']}, score {end.score} vs {meta['result']['score']}")
    last = end.frame
    hits[last], kills[last] = end.hits_taken, end.kills
    for d in decisions:
        a = d.get("arr_frame", d["req_frame"])
        b = min(a + 30, last)
        d["outcome"] = {"hit": hits.get(b, hits[last]) > hits.get(a, 0), "kills": kills.get(b, kills[last]) - kills.get(a, 0)}
    with open(path.with_suffix(".jsonl"), "w") as f:
        for d in decisions:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    meta["labeled"] = True
    path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    return meta

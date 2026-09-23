import hashlib
import json
from pathlib import Path

from agent.client import parse_answers
from agent.modes import replay
from agent.oracle import labels, line_of_fire
from agent.policy import decide, retemper
from agent.questions import KEYS, VARIANTS, request_body
from game.core import Action, World
from game.describe import describe

ROOT = Path(__file__).resolve().parents[1]


def _run(seed, n=900):
    w, h = World(seed), hashlib.sha1()
    for f in range(n):
        w.step(Action(move=1, jump=f % 45 < 2, aim="E" if f % 60 < 30 else "NE", shoot=True))
        h.update(f"{w.px:.4f}{w.py:.4f}{w.score}{len(w.enemies)}{len(w.eshots)}".encode())
    return w, h.hexdigest()


def test_determinism():
    assert _run(1987)[1] == _run(1987)[1]
    assert _run(1987)[1] != _run(7)[1]


def test_fixture_schema_roundtrip():
    fx = json.loads((ROOT / "fixtures" / "systemone_6q.json").read_text())
    ans = parse_answers(fx["response"], {k: fx["request"]["questions"][k] for k in KEYS})
    assert set(ans) == set(KEYS)
    d = decide(ans)
    assert d.tag in ("ACTUA", "DUDA", "FALLBACK") and 0 <= d.danger <= 1


def test_one_request_six_questions():
    for v in VARIANTS:
        body = request_body("estado", v)
        assert list(body["questions"]) == list(KEYS)
        assert set(body) == {"state", "model", "questions"}


def test_retemper_preserves_argmax():
    fx = json.loads((ROOT / "fixtures" / "systemone_6q.json").read_text())
    ans = parse_answers(fx["response"], {k: fx["request"]["questions"][k] for k in KEYS})
    r = retemper(ans, 1.55)
    assert r["aim"].value == ans["aim"].value
    assert abs(sum(r["aim"].probabilities.values()) - 1) < 1e-9


def test_oracle_shoot_matches_geometry():
    w = World(1987)
    for _ in range(400):
        w.step(Action(move=1, aim="E", shoot=False))
    lof = line_of_fire(w)
    for d, (dist, kind) in lof.items():
        assert dist > 0 and kind
    lab = labels(w, Action(move=1))
    assert lab["aligned"] == bool(lof)


def test_replay_matches_log():
    paths = [p for p in sorted((ROOT / "runs").rglob("*.meta.json")) if "_obsolete" not in p.parts]
    for meta_path in paths[:4]:
        meta = json.loads(meta_path.read_text())
        end = replay(meta)
        assert end.frame == meta["frames"] and end.score == meta["result"]["score"]


def test_state_is_compact_and_deterministic():
    w = World(1987)
    for _ in range(300):
        w.step(Action(move=1, shoot=True))
    assert describe(w) == describe(w.snapshot())
    assert len(describe(w)) < 700

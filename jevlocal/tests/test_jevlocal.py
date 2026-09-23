"""Unit tests for request planning plus GPU integration tests (skipped without the GGUF)."""

import math
import os
from pathlib import Path

import pytest

from jevlocal.prompts import RequestError, SYSTEM_LETTER, answers, confidence, plan_request

GGUF = os.environ.get("JEVLOCAL_GGUF") or str(
    Path(__file__).resolve().parents[2] / "models" / "gguf" / "Qwen_Qwen3.5-4B-Q8_0.gguf")


def body(questions, state="Help! My payouts have been failing for 3 days."):
    return {"state": state, "model": "jev-latest", "questions": questions}


CHOICE = {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "Payments", "technical": None}}


def test_confidence_matches_typesafe_formula():
    assert confidence([1 / 3] * 3) == 0
    assert confidence([1.0, 0.0]) == 1
    assert math.isclose(confidence([0.9, 0.06, 0.04]), (3 * 0.9 - 1) / 2)


@pytest.mark.parametrize("bad", [
    {"model": "x", "questions": {"a": CHOICE}},
    body({}),
    body({"a": {"type": "choice", "instructions": "?", "criteria": {"only": None}}}),
    body({"a": {"type": "score", "instructions": "?", "criteria": ["one"] * 11}}),
    body({"a": {"type": "noul", "instructions": "?", "criteria": {"maybe": "x"}}}),
    body({"a": {"type": "vote", "instructions": "?"}}),
    body({"a": CHOICE}, state="   "),
])
def test_validation_rejects(bad):
    with pytest.raises(RequestError):
        plan_request(bad)


def test_letter_prompt_matches_semif_template():
    plan = plan_request(body({"a": CHOICE}), option_style="desc")
    text = plan.readouts[0].text
    assert text.startswith(f"<|im_start|>system\n{SYSTEM_LETTER}<|im_end|>\n<|im_start|>user\n{{\"evidence\": ")
    assert text.endswith("<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")
    assert '"description": "Payments"' in text and '"description": "technical"' in text


def test_codes_beyond_26_options_and_debias():
    many = {"type": "choice", "instructions": "?", "criteria": {f"o{i}": None for i in range(120)}}
    plan = plan_request(body({"m": many, "n": {"type": "noul", "instructions": "?"}}), debias="all")
    coded = [r for r in plan.readouts if r.question == "m"]
    assert [r.labels[:2] for r in coded] == [["000", "001"]] * 2 and coded[1].order[0] == 119
    assert len(plan.readouts) == 4


def test_answer_shapes():
    plan = plan_request(body({
        "c": CHOICE, "n": {"type": "noul", "instructions": "?"},
        "s": {"type": "score", "instructions": "?", "criteria": ["low", {"level": "high"}]}}))
    for r in plan.readouts:
        r.probabilities = [0.75, 0.25]
    out = answers(plan)
    assert out["c"] == {"type": "choice", "choice": "billing", "probabilities": {"billing": 0.75, "technical": 0.25},
                        "confidence": 0.5}
    assert out["n"] == {"type": "noul", "noul": 0.75}
    assert out["s"]["score"] == 0.25 and out["s"]["legend"] == {"0": "low", "1": '{"level": "high"}'}


gpu = pytest.mark.skipif(not Path(GGUF).is_file(), reason="GGUF not available")


@pytest.fixture(scope="module")
def engine():
    from jevlocal.engine import Engine

    e = Engine(GGUF, n_seq_max=4, n_ctx=16384)  # few sequences: exercises deferral and re-rooting
    yield e
    e.close()


def probs(engine, b, **kw):
    plan = plan_request(b, **kw)
    engine.score(plan.readouts)
    return plan, answers(plan)


@gpu
def test_example_answers(engine):
    _, out = probs(engine, body({"d": {"type": "choice", "instructions": "Which team should handle this?", "criteria": {
        "billing": "Payments, invoicing, refunds", "technical": "Bugs, outages, integrations",
        "sales": "Pricing, upgrades, new accounts"}}}))
    assert out["d"]["choice"] == "billing"
    assert math.isclose(sum(out["d"]["probabilities"].values()), 1, abs_tol=1e-5)


@gpu
def test_batched_matches_single_within_noise(engine):
    q = {"type": "noul", "instructions": "Does this convey urgency?"}
    _, alone = probs(engine, body({"u": q}))
    _, together = probs(engine, body({"u": q, "c": CHOICE, "s": {"type": "score", "instructions": "Anger?",
                                                                  "criteria": ["calm", "upset", "furious"]}}))
    assert abs(alone["u"]["noul"] - together["u"]["noul"]) < 0.05


@gpu
def test_many_states_and_questions_with_four_sequences(engine):
    plans = [plan_request(body({f"q{j}": CHOICE for j in range(3)}, state=f"Ticket {i}: refund please " * (i + 1)))
             for i in range(5)]
    engine.score([r for p in plans for r in p.readouts])
    for p in plans:
        for a in answers(p).values():
            assert a["choice"] == "billing"
    assert len(engine.pool) == engine.n_seq_max - 1  # no leaked sequences


@gpu
def test_three_digit_codes(engine):
    criteria = {f"city_{i}": f"City number {i}" for i in range(130)}
    _, out = probs(engine, body({"c": {"type": "choice", "instructions": "Which city does the user want?",
                                       "criteria": criteria}}, state="Book me a flight to city number 117."))
    assert math.isclose(sum(out["c"]["probabilities"].values()), 1, abs_tol=1e-4)
    assert out["c"]["choice"] == "city_117"

"""Jev request -> scored prompts, and scored slots -> Jev answers.

Two prompt profiles over the same frozen model:
  semif   SemIf `direct-options-v1`: one JSON object {evidence, criterion, options[letter, description]}
  reflex  reflex `stable` markdown layout: # Evidence / # Criterion / # Options, "A. key: description"

Options beyond 26 use fixed-width digit codes scored digit by digit
(P(code) = prod P(digit | previous digits)).
"""

from __future__ import annotations

import json
import math
import random
import string
from dataclasses import dataclass, field

LETTERS = string.ascii_uppercase  # 26 single-token labels
MAX_CHOICE_OPTIONS = 255
MAX_SCORE_LEVELS = 10
PROFILES = ("semif", "reflex")

SYSTEM_LETTER = (
    "Apply the supplied criterion to the supplied evidence. Choose exactly one listed option. "
    "Respond with only its uppercase letter, with no explanation or reasoning."
)
SYSTEM_CODE = (
    "Apply the supplied criterion to the supplied evidence. Choose exactly one listed option. "
    "Respond with only its numeric code, with no explanation or reasoning."
)
SYSTEM_REFLEX = (
    "You are a System One decision model. You read the State and answer each Question "
    "by choosing exactly one of the listed options. You never explain. You answer with "
    "the single option label only."
)
# Chat formats. "qwen": ChatML with an empty <think> block = no reasoning (System 1). "gemma": Gemma turns
# (no system role, so the instruction opens the user turn). Selected once per server with set_chat().
CHATS = {
    "qwen": {"system": "<|im_start|>system\n{system}<|im_end|>\n", "user": "<|im_start|>user\n",
             "assistant": "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"},
    # Gemma 4 canonical template rendered with enable_thinking=False (checked against the GGUF's own template)
    "gemma": {"system": "<bos><|turn>system\n{system}<turn|>\n", "user": "<|turn>user\n",
              "assistant": "<turn|>\n<|turn>model\n"},
}
CHAT = "qwen"
USER_OPEN = CHATS[CHAT]["user"]
ASSISTANT_OPEN = CHATS[CHAT]["assistant"]


def set_chat(name: str, spec: dict | None = None) -> None:
    """Switch the chat format for every prompt built afterwards (one model per server)."""
    global CHAT, USER_OPEN, ASSISTANT_OPEN
    if spec:
        CHATS[name] = spec
    CHAT = name
    USER_OPEN = CHATS[name]["user"]
    ASSISTANT_OPEN = CHATS[name]["assistant"]


def system_block(system: str) -> str:
    return CHATS[CHAT]["system"].format(system=system)


def template_text(profile: str = "semif") -> str:
    """Constant text that precedes every state; kept resident on the GPU."""
    if profile == "reflex":
        return system_block(SYSTEM_REFLEX) + USER_OPEN + "# Evidence\n"
    return system_block(SYSTEM_LETTER) + USER_OPEN + '{"evidence": '


class RequestError(ValueError):
    """Validation failure reported as HTTP 422."""


@dataclass
class Readout:
    """One scored prompt: the options it lists, in the order they are shown."""

    question: str
    group: str  # text shared by every readout over the same state (branch point)
    text: str
    labels: list[str]  # label shown for each displayed option ("A" or "007")
    order: list[int]  # displayed position -> canonical option index
    probabilities: list[float] = field(default_factory=list)  # filled by the engine, canonical order
    charged: int = 0  # prompt tokens billed to this readout (a shared state is billed once)


def _labels(count: int) -> tuple[list[str], bool]:
    if count <= len(LETTERS):
        return list(LETTERS[:count]), False
    width = len(str(count - 1))
    return [str(i).zfill(width) for i in range(count)], True


def _render_semif(state, instructions, shown: list, labels: list[str], coded: bool, kind: str) -> tuple[str, str]:
    key = "code" if coded else "letter"
    payload = {
        "evidence": state,
        "criterion": instructions,
        "options": [{key: label, "description": d} for label, d in zip(labels, shown)],
    }
    system = SYSTEM_CODE if coded else SYSTEM_LETTER
    text = system_block(system) + USER_OPEN + json.dumps(payload, ensure_ascii=False) + ASSISTANT_OPEN
    return text.split(', "criterion": ', 1)[0], text


def _plain(x) -> str:
    return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, indent=2)


def _render_reflex(state, instructions, shown: list, labels: list[str], coded: bool, kind: str) -> tuple[str, str]:
    group = template_text("reflex") + _plain(state) + "\n\n"
    if coded:
        ask = "Respond with only the number of the best option."
    elif kind == "score":
        ask = "Respond with only the letter of the level that best matches."
    else:
        ask = "Respond with only the letter of the best option."
    lines = [f"# Criterion\n{_plain(instructions)}\n", "# Options"]
    lines += [f"{label}. {_plain(d)}" for label, d in zip(labels, shown)]
    lines.append(f"\n{ask}\n")
    return group, group + "\n".join(lines) + ASSISTANT_OPEN


def _reflex_orders(qid: str, count: int, permutations: int) -> list[list[int]]:
    """reflex `distinct_orders`: identity first, then distinct shuffles from Random(f"0:{qid}")."""
    keys = list(range(count))
    rng = random.Random(f"0:{qid}")
    orders, seen = [list(keys)], {tuple(keys)}
    limit = min(permutations, math.factorial(count)) if count <= 8 else permutations
    tries = 0
    while len(orders) < limit and tries < 50 * limit:
        tries += 1
        order = list(keys)
        rng.shuffle(order)
        if tuple(order) not in seen:
            seen.add(tuple(order))
            orders.append(order)
    return orders


def _readouts(qid: str, state, instructions, descriptions: list, two_orders: bool, profile: str, kind: str) -> list[Readout]:
    labels, coded = _labels(len(descriptions))
    if profile == "reflex":
        orders = _reflex_orders(qid, len(descriptions), 2 if two_orders else 1)
        if kind == "noul" and two_orders:
            orders = [[0, 1], [1, 0]]
        render = _render_reflex
    else:
        orders = [list(range(len(descriptions)))]
        if two_orders:
            orders.append(orders[0][::-1])
        render = _render_semif
    out = []
    for order in orders:
        group, text = render(state, instructions, [descriptions[i] for i in order], labels, coded, kind)
        out.append(Readout(qid, group, text, labels, order))
    return out


def _is_json(value, kinds=(str, dict, list)) -> bool:
    if not isinstance(value, kinds):
        return False
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _describe(key: str, value, style: str = "key"):
    """Option text. style="key" prefixes the option key; "desc" sends the rubric alone (SemIf parity)."""
    if value is None or value == "":
        return key
    if isinstance(value, str):
        return f"{key}: {value}" if style == "key" else value
    return {"option": key, "description": value}


@dataclass
class Plan:
    state: object
    questions: dict
    readouts: list[Readout]


def plan_request(body: dict, debias: str = "none", option_style: str = "key", profile: str = "semif") -> Plan:
    """Validate a /v1/systemone body and expand it into scored prompts."""
    if not isinstance(body, dict):
        raise RequestError("body must be a JSON object")
    for key in ("state", "model", "questions"):
        if key not in body:
            raise RequestError(f"missing required field: {key}")
    state = body["state"]
    if not _is_json(state) or (isinstance(state, str) and not state.strip()) or state in ({}, []):
        raise RequestError("state must be a nonempty string, object, or array")
    if not isinstance(body["model"], str) or not body["model"]:
        raise RequestError("model must be a nonempty string")
    questions = body["questions"]
    if not isinstance(questions, dict) or not questions:
        raise RequestError("questions must be a nonempty map")
    if profile not in PROFILES:
        raise ValueError(f"unknown prompt profile {profile!r}")
    readouts: list[Readout] = []
    for qid, q in questions.items():
        where = f"questions.{qid}"
        if not isinstance(q, dict):
            raise RequestError(f"{where} must be an object")
        kind = q.get("type")
        instructions = q.get("instructions")
        if not _is_json(instructions) or (isinstance(instructions, str) and not instructions.strip()):
            raise RequestError(f"{where}.instructions must be a nonempty string, object, or array")
        criteria = q.get("criteria")
        if kind == "noul":
            if criteria is not None and not isinstance(criteria, dict):
                raise RequestError(f"{where}.criteria must be an object with optional true/false")
            criteria = criteria or {}
            extra = set(criteria) - {"true", "false"}
            if extra:
                raise RequestError(f"{where}.criteria has unknown keys: {sorted(extra)}")
            yes = criteria.get("true")
            no = criteria.get("false")
            if profile == "reflex":
                descriptions = ["yes: " + (_plain(yes) if yes else "The statement is true."),
                                "no: " + (_plain(no) if no else "The statement is false.")]
            else:
                descriptions = [_describe("Yes", yes), _describe("No", no)]
            readouts += _readouts(qid, state, instructions, descriptions, debias in ("noul", "all"), profile, kind)
        elif kind == "choice":
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= MAX_CHOICE_OPTIONS:
                raise RequestError(f"{where}.criteria must map 2-{MAX_CHOICE_OPTIONS} options to descriptions")
            for option, value in criteria.items():
                if value is not None and not _is_json(value):
                    raise RequestError(f"{where}.criteria.{option} must be a string, object, array, or null")
            descriptions = [_describe(k, v, option_style) for k, v in criteria.items()]
            readouts += _readouts(qid, state, instructions, descriptions, debias == "all", profile, kind)
        elif kind == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= MAX_SCORE_LEVELS:
                raise RequestError(f"{where}.criteria must be an array of 2-{MAX_SCORE_LEVELS} levels")
            if not all(_is_json(level) for level in criteria):
                raise RequestError(f"{where}.criteria levels must be strings, objects, or arrays")
            levels = list(criteria)
            if profile == "reflex":
                levels = [f"(level {i} of {len(levels) - 1}) {_plain(lv)}" for i, lv in enumerate(levels)]
            readouts += _readouts(qid, state, instructions, levels, debias == "all", profile, kind)
        else:
            raise RequestError(f"{where}.type must be one of noul, choice, score")
    return Plan(state, questions, readouts)


def confidence(probabilities: list[float]) -> float:
    """TypeSafe's published statistic: (K * p_max - 1) / (K - 1), clamped to [0, 1]."""
    k = len(probabilities)
    return max(0.0, min(1.0, (k * max(probabilities) - 1) / (k - 1)))


def _r(x: float) -> float:
    return round(float(x), 6)


def answers(plan: Plan) -> dict:
    """Average each question's readouts (order debiasing) and build Jev-shaped answers."""
    grouped: dict[str, list[list[float]]] = {}
    for readout in plan.readouts:
        grouped.setdefault(readout.question, []).append(readout.probabilities)
    out = {}
    for qid, q in plan.questions.items():
        runs = grouped[qid]
        probs = [sum(run[i] for run in runs) / len(runs) for i in range(len(runs[0]))]
        kind = q["type"]
        if kind == "noul":
            out[qid] = {"type": "noul", "noul": _r(probs[0])}
        elif kind == "choice":
            keys = list(q["criteria"])
            best = max(range(len(keys)), key=probs.__getitem__)
            out[qid] = {
                "type": "choice",
                "choice": keys[best],
                "probabilities": {k: _r(p) for k, p in zip(keys, probs)},
                "confidence": _r(confidence(probs)),
            }
        else:
            levels = q["criteria"]
            out[qid] = {
                "type": "score",
                "score": _r(sum(i * p for i, p in enumerate(probs))),
                "legend": {str(i): lv if isinstance(lv, str) else json.dumps(lv, ensure_ascii=False) for i, lv in enumerate(levels)},
                "probabilities": {str(i): _r(p) for i, p in enumerate(probs)},
                "confidence": _r(confidence(probs)),
            }
    return out

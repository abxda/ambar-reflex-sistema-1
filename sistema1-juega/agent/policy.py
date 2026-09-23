"""Answers -> game action, gated by calibrated confidence (policy v2).

The API only defines `confidence` for choice/score answers, so the thresholds gate the two choices:
  move, aim: confidence > HIGH act (ACTUA); LOW..HIGH act, marked DUDA; < LOW conservative default
             (move: stay; aim: straight ahead and keep shooting), marked FALLBACK.
  jump, crouch, shoot (noul): act when P(yes) >= 0.5.
The decision's tag is the worst of its two choice tags (danger only feeds the HUD).

Policy v1 also gated nouls with |2p - 1| (our own extension, not in the API). It refused jumps at
p = 0.53-0.65 and the agent fell into pits or stalled below steps: kept as POLICY="v1" for the record.
"""

from __future__ import annotations

from dataclasses import dataclass

from game.core import Action

HIGH, LOW = 0.9, 0.5
MOVE = {"avanzar": 1, "retroceder": -1, "quieto": 0}
CONSERVATIVE = {"move": 0, "aim": "E", "shoot": True, "jump": False, "crouch": False}
CONTROL = ("move", "jump", "crouch", "aim", "shoot")
GATED = ("move", "aim")
POLICY = "v2"
RANK = {"ACTUA": 0, "DUDA": 1, "FALLBACK": 2}


@dataclass
class Decision:
    action: Action
    tag: str
    tags: dict
    confidence: float  # min over control components
    danger: float      # score normalised to 0..1


def retemper(ans: dict, factor: float) -> dict:
    """Exact recalibration of server probabilities: p' ∝ p ** factor, factor = T_server / T_new."""
    if factor == 1.0:
        return ans
    out = {}
    for k, a in ans.items():
        if a.type == "noul":
            y, n = a.value ** factor, (1 - a.value) ** factor
            p = y / (y + n)
            out[k] = type(a)("noul", p, None, abs(2 * p - 1))
        else:
            w = {o: max(p, 1e-12) ** factor for o, p in a.probabilities.items()}
            z = sum(w.values())
            probs = {o: v / z for o, v in w.items()}
            kk = len(probs)
            conf = max(0.0, min(1.0, (kk * max(probs.values()) - 1) / (kk - 1)))
            value = a.value if a.type == "choice" else sum(int(o) * p for o, p in probs.items())
            out[k] = type(a)(a.type, value, probs, conf)
    return out


def decide(ans: dict, high: float = HIGH, low: float = LOW, factor: float = 1.0, policy: str = POLICY) -> Decision:
    ans = retemper(ans, factor)
    val, tags = {}, {}
    gated = CONTROL if policy == "v1" else GATED
    for k in CONTROL:
        a = ans[k]
        if a.type == "noul":
            v = a.value >= 0.5
        elif k == "move":
            v = MOVE[a.value]
        else:
            v = a.value
        if k not in gated:
            val[k] = v
        elif a.confidence < low:
            val[k], tags[k] = CONSERVATIVE[k], "FALLBACK"
            if k == "aim":
                val["shoot_fallback"] = True
        else:
            val[k], tags[k] = v, ("ACTUA" if a.confidence > high else "DUDA")
    if val.pop("shoot_fallback", False):
        val["shoot"] = True  # conservative default: aim straight ahead and keep shooting
    tag = max(tags.values(), key=RANK.__getitem__)
    danger = ans["danger"].value / (len(ans["danger"].probabilities) - 1)
    act = Action(move=val["move"], jump=val["jump"], crouch=val["crouch"], aim=val["aim"], shoot=val["shoot"])
    return Decision(act, tag, tags, min(ans[k].confidence for k in gated), danger)

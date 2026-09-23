"""System 2 baseline: a generative LLM (OpenAI-compatible chat API, e.g. Ollama qwen3.5:4b) that must
write JSON with the same six decisions. Same questions as variant B, so only the readout differs:
generated text + parsing versus typed probabilities. Parse/schema errors become FALLBACK."""

from __future__ import annotations

import http.client
import json
import os
import threading
import time
from dataclasses import asdict
from urllib.parse import urlparse

from game.core import DIRS, Action

from .questions import VARIANTS

BASE = os.environ.get("SYSTEM2_BASE_URL", "http://127.0.0.1:11434/v1")
MODEL = os.environ.get("SYSTEM2_MODEL", "qwen3.5:4b")
MOVE = {"avanzar": 1, "retroceder": -1, "quieto": 0}
_local = threading.local()


def prompt(state: str, variant: str = "B") -> list:
    v = VARIANTS[variant]
    q = []
    for key in ("move", "jump", "crouch", "aim", "shoot", "danger"):
        spec = v[key]
        if spec["type"] == "choice":
            opts = "; ".join(f'"{k}" = {d}' for k, d in spec["criteria"].items())
            q.append(f'- "{key}": {spec["instructions"]} Opciones: {opts}.')
        elif spec["type"] == "noul":
            q.append(f'- "{key}": {spec["instructions"]} Responde true o false.')
        else:
            q.append(f'- "{key}": {spec["instructions"]} Responde un entero 0..{len(spec["criteria"]) - 1} '
                     f'({", ".join(f"{i}={c}" for i, c in enumerate(spec["criteria"]))}).')
    system = ("Controlas a un soldado en un videojuego de acción. Lee el estado y responde SOLO un objeto JSON "
              "con las claves move, jump, crouch, aim, shoot, danger. Sin explicaciones.")
    user = f"Estado: {state}\n\nPreguntas:\n" + "\n".join(q)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`").split("\n", 1)[-1]
    obj = json.loads(s[s.index("{"): s.rindex("}") + 1])
    out = {"move": MOVE[obj["move"]], "aim": obj["aim"], "jump": obj["jump"], "crouch": obj["crouch"],
           "shoot": obj["shoot"], "danger": int(obj["danger"])}
    if out["aim"] not in DIRS or not all(isinstance(out[k], bool) for k in ("jump", "crouch", "shoot")) \
            or not 0 <= out["danger"] <= 2:
        raise ValueError("schema")
    return out


def _conn():
    if getattr(_local, "conn", None) is None:
        u = urlparse(BASE)
        _local.conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=60)
        _local.path = u.path.rstrip("/") + "/chat/completions"
    return _local.conn, _local.path


def ask(client, state: str, variant: str, factor: float = 1.0, gate: bool = True) -> dict:
    """Same record shape as System One's _ask; `client`/`factor` are unused (no probabilities)."""
    conn, path = _conn()
    body = {"model": MODEL, "messages": prompt(state), "temperature": 0, "max_tokens": 200,
            "response_format": {"type": "json_object"}, "reasoning_effort": "none"}
    t = time.perf_counter()
    try:
        conn.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
        raw = json.loads(conn.getresponse().read())
    except Exception:
        _local.conn = None
        raise
    rtt = (time.perf_counter() - t) * 1000
    text = raw["choices"][0]["message"]["content"] or ""
    usage = raw.get("usage", {})
    try:
        d = parse(text)
        act = Action(move=d["move"], jump=d["jump"], crouch=d["crouch"], aim=d["aim"], shoot=d["shoot"])
        tag, err, danger = "ACTUA", None, d["danger"] / 2
    except Exception as e:  # noqa: BLE001
        act, tag, err, danger = Action(aim="E", shoot=True), "FALLBACK", f"{type(e).__name__}: {e}", 0.0
    return {"system2_text": text, "parse_error": err, "rtt_ms": round(rtt, 2), "server_ms": None,
            "action": asdict(act), "tag": tag, "tags": {}, "conf": None, "danger": danger,
            "input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)}

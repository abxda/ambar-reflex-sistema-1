"""Fit a game-specific recalibration factor on held-out oracle labels.
p' ∝ p ** factor applied to the server's (T=1.8) probabilities; factor = 1.8 / T_game."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

NOULS = ("shoot", "jump", "crouch")


def pairs(paths, keys=NOULS):
    out = []
    for path in paths:
        for line in open(path):
            d = json.loads(line)
            if "raw" not in d or "labels" not in d:
                continue
            for k in keys:
                out.append((d["raw"]["answers"][k]["noul"], bool(d["labels"][k]), k))
    return out


def temper(p, f):
    p = min(max(p, 1e-9), 1 - 1e-9)
    y, n = p ** f, (1 - p) ** f
    return y / (y + n)


def nll(data, f):
    return -sum(math.log(temper(p, f) if y else 1 - temper(p, f)) for p, y, _ in data) / len(data)


def ece(data, f=1.0, bins=10):
    """Reliability of P(yes) against the label frequency (the standard binary ECE)."""
    b = [[] for _ in range(bins)]
    for p, y, _ in data:
        q = temper(p, f)
        b[min(int(q * bins), bins - 1)].append((q, y))
    return sum(abs(sum(q for q, _ in c) / len(c) - sum(y for _, y in c) / len(c)) * len(c) for c in b if c) / len(data)


def fit(data):
    grid = [round(0.5 + 0.05 * i, 2) for i in range(91)]  # 0.5 .. 5.0
    return min(grid, key=lambda f: nll(data, f))


if __name__ == "__main__":
    files = [Path(p) for p in sys.argv[1:]]
    data = pairs(files)
    f = fit(data)
    report = {"n": len(data), "factor": f, "T_game": round(1.8 / f, 3),
              "nll_server": round(nll(data, 1.0), 4), "nll_game": round(nll(data, f), 4),
              "ece_server": round(ece(data, 1.0), 4), "ece_game": round(ece(data, f), 4)}
    print(json.dumps(report))
    Path("runs/calibration.json").write_text(json.dumps(report, indent=1))

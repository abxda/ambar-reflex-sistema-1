"""Original chiptune + SFX synthesized with numpy (2 pulse channels, triangle bass, noise drums).
Composition written for this project: A minor, 150 BPM, 8-bar loop."""

from __future__ import annotations

import numpy as np

SR = 44100
BPM = 150
STEP = 60 / BPM / 4  # sixteenth note

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name: str) -> float:
    n, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[n] + 12 * (o - 4) - 9) / 12)


# 8 bars x 16 steps; "-" holds, "." rest
LEAD = ("A4 - - C5 - - E5 - D5 - C5 - B4 - G4 - " "A4 - - - E5 - - - A5 - G5 - E5 - D5 - "
        "F4 - - A4 - - C5 - B4 - A4 - G4 - E4 - " "F4 - A4 - C5 - D5 - E5 - - - . . . . "
        "A4 - - C5 - - E5 - D5 - C5 - B4 - G4 - " "A4 - - - E5 - - - A5 - B5 - C6 - B5 - "
        "G5 - - E5 - - C5 - D5 - E5 - D5 - B4 - " "A4 - - - - - - - . . A4 C5 E5 A5 . . ").split()
BASS = ("A2 . A2 . A3 . A2 . A2 . A2 . G2 . G2 . " * 2 + "F2 . F2 . F3 . F2 . F2 . F2 . G2 . G2 . " * 2) * 2
BASS = BASS.split()
CHORD = ["A3", "C4", "E4", "A3", "C4", "E4", "G3", "B3", "D4", "G3", "B3", "D4", "F3", "A3", "C4", "E4"]


def _pulse(f, n, duty=0.5, vol=0.12):
    t = np.arange(n) / SR
    wave = np.where((t * f) % 1.0 < duty, 1.0, -1.0)
    env = np.minimum(1.0, np.linspace(1.2, 0.3, n))
    return wave * env * vol


def _tri(f, n, vol=0.16):
    t = np.arange(n) / SR
    return (2 * np.abs(2 * ((t * f) % 1.0) - 1) - 1) * vol


def _noise(n, vol, decay, seed):
    rng = np.random.default_rng(seed)
    return rng.uniform(-1, 1, n) * np.exp(-np.arange(n) / (decay * SR)) * vol


def music_loop() -> np.ndarray:
    step_n = int(STEP * SR)
    total = step_n * len(LEAD)
    out = np.zeros(total)
    # lead with holds
    i = 0
    while i < len(LEAD):
        tok = LEAD[i]
        j = i + 1
        while j < len(LEAD) and LEAD[j] == "-":
            j += 1
        if tok not in ".-":
            n = step_n * (j - i)
            out[i * step_n:i * step_n + n] += _pulse(hz(tok), n, 0.25, 0.10)
        i = j
    for i, tok in enumerate(BASS[:len(LEAD)]):
        if tok != ".":
            out[i * step_n:(i + 2) * step_n] += _tri(hz(tok), 2 * step_n)[: len(out[i * step_n:(i + 2) * step_n])]
    for i in range(len(LEAD)):  # arpeggio
        f = hz(CHORD[(i // 16 * 3 + i % 3) % len(CHORD)])
        out[i * step_n:(i + 1) * step_n] += _pulse(f * 2, step_n, 0.125, 0.035)
    for i in range(0, len(LEAD), 4):  # drums
        kick = i % 8 == 0
        n = step_n * 2
        seg = out[i * step_n:i * step_n + n]
        seg += _noise(len(seg), 0.10 if kick else 0.06, 0.05 if kick else 0.02, i)[: len(seg)]
    return out


def sfx(name: str) -> np.ndarray:
    if name == "shoot":
        n = int(0.06 * SR)
        f = np.linspace(1400, 500, n)
        return np.where((np.cumsum(f) / SR) % 1.0 < 0.5, 1.0, -1.0) * np.linspace(0.08, 0, n)
    if name == "jump":
        n = int(0.12 * SR)
        f = np.linspace(300, 900, n)
        return np.where((np.cumsum(f) / SR) % 1.0 < 0.5, 1.0, -1.0) * np.linspace(0.08, 0, n)
    if name in ("explode", "die"):
        return _noise(int((0.5 if name == "die" else 0.3) * SR), 0.25 if name == "die" else 0.18, 0.12, 7)
    if name == "hit":
        return _noise(int(0.05 * SR), 0.08, 0.02, 3)
    if name == "pickup":
        n = int(0.25 * SR)
        f = np.repeat([660, 880, 1320], n // 3 + 1)[:n]
        return np.where((np.cumsum(f) / SR) % 1.0 < 0.5, 1.0, -1.0) * 0.08
    if name in ("boss", "clear"):
        n = int(0.8 * SR)
        f = np.linspace(200, 80, n) if name == "boss" else np.repeat([523, 659, 784, 1047], n // 4 + 1)[:n]
        return np.where((np.cumsum(f) / SR) % 1.0 < 0.5, 1.0, -1.0) * np.linspace(0.12, 0, n)
    return np.zeros(1)


def render_track(frames: int, events: list, fps: int = 60, lead_in: float = 0.0, tail: float = 0.0,
                 music_vol: float = 0.9) -> np.ndarray:
    """Stereo int16 for `frames` game frames (+ optional silent-ish title/outro padding)."""
    dur = lead_in + frames / fps + tail
    n = int(dur * SR)
    loop = music_loop()
    reps = n // len(loop) + 1
    out = np.tile(loop, reps)[:n] * music_vol
    cache = {}
    for frame, name in events:
        if name == "shoot" and frame % 2:  # thin out rapid fire
            continue
        s = cache.setdefault(name, sfx(name))
        i = int((lead_in + frame / fps) * SR)
        j = min(n, i + len(s))
        if i < n:
            out[i:j] += s[: j - i]
    out = np.tanh(out * 1.4) * 0.8
    return (np.stack([out, out], axis=1) * 32767).astype(np.int16)

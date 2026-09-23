"""The visual layer must leave replay state untouched and be stable on repaint."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json
import pickle
from pathlib import Path

import pygame
import pytest

from agent.modes import replay
from game.render import draw_world
from game.core import World
from hud import panel


def test_render_preserves_every_replay_frame():
    meta = json.loads(Path("runs/bench/realtime/rt-D-1987-2.meta.json").read_text())
    surface = pygame.Surface((256, 240))
    count = 0

    def on_frame(world, applied, current):
        nonlocal count
        before = pickle.dumps(world)
        draw_world(surface, world)
        assert pickle.dumps(world) == before
        pixels = pygame.image.tobytes(surface, "RGB")
        draw_world(surface, world)
        assert pygame.image.tobytes(surface, "RGB") == pixels
        count += 1

    replay(meta, on_frame)
    assert count == meta["frames"]


@pytest.mark.parametrize("frame", [0, 324])
def test_panel_watermark_is_drawn_once(frame, monkeypatch):
    decisions = [json.loads(line) for line in
                 Path("runs/bench/realtime/rt-D-1987-2.jsonl").read_text().splitlines()]
    view = panel.RunView(decisions, "jev-local")
    view.advance(frame)
    calls = []
    original = panel.watermark

    def record(surface, x, y, scale=4, alpha=102):
        calls.append(alpha)
        original(surface, x, y, scale, alpha)

    monkeypatch.setattr(panel, "watermark", record)
    surface = pygame.Surface((1080, 1920))
    panel.draw_panel(surface, pygame.Rect(28, 1040, 1024, 852), view, World(), frame, 0)
    assert calls == [102]

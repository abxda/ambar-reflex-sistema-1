"""Fast design iteration: render single frames (PNG) of a logged run without encoding a video.

  .venv/bin/python -m bench.preview_frame --frames 124 324 600 --layout landscape vertical
  .venv/bin/python -m bench.preview_frame --card title        # title card
  .venv/bin/python -m bench.preview_frame --card outro        # outro card

Output: preview/<layout>_f<frame>.png (and preview/card_<name>.png). CPU only, no GPU, no server.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from agent.modes import replay  # noqa: E402
from bench.render_video import GAME_NAME, LAYOUTS, card, compose, model_label, summary  # noqa: E402
from hud.panel import AMBER, BG, BRIGHT, DIM, RunView  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = "runs/bench/realtime/rt-D-1987-2"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=DEFAULT_RUN)
    ap.add_argument("--frames", type=int, nargs="*", default=[124, 324, 600])
    ap.add_argument("--layout", nargs="*", default=["landscape"], choices=list(LAYOUTS))
    ap.add_argument("--card", choices=["title", "outro"])
    ap.add_argument("--out", default=str(ROOT / "preview"))
    args = ap.parse_args()
    pygame.init()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    run = ROOT / args.run
    meta = json.loads(run.with_suffix(".meta.json").read_text())
    decisions = [json.loads(l) for l in open(run.with_suffix(".jsonl"))]
    if args.card:
        canvas = pygame.Surface(LAYOUTS[args.layout[0]]["size"])
        s = summary(meta, decisions)
        if args.card == "title":
            lines = [(GAME_NAME, 7, BRIGHT), ("", 2, BG), ("JUGADO EN TIEMPO REAL POR SISTEMA 1", 3, AMBER),
                     (f"{model_label(meta)} LOCAL · DECISIONES TIPADAS · 0 TOKENS GENERADOS", 2, DIM), ("", 2, BG), ("@abxda", 3, AMBER)]
        else:
            lines = [("RESULTADO", 6, BRIGHT), ("", 2, BG),
                     (f"AVANCE {s['progress']:.0f}%   PUNTAJE {s['score']}   BAJAS {s['kills']}", 3, AMBER),
                     (f"{s['decisions']} DECISIONES · LATENCIA MEDIA {s['lat_mean']:.0f} MS · P95 {s['lat_p95']:.0f} MS", 2, AMBER),
                     (f"FALLBACK {s['fallback']:.0f}% · 0 TOKENS GENERADOS", 2, AMBER), ("", 2, BG),
                     ("EL FORMATO ESTÁ GARANTIZADO; LA CORRECCIÓN NO.", 2, DIM), ("", 2, BG), ("@abxda", 3, AMBER)]
        card(canvas, lines, 1.0)
        path = out / f"card_{args.card}.png"
        pygame.image.save(canvas, str(path))
        print(path)
        return
    wanted = set(min(f, meta["frames"] - 1) for f in args.frames)
    for layout in args.layout:
        canvas = pygame.Surface(LAYOUTS[layout]["size"])
        game_surf = pygame.Surface((256, 240))
        view = RunView(decisions, model_label(meta))

        def on_frame(world, applied, current, layout=layout, canvas=canvas, view=view, game_surf=game_surf):
            view.advance(world.frame)
            if world.frame in wanted:
                compose(canvas, layout, world, view, world.frame, game_surf)
                path = out / f"{layout}_f{world.frame}.png"
                pygame.image.save(canvas, str(path))
                print(path)

        replay(meta, on_frame)


if __name__ == "__main__":
    main()

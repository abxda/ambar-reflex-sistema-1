"""Token count of `state` texts with the served model's own tokenizer (vocab only: no GPU).
Run with the jevlocal venv (has llama_cpp):  <jevlocal-venv>/bin/python -m bench.state_tokens"""

from __future__ import annotations

import glob
import json
import statistics as st
import sys
from pathlib import Path

GGUF = str(Path(__file__).resolve().parents[2] / "models" / "gguf" / "Qwen_Qwen3.5-4B-Q8_0.gguf")


def main():
    import llama_cpp

    llm = llama_cpp.Llama(model_path=GGUF, vocab_only=True, verbose=False)
    counts = {}
    for path in sorted(glob.glob("runs/bench/**/*.jsonl", recursive=True) + glob.glob("runs/variants/*.jsonl")):
        for line in open(path):
            d = json.loads(line)
            if d.get("state"):
                counts.setdefault(d.get("variant", "?"), []).append(len(llm.tokenize(d["state"].encode(), add_bos=False)))
    out = {v: {"n": len(c), "median": st.median(c), "p95": sorted(c)[int(0.95 * (len(c) - 1))], "max": max(c)}
           for v, c in counts.items()}
    Path("runs/state_tokens.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out))


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()

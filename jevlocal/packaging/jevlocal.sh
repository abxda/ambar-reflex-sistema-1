#!/usr/bin/env bash
# jevlocal launcher (relocatable bundle). Usage:
#   bin/jevlocal selftest                         load the model, answer the docs example, print timing
#   bin/jevlocal serve --host 0.0.0.0 --port 8765 Jev-compatible API at /v1/systemone
#   bin/jevlocal score in.jsonl out.jsonl         offline batch scoring
#   bin/jevlocal bench                            in-process latency/throughput
#   bin/jevlocal load  --url http://host:8765     concurrent HTTP load (works against api.typesafe.ai too)
#   bin/jevlocal eval  --data rows.jsonl [--url]  accuracy/calibration on labeled rows
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
PY="$HERE/python/bin/python3.12"
export JEVLOCAL_GGUF="${JEVLOCAL_GGUF:-$HERE/models/Qwen_Qwen3.5-4B-Q8_0.gguf}"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
# Bundled CUDA 12.8 runtime first, whatever CUDA the host has on LD_LIBRARY_PATH.
export LD_LIBRARY_PATH="$HERE/python/lib/python3.12/site-packages/llama_cpp/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unset PYTHONPATH PYTHONHOME
if ! command -v nvidia-smi >/dev/null 2>&1 && [ ! -e /dev/nvidia0 ]; then
  echo "jevlocal: no NVIDIA GPU/driver detected (driver >= 570 required)" >&2
fi
cmd="${1:-}"
case "$cmd" in
  bench) shift; exec "$PY" "$HERE/bench/latency.py" --gguf "$JEVLOCAL_GGUF" "$@" ;;
  load)  shift; exec "$PY" "$HERE/bench/load.py" "$@" ;;
  eval)  shift; exec "$PY" "$HERE/bench/eval_labeled.py" "$@" ;;
  ""|-h|--help) exec "$PY" -m jevlocal --help ;;
  *) exec "$PY" -m jevlocal "$@" ;;
esac

#!/usr/bin/env bash
# Build a self-contained, relocatable Linux x86_64 bundle of jevlocal:
#   python/   standalone CPython 3.12 (python-build-standalone) with jevlocal + llama-cpp-python (CUDA)
#   models/   Qwen3.5-4B Q8_0 GGUF
#   bin/      launcher
# The target machine only needs an NVIDIA driver >= 570 (CUDA 12.8 runtime is bundled) and glibc >= 2.17.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"           # /mnt/data_4tb/JEV-CODING
NAME="jevlocal-1.0.0-linux-x86_64-cuda12"
OUT="${OUT:-$ROOT/dist}"
STAGE="$OUT/$NAME"
PY_SRC="${PY_SRC:-$HOME/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu}"
WHEEL="$ROOT/build/dist228/llama_cpp_python-0.3.35-py3-none-linux_x86_64.whl"  # built against glibc 2.28 sysroot
CENV="$ROOT/build/cenv"
GGUF="$ROOT/models/gguf/Qwen_Qwen3.5-4B-Q8_0.gguf"
UV="${UV:-$HOME/.local/bin/uv}"

rm -rf "$STAGE"
mkdir -p "$STAGE"/{bin,models,bench}
echo "[1/6] standalone python"
cp -a "$PY_SRC" "$STAGE/python"
rm -f "$STAGE/python/lib/python3.12/EXTERNALLY-MANAGED"
PY="$STAGE/python/bin/python3.12"

echo "[2/6] wheels (llama-cpp-python CUDA fat binary sm75..sm120, jevlocal)"
"$UV" build -q --wheel -o "$ROOT/build/dist" "$ROOT/jevlocal"
"$UV" pip install -q --python "$PY" --break-system-packages --no-cache "$WHEEL" "$ROOT/build/dist/jevlocal-1.0.0-py3-none-any.whl"

echo "[3/6] bundle CUDA runtime + C++ runtime next to the llama.cpp libraries"
LIB="$STAGE/python/lib/python3.12/site-packages/llama_cpp/lib"
for so in libcudart.so.12 libcublas.so.12 libcublasLt.so.12 libstdc++.so.6 libgcc_s.so.1; do
  cp -L "$CENV/lib/$so" "$LIB/"
done
rm -f "$LIB"/libmtmd.so*  # multimodal helper, unused
for f in "$LIB"/*.so*; do
  [ -L "$f" ] && continue
  "$CENV/bin/patchelf" --force-rpath --set-rpath '$ORIGIN' "$f"  # DT_RPATH beats LD_LIBRARY_PATH
done

echo "[4/6] model"
cp "$GGUF" "$STAGE/models/"

echo "[5/6] launcher, docs, benchmarks"
cp "$ROOT/jevlocal/packaging/jevlocal.sh" "$STAGE/bin/jevlocal"
cp "$ROOT/jevlocal/packaging/jevlocal.service" "$STAGE/"
cp "$ROOT/jevlocal/packaging/README.md" "$STAGE/README.md"
cp "$ROOT/jevlocal/bench/"*.py "$STAGE/bench/"
chmod +x "$STAGE/bin/jevlocal"
find "$STAGE/python" -name "__pycache__" -prune -exec rm -rf {} +
( cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )

echo "[6/6] tarball"
tar -C "$OUT" -cf - "$NAME" | zstd -T0 -3 -q -o "$OUT/$NAME.tar.zst" -f
ls -la "$OUT/$NAME.tar.zst"
du -sh "$STAGE"

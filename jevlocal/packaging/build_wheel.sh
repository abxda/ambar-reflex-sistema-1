#!/usr/bin/env bash
# Build the CUDA wheel of llama-cpp-python 0.3.35 exactly as used by jevlocal:
# conda-forge gcc/g++ 13 + CUDA 12.8 toolchain + glibc 2.28 sysroot (portable: RHEL/Rocky 8+, Ubuntu 20.04+).
# Fat binary for sm_75..sm_120. Needs miniconda/conda and uv. Output: build/dist228/llama_cpp_python-0.3.35-*.whl
# Uses up to $JOBS parallel compile jobs (default 32) under a memory cap: compiling is CPU/RAM heavy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CENV="$ROOT/build/cenv"
JOBS="${JOBS:-32}"
mkdir -p "$ROOT/build"
source "$(conda info --base)/etc/profile.d/conda.sh"
if [ ! -x "$CENV/bin/nvcc" ]; then
  conda create -y -q -p "$CENV" -c conda-forge -c nvidia/label/cuda-12.8.1 \
    gxx_linux-64=13 gcc_linux-64=13 "sysroot_linux-64=2.28" cuda-nvcc=12.8 cuda-cudart-dev=12.8 \
    libcublas-dev=12.8 cuda-version=12.8 cmake ninja patchelf
fi
conda activate "$CENV"
export CUDACXX="$CONDA_PREFIX/bin/nvcc" CUDAToolkit_ROOT="$CONDA_PREFIX"
export CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75-real;80-real;86-real;89-real;90-real;120-real;120-virtual -DGGML_NATIVE=off -DGGML_OPENMP=off -DGGML_AVX2=on -DGGML_FMA=on -DGGML_F16C=on -DCMAKE_CUDA_HOST_COMPILER=$CXX"
export CMAKE_BUILD_PARALLEL_LEVEL="$JOBS"
cd "$ROOT/build"
if [ ! -d llama_cpp_python-0.3.35 ]; then
  url=$(curl -s https://pypi.org/pypi/llama-cpp-python/0.3.35/json | python3 -c 'import json,sys;print([u["url"] for u in json.load(sys.stdin)["urls"] if u["packagetype"]=="sdist"][0])')
  curl -sL -o llama_cpp_python-0.3.35.tar.gz "$url"
  tar xzf llama_cpp_python-0.3.35.tar.gz
fi
PY="${PY:-$(command -v python3.12 || command -v python3)}"
cmd=(uv build --wheel -p "$PY" -o "$ROOT/build/dist228" "$ROOT/build/llama_cpp_python-0.3.35")
if command -v systemd-run >/dev/null; then
  systemd-run --user --scope -q -p MemoryMax=64G nice -n 15 "${cmd[@]}"
else
  nice -n 15 "${cmd[@]}"
fi
ls -la "$ROOT/build/dist228"

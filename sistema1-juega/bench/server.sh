#!/usr/bin/env bash
# Start/stop the local System One server by PID file (never by pattern matching).
# usage: bench/server.sh start [profile] | stop | status
set -euo pipefail
JEV="${JEVLOCAL_BIN:-$(cd "$(dirname "$0")/../.." && pwd)/.venv-jl/bin/jevlocal}"
PIDF="$(dirname "$0")/../runs/.server.pid"
LOG="$(dirname "$0")/../runs/server.log"
PORT="${JEV_PORT:-8765}"
case "${1:-status}" in
  start)
    if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "already running pid $(cat "$PIDF")"; exit 0; fi
    mkdir -p "$(dirname "$LOG")"
    nohup "$JEV" serve --port "$PORT" --profile "${2:-semif}" >"$LOG" 2>&1 &
    echo $! > "$PIDF"
    for _ in $(seq 60); do curl -sf "localhost:$PORT/health" >/dev/null && break; sleep 1; done
    curl -s "localhost:$PORT/health"; echo ;;
  stop)
    if [ -f "$PIDF" ]; then kill "$(cat "$PIDF")" 2>/dev/null || true; rm -f "$PIDF"; fi
    for _ in $(seq 30); do curl -sf "localhost:$PORT/health" >/dev/null || break; sleep 1; done
    echo stopped ;;
  status) curl -s "localhost:$PORT/health" || echo "not running"; echo ;;
esac

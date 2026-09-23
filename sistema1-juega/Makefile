# Sistema 1 juega — @abxda
# Prerequisite for GPU targets: System One server up  ->  bench/server.sh start ; export JEV_BASE_URL=http://127.0.0.1:8765
PY := .venv/bin/python
export JEV_BASE_URL ?= http://127.0.0.1:8765

.PHONY: setup test benchmark human system2 analyze report video server-start server-stop check-server

setup:
	uv venv -q -p 3.12 .venv && uv pip install -q -p $(PY) pygame-ce numpy matplotlib pytest

test:
	$(PY) -m pytest -q tests

check-server:
	@curl -sf $(JEV_BASE_URL)/health >/dev/null || (echo "System One server not reachable at $(JEV_BASE_URL). Run: bench/server.sh start" && exit 1)

benchmark: check-server test
	$(PY) -m bench.benchmark

human:
	$(PY) -m game.play_human --seed 1987

system2:
	$(PY) -m bench.system2_phase

analyze:
	$(PY) -m bench.analyze

report: analyze
	$(PY) -m bench.report

video:
	$(PY) -m bench.make_videos

server-start:
	bench/server.sh start semif

server-stop:
	bench/server.sh stop

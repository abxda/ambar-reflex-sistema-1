"""Every figure quoted in social.md and in the video outro must exist in results.md;
latencies in results.json must be recomputable from the JSONL logs."""

import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?=\s?(?:%|ms|frames|tokens))")


def test_social_numbers_come_from_results():
    results = (ROOT / "results.md").read_text()
    tokens = set(re.findall(r"\d+(?:\.\d+)?", results))
    for doc in ("social.md", "video/PUBLICACION.md"):
        text = (ROOT / doc).read_text()
        missing = [n for n in set(NUM.findall(text)) if n not in tokens]
        assert not missing, f"numbers in {doc} not found as figures in results.md: {missing}"


def test_comparison_numbers_come_from_results_modelos():
    path = ROOT / "results_modelos.md"
    if not path.exists():
        return
    tokens = set(re.findall(r"\d+(?:\.\d+)?", path.read_text()))
    text = (ROOT / "video" / "PUBLICACION_COMPARACION.md").read_text()
    missing = [n for n in set(NUM.findall(text)) if n not in tokens]
    assert not missing, f"numbers in PUBLICACION_COMPARACION.md not in results_modelos.md: {missing}"


def test_latency_recomputes_from_logs():
    R = json.loads((ROOT / "results.json").read_text())
    lat = [json.loads(l)["rtt_ms"] for p in sorted((ROOT / "runs" / "bench" / "realtime").glob("*.jsonl"))
           for l in open(p) if json.loads(l).get("rtt_ms")]
    assert abs(st.fmean(lat) - R["table"]["realtime"]["lat_mean"]) < 1e-6


def test_signatures():
    social = (ROOT / "social.md").read_text()
    assert social.count("— @abxda") >= 6
    assert "el formato está garantizado; la corrección no" in social.lower()

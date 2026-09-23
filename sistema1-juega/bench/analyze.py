"""Aggregate runs -> results.json, results.md and figures (all numbers come from the JSONL logs)."""

from __future__ import annotations

import json
import math
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bench.calibrate import ece, temper  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "bench"
FIG = ROOT / "figures"
CONFIGS = [  # (dir, label)
    ("realtime", "Sistema 1 · tiempo real"),
    ("turns", "Sistema 1 · por turnos"),
    ("system2_realtime", "Sistema 2 (LLM + JSON) · tiempo real"),
    ("system2_turns", "Sistema 2 (LLM + JSON) · por turnos"),
    ("human", "Humano (teclado)"),
    ("random", "Aleatorio uniforme (piso)"),
]
AMBER, DIM = "#ffb000", "#7a5200"


def load(cfg: str) -> list:
    out = []
    for meta_path in sorted((RUNS / cfg).glob("*.meta.json")):
        meta = json.loads(meta_path.read_text())
        jl = meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl"))
        decs = [json.loads(l) for l in open(jl)] if jl.exists() else []
        out.append((meta, decs))
    return out


def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))] if xs else float("nan")


def summarize(runs: list) -> dict:
    res = [m["result"] for m, _ in runs]
    decs = [d for _, ds in runs for d in ds]
    lat = [d["rtt_ms"] for d in decs if d.get("rtt_ms")]
    frames = [d["arr_frame"] - d["req_frame"] for d in decs if "arr_frame" in d and d.get("rtt_ms")]
    seconds = sum(r["seconds"] for r in res)
    s = {
        "n": len(runs),
        "progress_mean": st.fmean(r["progress"] for r in res), "progress_sd": st.pstdev([r["progress"] for r in res]),
        "progress_max": max(r["progress"] for r in res),
        "score_mean": st.fmean(r["score"] for r in res), "kills_mean": st.fmean(r["kills"] for r in res),
        "deaths_mean": st.fmean(r["deaths"] for r in res), "cleared": sum(r["cleared"] for r in res),
        "stalled": sum(r.get("stalled", False) for r in res), "seconds_mean": st.fmean(r["seconds"] for r in res),
        "decisions": len(decs),
    }
    realtime = runs and "realtime" in runs[0][0].get("mode", "")
    if lat:
        s.update(lat_mean=st.fmean(lat), lat_p50=st.median(lat), lat_p95=_pct(lat, 0.95),
                 frames_per_decision=st.median(frames) if frames and realtime else None,
                 decisions_per_s=len(lat) / seconds if seconds and realtime else None,
                 tokens_in=st.median(d["input_tokens"] for d in decs if d.get("input_tokens")))
    tagged = [d for d in decs if d.get("tag") and d.get("rtt_ms")]
    if tagged:
        s["pct_fallback"] = 100 * sum(d["tag"] == "FALLBACK" for d in tagged) / len(tagged)
        s["pct_duda"] = 100 * sum(d["tag"] == "DUDA" for d in tagged) / len(tagged)
        s["pct_actua"] = 100 * sum(d["tag"] == "ACTUA" for d in tagged) / len(tagged)
    s2 = [d for d in decs if "system2_text" in d]
    if s2:
        s["parse_errors"] = sum(d["parse_error"] is not None for d in s2)
        s["pct_parse_errors"] = 100 * s["parse_errors"] / len(s2)
        s["output_tokens_mean"] = st.fmean(d.get("output_tokens", 0) for d in s2)
    return s


def accuracy(runs: list) -> dict:
    decs = [d for _, ds in runs for d in ds if "labels" in d and "raw" in d]
    if not decs:
        return {}
    out = {}
    for k in ("shoot", "jump", "crouch"):
        y = [d["labels"][k] for d in decs]
        p = [d["raw"]["answers"][k]["noul"] for d in decs]
        tp = sum(yy and pp >= 0.5 for yy, pp in zip(y, p))
        out[k] = {"acc": sum((pp >= 0.5) == yy for yy, pp in zip(y, p)) / len(y), "positives": sum(y),
                  "recall": tp / sum(y) if sum(y) else None, "precision": tp / sum(pp >= 0.5 for pp in p) if any(pp >= 0.5 for pp in p) else None}
    aligned = [d for d in decs if d["labels"]["best_aim"]]
    out["aim"] = {"acc_when_aligned": sum(d["raw"]["answers"]["aim"]["choice"] == d["labels"]["best_aim"] for d in aligned) / len(aligned) if aligned else None,
                  "n": len(aligned)}
    return out


def calib_pairs(runs, key):
    return [(d["raw"]["answers"][key]["noul"], bool(d["labels"][key]), key) for _, ds in runs for d in ds
            if "labels" in d and "raw" in d]


def _wm(fig):
    fig.text(0.985, 0.02, "@abxda", ha="right", va="bottom", fontsize=16, color="white", alpha=0.4,
             fontweight="bold", family="monospace")


def _style(ax):
    ax.set_facecolor("#080602")
    for sp in ax.spines.values():
        sp.set_color(DIM)
    ax.tick_params(colors=AMBER)
    ax.xaxis.label.set_color(AMBER)
    ax.yaxis.label.set_color(AMBER)
    ax.title.set_color(AMBER)


def reliability_fig(pairs, key, factor, path):
    fig, ax = plt.subplots(figsize=(7, 6), facecolor="#080602")
    _style(ax)
    ax.plot([0, 1], [0, 1], "--", color=DIM, lw=1, label="calibración perfecta")
    for f, name, col in ((1.0, "T=1.8 (servidor, genérica)", AMBER), (factor, f"T={1.8 / factor:.2f} (recalibrada en el juego)", "#ff5a3c")):
        bins = [[] for _ in range(10)]
        for p, y, _ in pairs:
            q = temper(p, f)
            bins[min(int(q * 10), 9)].append((q, y))
        xs = [st.fmean(q for q, _ in b) for b in bins if b]
        ys = [st.fmean(y for _, y in b) for b in bins if b]
        ns = [len(b) for b in bins if b]
        ax.plot(xs, ys, "o-", color=col, lw=2, label=f"{name}  ECE={ece(pairs, f):.3f}")
        for x, y, n in zip(xs, ys, ns):
            ax.annotate(str(n), (x, y), textcoords="offset points", xytext=(4, -12), color=col, fontsize=7)
    ax.set_xlabel(f"P(sí) de System One para '{key}'")
    ax.set_ylabel("tasa real (etiqueta del oráculo)")
    ax.set_title(f"Diagrama de confiabilidad · {key} · n={len(pairs)}")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    leg = ax.legend(facecolor="#080602", edgecolor=DIM, fontsize=8)
    for t in leg.get_texts():
        t.set_color(AMBER)
    _wm(fig)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def latency_fig(groups: dict, path):
    fig, ax = plt.subplots(figsize=(8, 5), facecolor="#080602")
    _style(ax)
    cols = [AMBER, "#ff5a3c", "#7ad0ff", "#9cff7a"]
    for (label, lat), c in zip(groups.items(), cols):
        if lat:
            ax.hist(lat, bins=40, alpha=0.6, color=c, label=f"{label} (mediana {st.median(lat):.0f} ms)")
    ax.axvline(1000 / 60 * 8, color=DIM, ls=":", lw=1)
    ax.text(1000 / 60 * 8 + 5, ax.get_ylim()[1] * 0.9, "8 frames", color=DIM, fontsize=8)
    ax.set_xlabel("latencia de ida y vuelta por decisión (ms)")
    ax.set_ylabel("decisiones")
    ax.set_title("Latencia por decisión (6 preguntas en una petición)")
    leg = ax.legend(facecolor="#080602", edgecolor=DIM, fontsize=8)
    for t in leg.get_texts():
        t.set_color(AMBER)
    _wm(fig)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def progress_fig(rows: list, path):
    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#080602")
    _style(ax)
    labels = [r[0] for r in rows]
    means = [r[1]["progress_mean"] for r in rows]
    sds = [r[1]["progress_sd"] for r in rows]
    ax.barh(labels, means, xerr=sds, color=AMBER, ecolor=DIM, alpha=0.85)
    for i, m in enumerate(means):
        ax.text(m + 1, i, f"{m:.1f}%", va="center", color=AMBER, fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_xlabel("avance medio en el nivel (%) · N partidas, misma semilla")
    ax.set_title("Desempeño por configuración")
    ax.invert_yaxis()
    _wm(fig)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    FIG.mkdir(exist_ok=True)
    calib = json.loads((ROOT / "runs" / "calibration.json").read_text())
    variants = json.loads((ROOT / "runs" / "variants.json").read_text()) if (ROOT / "runs" / "variants.json").exists() else None
    conc = json.loads((ROOT / "runs" / "concurrency.json").read_text()) if (ROOT / "runs" / "concurrency.json").exists() else None
    tokens = json.loads((ROOT / "runs" / "state_tokens.json").read_text()) if (ROOT / "runs" / "state_tokens.json").exists() else None
    table, loaded = [], {}
    for cfg, label in CONFIGS:
        runs = load(cfg)
        if runs:
            loaded[cfg] = runs
            table.append((label, summarize(runs), cfg))
    s1 = loaded.get("realtime", []) + loaded.get("turns", [])
    acc = {cfg: accuracy(loaded[cfg]) for cfg in ("realtime", "turns") if cfg in loaded}
    cal = {}
    for key in ("shoot", "jump"):
        pairs = calib_pairs(s1, key)
        if pairs:
            reliability_fig(pairs, key, calib["factor"], FIG / f"reliability_{key}.png")
            cal[key] = {"n": len(pairs), "ece_server": ece(pairs, 1.0), "ece_game": ece(pairs, calib["factor"]),
                        "positives": sum(y for _, y, _ in pairs)}
    latency_fig({label: [d["rtt_ms"] for m, ds in loaded[cfg] for d in ds if d.get("rtt_ms")]
                 for cfg, label in CONFIGS if cfg in loaded and cfg in ("realtime", "turns", "system2_realtime", "system2_turns")},
                FIG / "latency_hist.png")
    progress_fig([(label, s) for label, s, _ in table], FIG / "progress_by_config.png")
    results = {"table": {cfg: s for _, s, cfg in table}, "accuracy": acc, "calibration": cal,
               "calibration_fit": calib, "variants": variants, "concurrency": conc, "state_tokens": tokens,
               "human_pending": "human" not in loaded}
    (ROOT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print(json.dumps({cfg: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()} for _, s, cfg in table}, indent=1))
    return results


if __name__ == "__main__":
    main()

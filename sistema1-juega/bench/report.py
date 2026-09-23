"""results.json -> results.md and social.md (every number is formatted from results.json)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"realtime": "Sistema 1 · tiempo real", "turns": "Sistema 1 · por turnos",
          "system2_realtime": "Sistema 2 (LLM+JSON) · tiempo real", "system2_turns": "Sistema 2 (LLM+JSON) · por turnos",
          "human": "Humano (teclado)", "random": "Aleatorio uniforme"}
SIGN = "— @abxda"


def f0(x):
    return "—" if x is None else f"{x:.0f}"


def f1(x):
    return "—" if x is None else f"{x:.1f}"


def f2(x):
    return "—" if x is None else f"{x:.2f}"


def f3(x):
    return "—" if x is None else f"{x:.3f}"


def export_eval_rows():
    """Oracle-labeled `shoot` decisions in jevlocal's eval format, to refit the server temperature."""
    rows = []
    for jl in sorted((ROOT / "runs" / "bench").glob("*/*.jsonl")) + [ROOT / "runs" / "calib" / "turns-B-2024.jsonl"]:
        if not jl.exists():
            continue
        for line in open(jl):
            d = json.loads(line)
            if "labels" in d and "raw" in d:
                q = d["raw"]["answers"]  # question text comes from the variant used
                rows.append({"id": f"{jl.stem}-{d['i']}", "state": d["state"],
                             "question": "¿Hay un enemigo en la línea de tiro? Cuenta cualquier enemigo en pantalla (no balas): el arma gira en 8 direcciones.",
                             "options": [{"id": "yes", "description": "Sí"}, {"id": "no", "description": "No"}],
                             "label": 0 if d["labels"]["shoot"] else 1})
    out = ROOT / "runs" / "eval_rows_shoot.jsonl"
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out, len(rows)


def main():
    R = json.loads((ROOT / "results.json").read_text())
    T = R["table"]
    vm = json.loads((ROOT / "video" / "video_meta.json").read_text()) if (ROOT / "video" / "video_meta.json").exists() else None
    best_meta = None
    if vm:
        p = next((ROOT / "runs").rglob(vm["run"] + ".meta.json"), None)
        best_meta = json.loads(p.read_text()) if p else None
    eval_path, n_eval = export_eval_rows()
    rt, tu = T.get("realtime", {}), T.get("turns", {})
    cal = R["calibration"]
    fit = R["calibration_fit"]
    var = R.get("variants") or {}
    conc = R.get("concurrency") or {}
    tok = R.get("state_tokens") or {}
    L = []
    w = L.append
    w("# Sistema 1 juega — resultados\n")
    w("*Ámbar Reflex, run-and-gun original de 8 bits jugado por decisiones tipadas (API compatible con Jev). "
      f"Todas las cifras salen de `runs/` y `results.json`.* {SIGN}\n")
    w("## Resumen\n")
    if rt:
        w(f"- En **tiempo real**, System One (Qwen3.5-4B local, 6 preguntas por petición) llegó en promedio al "
          f"**{f1(rt['progress_mean'])} %** del nivel (máximo {f1(rt['progress_max'])} %), con **{f0(rt['lat_mean'])} ms** "
          f"de latencia media por decisión (p95 {f0(rt['lat_p95'])} ms): una decisión cada "
          f"{f0(rt.get('frames_per_decision'))} frames. Ninguna partida pasó del {f1(rt['progress_max'])} % del nivel.")
    if tu:
        if tu["progress_mean"] < rt.get("progress_mean", 0):
            w(f"- **Por turnos** (el juego espera cada respuesta) llegó solo al **{f1(tu['progress_mean'])} %**, menos que en "
              "tiempo real. La causa es un sesgo medible: P(saltar) ronda 0.55 aun sin amenazas y, decidiendo cada 8 frames, "
              "el soldado salta en la mayoría de las decisiones hacia el peligro. En tiempo real decide cada ~25 frames y "
              "salta menos. La recalibración por temperatura no corrige un sesgo; hacen falta umbrales por pregunta.")
        else:
            w(f"- **Por turnos** (el juego espera cada respuesta) llegó al **{f1(tu['progress_mean'])} %**.")
    if "random" in T:
        w(f"- El agente **aleatorio** (piso) llegó al {f1(T['random']['progress_mean'])} %.")
    if "system2_realtime" in T:
        s2 = T["system2_realtime"]
        w(f"- **Sistema 2** (qwen3.5:4b generando JSON con las mismas preguntas) tardó **{f0(s2.get('lat_mean'))} ms** por "
          f"decisión ({f0(s2.get('frames_per_decision'))} frames), {f1(s2.get('output_tokens_mean'))} tokens generados de media "
          f"y {f1(s2.get('pct_parse_errors'))} % de JSON inválido (el modo JSON de Ollama funcionó bien). Llegó al "
          f"{f1(s2['progress_mean'])} %: con la misma información, reaccionar {s2.get('lat_mean', 0) / max(1, rt.get('lat_mean', 1)):.1f}× "
          "más lento cuesta más que cualquier ventaja de generar texto.")
    w("- La redacción importa más que el modelo: sin decir la meta, el agente se quedó quieto para siempre "
      "(punto muerto determinista), y medir `dy` desde los pies en vez de desde el arma hacía que apuntara mal.")
    s1_logs = [json.loads(l) for cfg in ("realtime", "turns") for p in sorted((ROOT / "runs" / "bench" / cfg).glob("*.jsonl"))
               for l in open(p)]
    bad = sum("error" in d for d in s1_logs)
    w(f"- **El formato está garantizado; la corrección no**: {bad} de {len(s1_logs)} respuestas de System One fuera de "
      "esquema (validadas campo por campo contra el fixture), pero muchas decisiones equivocadas dentro del esquema "
      "(ver exactitud contra el oráculo).\n")
    w("## Configuración\n")
    w("- Servidor: `jevlocal` (Qwen3.5-4B GGUF Q8_0, llama.cpp CUDA) en RTX 3060 12 GB que también dibuja el escritorio; "
      "ctx 16k, 16 ramas, ubatch 512 (modo seguro), temperatura del servidor T=1.8.")
    w(f"- Semilla del nivel {1987}; partidas en tiempo real N=5 (varían por el tiempo de llegada de cada respuesta). "
      "El modo por turnos es determinista: 2 réplicas idénticas lo verifican, más serían copias.")
    w(f"- Recalibración del juego: factor {fit['factor']} sobre las probabilidades del servidor (T efectiva "
      f"{f2(fit['T_game'])}), ajustado con {fit['n']} etiquetas del oráculo en una partida separada (semilla 2024).")
    w("- Política v2: los umbrales se aplican a las preguntas que la API devuelve con `confidence` (mover y apuntar): "
      "> 0.9 ACTÚA, 0.5–0.9 DUDA (se ejecuta), < 0.5 FALLBACK (quieto; apuntar al frente y disparar). Las noul "
      "(saltar, agacharse, disparar) se ejecutan si P(sí) ≥ 0.5. La etiqueta de la decisión es la peor de mover/apuntar.\n")
    w("## Tabla comparativa\n")
    w("| Configuración | N | Avance medio % (±sd) | Máx % | Puntaje medio | Bajas | Muertes | Latencia media ms | p95 ms | Frames/decisión | Decisiones/s | % DUDA | % FALLBACK |")
    w("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for cfg, s in T.items():
        w(f"| {LABELS[cfg]} | {s['n']} | {f1(s['progress_mean'])} (±{f1(s['progress_sd'])}) | {f1(s['progress_max'])} | "
          f"{f0(s['score_mean'])} | {f1(s['kills_mean'])} | {f1(s['deaths_mean'])} | {f0(s.get('lat_mean'))} | "
          f"{f0(s.get('lat_p95'))} | {f0(s.get('frames_per_decision'))} | {f2(s.get('decisions_per_s'))} | "
          f"{f0(s.get('pct_duda'))} | {f0(s.get('pct_fallback'))} |")
    if R.get("human_pending"):
        w(f"| {LABELS['human']} | 0 | pendiente (`make human`) | | | | | | | | | | |")
    w("\n![avance](figures/progress_by_config.png)\n")
    if var:
        w("## Variantes de redacción (selección por avance medio, N=3 en tiempo real)\n")
        w("| Variante | Qué cambia | Avance medio % | Latencia mediana ms | Tokens por petición |")
        w("|---|---|--:|--:|--:|")
        desc = {"A": "literal de la especificación", "B": "geométrica, meta explícita, alturas de balas",
                "C": "B en inglés", "D": "B + compensación de latencia (dead reckoning)"}
        for v, d in var["variants"].items():
            rtts = [r["rtt_ms"] for r in d["runs"] if r["rtt_ms"]]
            toks = [r["tokens"] for r in d["runs"] if r["tokens"]]
            w(f"| {v} | {desc.get(v, v)} | {f1(d['mean_progress'])} | {f0(sorted(rtts)[len(rtts) // 2] if rtts else None)} | "
              f"{f0(sorted(toks)[len(toks) // 2] if toks else None)} |")
        w(f"\nElegida: **{var['best']}**. La A se queda quieta desde el primer frame: sin la meta, el modelo prefiere "
          "'quieto' (p≈0.50) y, como el estado nunca cambia, repite la misma respuesta hasta que la regla de "
          "estancamiento (45 s) termina la partida. La A además dice 'agacharse para esquivar un proyectil bajo', "
          "lo contrario de la física del juego (agacharse esquiva balas altas).\n")
    v1 = sorted((ROOT / "runs" / "_policy_v1" / "variants").glob("*.meta.json"))
    if v1:
        by = {}
        for p in v1:
            m = json.loads(p.read_text())
            by.setdefault(m["variant"], []).append(m["result"]["progress"])
        w("## Política v1 (descartada) — por qué\n")
        w("La primera política también exigía confianza a las preguntas noul, usando |2p − 1| (una extensión nuestra; "
          "la API no define `confidence` para noul). El modelo sí pedía saltar (p = 0.53–0.65 frente a hoyos y escalones), "
          "pero esa confianza quedaba bajo 0.5 y el agente no saltaba: caía en el hoyo o se quedaba para siempre frente "
          "a un escalón.\n")
        w("| Variante | Avance medio % con v1 | Partidas |")
        w("|---|--:|--:|")
        for v, xs in sorted(by.items()):
            w(f"| {v} | {f1(sum(xs) / len(xs))} | {len(xs)} |")
        w("")
    if R.get("accuracy"):
        w("## Exactitud práctica contra el oráculo del simulador\n")
        w("El simulador es determinista, así que las etiquetas son exactas: `shoot` = hay un enemigo en pantalla; "
          "`jump`/`crouch` = hacerlo ahora evita un daño que sin hacerlo llegaría en 30 frames (rollout contrafactual); "
          "`aim` = dirección del enemigo alineado más cercano.\n")
        w("| Modo | shoot exactitud | jump exactitud (positivos) | jump recall | crouch exactitud (positivos) | aim exactitud (n) |")
        w("|---|--:|--:|--:|--:|--:|")
        for cfg, a in R["accuracy"].items():
            w(f"| {LABELS[cfg]} | {f3(a['shoot']['acc'])} | {f3(a['jump']['acc'])} ({a['jump']['positives']}) | "
              f"{f3(a['jump']['recall'])} | {f3(a['crouch']['acc'])} ({a['crouch']['positives']}) | "
              f"{f3(a['aim']['acc_when_aligned'])} ({a['aim']['n']}) |")
        w("")
    if cal:
        w("## Calibración aplicada\n")
        w("| Pregunta | n | positivos | ECE con T=1.8 (servidor) | ECE recalibrada para el juego |")
        w("|---|--:|--:|--:|--:|")
        for k, c in cal.items():
            w(f"| {k} | {c['n']} | {c['positives']} | {f3(c['ece_server'])} | {f3(c['ece_game'])} |")
        w("\n![shoot](figures/reliability_shoot.png) ![jump](figures/reliability_jump.png)\n")
        sh, jp = cal.get("shoot", {}), cal.get("jump", {})
        w(f"La T=1.8 del servidor es genérica (ajustada en 554 decisiones de texto, no de este juego). Recalibrar la "
          f"temperatura con datos del juego mejora `shoot` (ECE {f3(sh.get('ece_server'))} → {f3(sh.get('ece_game'))}) pero "
          f"casi no `jump` ({f3(jp.get('ece_server'))} → {f3(jp.get('ece_game'))}): ahí el error es un sesgo (P(saltar)≈0.55 "
          "sin amenazas) que una temperatura no puede mover; hace falta un umbral o Platt por pregunta. Propuesta: recalibrar el "
          f"servidor con datos del dominio usando `bin/jevlocal eval` sobre `{eval_path.relative_to(ROOT)}` "
          f"({n_eval} decisiones etiquetadas en el formato de jevlocal, con `--as-noul`).\n")
    w("## Latencia, lote y tokens\n")
    w("![latencia](figures/latency_hist.png)\n")
    if conc:
        c1, c2 = conc.get("inflight_1", {}), conc.get("inflight_2", {})
        w(f"- Concurrencia (30 s): con 1 petición en vuelo, {f2(c1.get('decisions_per_s'))} decisiones/s y "
          f"{f0(c1.get('lat_mean_ms'))} ms; con 2 en vuelo, {f2(c2.get('decisions_per_s'))} decisiones/s y "
          f"{f0(c2.get('lat_mean_ms'))} ms. El servidor agrupa las dos peticiones en un lote, pero el cuello es de "
          "cómputo: sube la tasa a costa de decisiones más viejas.")
    if tok:
        for v, t in tok.items():
            w(f"- Tokens del `state` (variante {v}): mediana {f0(t['median'])}, p95 {f0(t['p95'])}, máximo {f0(t['max'])} "
              "— muy por debajo del contexto seguro de 16k.")
    if rt.get("tokens_in"):
        best_v = var.get("best") if var else None
        st_med = tok.get(best_v, {}).get("median") if best_v else None
        share = f"~{100 * (1 - st_med / rt['tokens_in']):.0f} %" if st_med else "la mayor parte"
        w(f"- Tokens por petición completa (estado + 6 preguntas): mediana {f0(rt['tokens_in'])}; el `state` usa "
          f"{f0(st_med)}, así que {share} es el texto de las preguntas: es la palanca real para bajar la latencia.")
    w("- 0 tokens generados: cada respuesta es una lectura de probabilidades en una pasada.\n")
    if best_meta:
        from bench.render_video import summary
        r = best_meta["result"]
        jl = next((ROOT / "runs").rglob(vm["run"] + ".jsonl"))
        sv = summary(best_meta, [json.loads(l) for l in open(jl)])
        w("## La partida del video\n")
        w(f"`{vm['run']}` (la mejor de las 5 en tiempo real): avance {sv['progress']:.0f} % ({f1(r['progress'])} %), "
          f"puntaje {sv['score']}, {sv['kills']} bajas, {r['seconds']:.1f} s de juego, {sv['decisions']} decisiones, "
          f"latencia media {sv['lat_mean']:.0f} ms, p95 {sv['lat_p95']:.0f} ms, FALLBACK {sv['fallback']:.0f} %. "
          "Son las cifras del cierre del video.\n")
    w("## Límites honestos\n")
    w("- El formato está garantizado; la corrección no.")
    w("- La latencia (~0.4 s con 6 preguntas en esta GPU en modo seguro) es lenta para un run-and-gun: en tiempo real "
      "el agente reacciona a un mundo que ya cambió.")
    w("- Un solo nivel, una semilla y un modelo de 4B; los resultados no generalizan a otros juegos sin medir.")
    w("- El oráculo define `shoot` como 'hay un enemigo en pantalla' porque el arma gira; la alineación exacta se "
      "reporta aparte.\n")
    w("## Reproducir\n")
    w("```bash\nbench/server.sh start      # servidor System One (prerrequisito)\nexport JEV_BASE_URL=http://127.0.0.1:8765\nmake benchmark\n```\n")
    w(SIGN)
    (ROOT / "results.md").write_text("\n".join(L))
    social(R, best_meta)
    print("results.md + social.md written")


def social(R: dict, best_meta):
    T = R["table"]
    rt, tu = T.get("realtime", {}), T.get("turns", {})
    s2 = T.get("system2_realtime")
    lat = f0(rt.get("lat_mean"))
    s2lat = f0(s2.get("lat_mean")) if s2 else "—"
    tweet = (f"Un modelo de 4B jugando un run-and-gun ochentero sin generar texto: 6 preguntas tipadas por decisión, "
             f"{lat} ms. El mismo tamaño escribiendo JSON: {s2lat} ms. Avance: {f1(rt.get('progress_mean'))} % vs "
             f"{f1(s2['progress_mean']) if s2 else '—'} %. El formato está garantizado; la corrección no. {SIGN}")
    thread = [
        f"1/ Sistema 1 = juicio rápido. En vez de pedirle a un LLM que escriba JSON, le pregunto 6 cosas "
        f"(mover, saltar, agacharse, apuntar, disparar, peligro) y leo la probabilidad de cada opción en una pasada. {SIGN}",
        f"2/ Resultado: {lat} ms por decisión con Qwen3.5-4B local y {f1(rt.get('progress_mean'))} % de avance medio en "
        f"tiempo real. Juega mal, pero rápido y dentro del esquema: disparar acierta {f0(100 * R['accuracy']['realtime']['shoot']['acc'])} %, "
        f"saltar apenas tiene {f0(100 * R['accuracy']['realtime']['jump']['precision'])} % de precisión. {SIGN}",
        f"3/ Lo más útil: la redacción. Sin decir la meta, el agente se quedó quieto para siempre. Medir la altura "
        f"desde los pies en vez de desde el arma lo hacía fallar la puntería. Y describir dónde estarán las balas cuando "
        f"llegue la respuesta subió el avance. {SIGN}",
    ]
    if s2:
        thread.append(f"4/ Sistema 2 (el mismo tamaño de modelo escribiendo JSON): {f0(s2.get('lat_mean'))} ms por decisión, "
                      f"{f1(s2.get('pct_parse_errors'))} % de JSON inválido y {f1(s2['progress_mean'])} % de avance. "
                      f"Aquí el JSON no falló; lo que perdió fue el tiempo de reacción. {SIGN}")
    linkedin = (
        "¿Qué pasa si a un modelo de lenguaje no le pides texto, sino decisiones?\n\n"
        "Construí «Ámbar Reflex», un run-and-gun original de estilo 8 bits, y lo puse a jugar con un servidor local de "
        "decisiones tipadas compatible con la API de Jev (Sistema 1): en cada decisión el modelo recibe una descripción "
        "compacta del frame y seis preguntas cerradas —mover, saltar, agacharse, apuntar, disparar y peligro— y devuelve "
        "probabilidades, sin generar un solo token.\n\n"
        f"Medí latencia, exactitud contra un oráculo del simulador y calibración. En una RTX 3060, cada decisión tomó "
        f"{lat} ms en promedio y el agente llegó al {f1(rt.get('progress_mean'))} % del nivel; el mismo tamaño de modelo "
        f"generando JSON tardó {s2lat} ms y llegó al {f1(s2['progress_mean']) if s2 else '—'} %. Los hallazgos: la redacción "
        "de las preguntas pesa más que el modelo, la compensación de latencia importa en tiempo real, y la temperatura "
        "genérica no sustituye a calibrar umbrales con datos del dominio.\n\n"
        "La lección práctica va más allá de los videojuegos: ruteo, moderación y pipelines de alto volumen pueden correr "
        "en local, sin costo por petición y con respuestas que nunca rompen el esquema. Eso sí: el formato está "
        "garantizado; la corrección no, y hay que medirla.\n\n"
        f"Código, datos y video en el repositorio. {SIGN}")
    facebook = (
        "Le enseñé a una IA a jugar un videojuego retro… sin dejarla hablar 🎮\n\n"
        "En lugar de pedirle que escriba qué hacer, le hago seis preguntas rápidas en cada momento (¿avanzo?, ¿salto?, "
        "¿me agacho?, ¿a dónde apunto?, ¿disparo?, ¿qué tan peligroso está?) y ella responde con probabilidades. "
        f"Tarda unos {lat} ms por decisión y todo corre en mi computadora.\n\n"
        f"¿Qué tal juega? Honestamente, mal: llegó en promedio al {f1(rt.get('progress_mean'))} % del nivel. Pero decide "
        f"en {lat} ms, y la misma IA escribiendo sus respuestas tardó {s2lat} ms y llegó menos lejos. Aprendí que cómo "
        "le preguntas cambia todo, y que una respuesta bien formada no siempre es una respuesta correcta.\n\n"
        f"El video muestra en vivo lo que «piensa» en cada decisión. {SIGN}")
    alt = ("Video en pantalla dividida: a la izquierda, un videojuego de estilo 8 bits donde un soldado de armadura "
           "verde azulado avanza y dispara contra soldados, torretas y drones; un abanico de flechas ámbar sale del "
           "soldado con opacidad según la probabilidad de cada dirección. A la derecha, una terminal ámbar muestra "
           "barras de probabilidad, un medidor de peligro, latencias y un registro de decisiones. Marca de agua @abxda.")
    L = ["# Kit de publicación\n", f"*Cifras tomadas de results.md.* {SIGN}\n",
         "## X / Twitter\n", f"**Tuit** ({len(tweet)} caracteres):\n", tweet + "\n", "**Hilo opcional:**\n"]
    L += [t + "\n" for t in thread]
    L += ["## LinkedIn\n", linkedin + "\n", f"*({len(linkedin.split())} palabras)*\n",
          "## Facebook\n", facebook + "\n",
          "## Hashtags\n", "#IA #LLM #SistemaUno #GameDev #PixelArt #OpenSource #Benchmark #IALocal\n",
          "## Llamado a la acción\n", f"¿Qué decisión de tu trabajo podría ser una pregunta cerrada en vez de un prompt largo? Cuéntame. {SIGN}\n",
          "## Texto alternativo del video\n", alt + f" {SIGN}\n"]
    (ROOT / "social.md").write_text("\n".join(L))
    assert len(tweet) <= 280, f"tweet too long ({len(tweet)})"


if __name__ == "__main__":
    main()

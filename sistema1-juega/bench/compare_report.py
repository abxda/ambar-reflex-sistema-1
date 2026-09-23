"""runs/models/comparacion.json -> results_modelos.md and video/PUBLICACION_COMPARACION.md."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/abxda/ambar-reflex-sistema-1"
SIGN = "— Dr. Coronado (@abxda)"
NAMES = {"qwen35-4b": "Qwen3.5-4B (Q8_0)", "gemma4-e4b": "Gemma 4 E4B (Q6_K)", "qwen35-9b": "Qwen3.5-9B (Q5_K_M)"}
SHORT = {"qwen35-4b": "Qwen3.5-4B", "gemma4-e4b": "Gemma 4 E4B", "qwen35-9b": "Qwen3.5-9B"}


def pct(x):
    return f"{100 * x:.1f}"


def main():
    R = json.loads((ROOT / "runs" / "models" / "comparacion.json").read_text())
    q4, g4, q9 = R["qwen35-4b"], R["gemma4-e4b"], R["qwen35-9b"]
    smart = max(R, key=lambda k: R[k]["eval_acc"])
    far = max(R, key=lambda k: R[k]["prog_mean"])
    fast = min(R, key=lambda k: R[k]["lat"])
    L = []
    w = L.append
    w("# ¿Quién decide mejor? Tres modelos locales jugando Ámbar Reflex (Sistema 1, sin pensamiento)\n")
    w(f"Mismo juego, misma partida (semilla 1987), misma variante de preguntas (D), misma política v2 y el mismo "
      f"servidor compatible con Jev. Solo cambia el modelo. {SIGN}\n")
    w("## Resultados\n")
    w("| | " + " | ".join(NAMES[k] for k in R) + " |")
    w("|---|" + "--:|" * len(R))
    rows = [
        ("Exactitud en 554 decisiones etiquetadas (sin presión de tiempo)", lambda r: f"{pct(r['eval_acc'])} %"),
        ("Exactitud balanceada (554)", lambda r: f"{pct(r['eval_bal'])} %"),
        ("Avance medio en tiempo real", lambda r: f"{r['prog_mean']:.1f} %"),
        ("Mejor partida", lambda r: f"{r['prog_max']:.1f} %"),
        ("Partidas en tiempo real (N)", lambda r: f"{r['n']}"),
        ("Latencia media por decisión (6 preguntas)", lambda r: f"{r['lat']:.0f} ms"),
        ("Frames por decisión (mediana)", lambda r: f"{r['fpd']:.0f}"),
        ("Bajas por partida", lambda r: f"{r['kills']:.1f}"),
        ("Disparar: exactitud contra el oráculo", lambda r: f"{pct(r['shoot'])} %"),
        ("Apuntar: exactitud contra el oráculo", lambda r: f"{pct(r['aim'])} %"),
        ("Saltar: % de decisiones con salto", lambda r: f"{r['jump_rate']} %"),
        ("Decisiones en FALLBACK", lambda r: f"{r['tags'].get('FALLBACK', 0)} %"),
        ("Factor de recalibración del juego (T efectiva)", lambda r: f"{r['factor']} ({1.8 / r['factor']:.2f})"),
    ]
    for name, f in rows:
        w(f"| {name} | " + " | ".join(f(R[k]) for k in R) + " |")
    w("")
    w("## Lectura\n")
    w(f"- **El más listo sin presión de tiempo es {SHORT[smart]}** ({pct(R[smart]['eval_acc'])} % en las 554 decisiones), "
      f"pero **el que llega más lejos jugando es {SHORT[far]}** ({R[far]['prog_mean']:.1f} %). En tiempo real, saber más no "
      "alcanza: pesan la latencia, los sesgos por pregunta y la calibración.")
    w(f"- **Qwen3.5-9B** decide mejor en texto y elimina más enemigos ({q9['kills']:.1f} por partida), pero tarda "
      f"{q9['lat']:.0f} ms por decisión (una cada {q9['fpd']:.0f} frames) y apunta mal en el juego ({pct(q9['aim'])} %). Con la "
      f"recalibración del juego, el {q9['tags'].get('FALLBACK', 0)} % de sus decisiones cae en FALLBACK (quieto y "
      "disparar al frente).")
    w(f"- **Gemma 4 E4B** es el más rápido ({g4['lat']:.0f} ms) y muy bueno en texto, pero en el juego salta en el "
      f"{g4['jump_rate']} % de las decisiones, un sesgo que lo expone. Su calibración tocó el límite de la búsqueda (factor "
      f"{g4['factor']}): es el más sobreconfiado.")
    w(f"- **Qwen3.5-4B** acierta menos en texto ({pct(q4['eval_acc'])} %), pero apunta mejor en el juego "
      f"({pct(q4['aim'])} %) y reacciona en {q4['lat']:.0f} ms.")
    w("")
    w("## Límites honestos\n")
    w("- **Ventaja de local:** la redacción de las preguntas (variante D) y la política de umbrales se iteraron con el "
      "Qwen3.5-4B. Los otros dos modelos juegan con preguntas que no se ajustaron para ellos.")
    w("- Qwen3.5-4B tiene N=5 partidas (el benchmark publicado); los otros, N=3. Una sola semilla y un solo nivel.")
    srv = {}
    for k in ("gemma4-e4b", "qwen35-9b"):
        meta = json.loads(sorted((ROOT / "runs" / "models" / k / "realtime").glob("*.meta.json"))[0].read_text())
        srv[k] = meta["server"]
    w("- Cuantizaciones distintas para que cada modelo quepa junto al escritorio en una RTX 3060 (Q8_0, Q6_K, Q5_K_M). "
      "Para dejar margen al escritorio, el watchdog redujo el contexto y las ramas: "
      + "; ".join(f"{SHORT[k]} {s['ctx']} tokens y {s['seqs']} ramas" for k, s in srv.items())
      + " (Qwen3.5-4B: 16384 y 16). Las peticiones del juego usan menos de 1,000 tokens, así que no se truncó nada.")
    w("- Todos corren **sin pensamiento**: plantilla de chat oficial con el pensamiento desactivado (verificada contra "
      "cada GGUF). 0 tokens generados.")
    w("")
    w("## Videos\n")
    w("- `video/comparacion_modelos_vertical_1080x1920.mp4`: los tres en pila, sincronizados. Si un modelo muere, su "
      "juego queda congelado en «GAME OVER» mientras los demás siguen.")
    w("- `video/comparacion_modelos_horizontal_1920x1080.mp4`: los mismos, lado a lado.")
    w("- `video/modelos/<modelo>_1080p60.mp4`: la mejor partida de cada modelo, con su panel completo.")
    w("")
    w(f"Reproducir: `bench/compare_models.py` (GPU, un modelo a la vez) y luego `bench/compare_video.py`. {SIGN}")
    (ROOT / "results_modelos.md").write_text("\n".join(L) + "\n")

    # ---------------- publications
    tweet = (f"¿Quién decide mejor? 3 modelos locales, sin pensamiento, en la misma partida de mi clon de #JEV: "
             f"{SHORT[smart]} es el más listo ({pct(R[smart]['eval_acc'])} %), pero {SHORT[far]} llega más lejos "
             f"({R[far]['prog_mean']:.1f} %): en tiempo real pesan velocidad, puntería y sesgos. {SIGN} {URL}")
    P = []
    p = P.append
    p("# Publicación — Benchmark en video: ¿quién decide mejor?\n")
    p(f"Autor: **Dr. Coronado (@abxda)** · Repositorio: {URL}")
    p("Hecho con **Claude Opus 5.5** (arquitectura, código, benchmark y análisis) y **GPT-6 Astra** (diseño gráfico).")
    p("Cifras de `../results_modelos.md`. Segunda publicación de la serie: el antecedente es `PUBLICACION.md`.\n")
    p("| Red | Video |\n|---|---|")
    p("| Facebook / reels | `comparacion_modelos_vertical_1080x1920.mp4` |")
    p("| X / Twitter | `comparacion_modelos_horizontal_1920x1080.mp4` |")
    p("| LinkedIn | `comparacion_modelos_horizontal_1920x1080.mp4` |\n")
    p("---\n\n## Facebook\n")
    p("¿Qué IA decide mejor? Las puse a jugar la misma partida 🎮")
    p("")
    p(f"Hace poco les conté de mi clon local de #JEV: un «Sistema 1» que no escribe, solo decide con probabilidades. "
      f"Ahora lo uso como banco de pruebas: tres modelos abiertos, sin pensamiento, juegan exactamente la misma partida "
      f"de Ámbar Reflex, uno encima del otro en el video.")
    p("")
    p(f"El resultado me sorprendió: {SHORT[smart]} es el más listo cuando le pregunto con calma "
      f"({pct(R[smart]['eval_acc'])} % de aciertos), pero {SHORT[far]} es el que llega más lejos jugando "
      f"({R[far]['prog_mean']:.1f} % del nivel): decide en {R[far]['lat']:.0f} ms y apunta mejor. El 9B tarda más, y "
      f"Gemma 4 E4B, aunque es el más rápido, salta de más. En tiempo real, saber más no alcanza.")
    p("")
    p("Un video así sirve para contrastar modelos de verdad: no solo cuánto saben, sino cómo se comportan bajo presión.")
    p("")
    p("Lo construí con Claude Opus 5.5 (código y medición) y GPT-6 Astra (diseño gráfico).")
    p(f"Código y datos: {URL}")
    p("")
    p(SIGN)
    p("")
    p("#JEV #InteligenciaArtificial #IALocal #Videojuegos #CódigoAbierto")
    p("\n---\n\n## X / Twitter\n")
    p("**Tuit principal** (≤ 280 caracteres):\n")
    p("> " + tweet + "\n")
    p("**Hilo:**\n")
    p(f"1/ Mismo juego, misma partida, mismas preguntas, mismo servidor compatible con #JEV. Solo cambia el modelo: "
      f"Qwen3.5-4B, Gemma 4 E4B y Qwen3.5-9B, todos sin pensamiento. {SIGN}\n")
    p(f"2/ Sin presión de tiempo (554 decisiones etiquetadas): 9B {pct(q9['eval_acc'])} %, Gemma "
      f"{pct(g4['eval_acc'])} %, 4B {pct(q4['eval_acc'])} %. Jugando en tiempo real: 4B {q4['prog_mean']:.1f} %, 9B "
      f"{q9['prog_mean']:.1f} %, Gemma {g4['prog_mean']:.1f} %. {SIGN}\n")
    p(f"3/ ¿Por qué? El 9B tarda {q9['lat']:.0f} ms por decisión contra {q4['lat']:.0f} ms del 4B, y Gemma salta en el "
      f"{g4['jump_rate']} % de las jugadas. Ojo: las preguntas se afinaron con el 4B, así que juega de local. {SIGN}\n")
    p(f"4/ El benchmark en video como forma de contrastar modelos: se ve quién decide, cuándo duda y cuándo muere. Hecho "
      f"con Claude Opus 5.5 y GPT-6 Astra (diseño). {URL} {SIGN}\n")
    p("#JEV #IA #LLM #OpenSource")
    p("\n---\n\n## LinkedIn\n")
    p("**¿Más inteligente significa mejor decisor? Un benchmark en video con tres modelos locales**")
    p("")
    p("En la publicación anterior presenté mi clon local de #JEV, el «Sistema 1» de TypeSafe AI: preguntas tipadas y "
      "probabilidades, sin generar texto. Ahora lo uso para contrastar modelos. Qwen3.5-4B, Gemma 4 E4B y Qwen3.5-9B "
      "juegan la misma partida de Ámbar Reflex, con las mismas preguntas, la misma política y sin pensamiento, en una "
      "RTX 3060.")
    p("")
    p("Resultados:")
    p(f"• Sin presión de tiempo (554 decisiones etiquetadas): Qwen3.5-9B {pct(q9['eval_acc'])} %, Gemma 4 E4B "
      f"{pct(g4['eval_acc'])} %, Qwen3.5-4B {pct(q4['eval_acc'])} %.")
    p(f"• En tiempo real: Qwen3.5-4B llega al {q4['prog_mean']:.1f} % del nivel ({q4['lat']:.0f} ms por decisión); "
      f"Qwen3.5-9B, al {q9['prog_mean']:.1f} % ({q9['lat']:.0f} ms); Gemma 4 E4B, al {g4['prog_mean']:.1f} % "
      f"({g4['lat']:.0f} ms, pero salta en el {g4['jump_rate']} % de las decisiones).")
    p("")
    p("La lección: la exactitud en un conjunto de prueba no predice el desempeño cuando la latencia, la calibración y "
      "los sesgos por pregunta importan. Una salvedad honesta: las preguntas se afinaron con el modelo de 4B.")
    p("")
    p("Ver a los modelos decidir lado a lado, con cada probabilidad y cada llamada JSON en pantalla, es una forma "
      "concreta de elegir modelo para ruteo, moderación o agentes en tiempo real.")
    p("")
    p("Construido con Claude Opus 5.5 (arquitectura, código y medición) y GPT-6 Astra (diseño gráfico).")
    p(f"Código, logs y videos reproducibles: {URL}")
    p("")
    p(SIGN)
    p("")
    p("#JEV #InteligenciaArtificial #LLM #IALocal #Benchmark #OpenSource")
    p("\n---\n\n## Texto alternativo del video\n")
    p("Video comparativo: tres versiones del mismo videojuego retro de 8 bits, apiladas (o lado a lado), cada una con una "
      "franja ámbar con el nombre del modelo que juega (Qwen3.5-4B, Gemma 4 E4B, Qwen3.5-9B). Junto a cada juego, la "
      "latencia, la decisión y las probabilidades en barras, y el JSON de cada llamada. Cuando un modelo pierde, su "
      f"pantalla queda congelada con «GAME OVER» mientras los demás siguen. Marca de agua @abxda. {SIGN}")
    doc = "\n".join(P) + "\n"
    (ROOT / "video" / "PUBLICACION_COMPARACION.md").write_text(doc)
    xlen = sum(2 if ord(c) > 0xFFFF else 1 for c in re.sub(r"https?://\S+", "x" * 23, tweet))
    assert xlen <= 280, f"tweet {xlen} > 280"
    print("results_modelos.md + video/PUBLICACION_COMPARACION.md; tweet", xlen)


if __name__ == "__main__":
    main()

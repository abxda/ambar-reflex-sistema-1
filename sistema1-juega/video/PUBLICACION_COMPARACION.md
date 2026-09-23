# Publicación — Benchmark en video: ¿quién decide mejor?

Autor: **Dr. Coronado (@abxda)** · Repositorio: https://github.com/abxda/ambar-reflex-sistema-1
Hecho con **Claude Opus 5.5** (arquitectura, código, benchmark y análisis) y **GPT-6 Astra** (diseño gráfico).
Cifras de `../results_modelos.md`. Segunda publicación de la serie: el antecedente es `PUBLICACION.md`.

| Red | Video |
|---|---|
| Facebook / reels | `comparacion_modelos_vertical_1080x1920.mp4` |
| X / Twitter | `comparacion_modelos_horizontal_1920x1080.mp4` |
| LinkedIn | `comparacion_modelos_horizontal_1920x1080.mp4` |

---

## Facebook

¿Qué IA decide mejor? Las puse a jugar la misma partida 🎮

Hace poco les conté de mi clon local de #JEV: un «Sistema 1» que no escribe, solo decide con probabilidades. Ahora lo uso como banco de pruebas: tres modelos abiertos, sin pensamiento, juegan exactamente la misma partida de Ámbar Reflex, uno encima del otro en el video.

El resultado me sorprendió: Qwen3.5-9B es el más listo cuando le pregunto con calma (82.7 % de aciertos), pero Qwen3.5-4B es el que llega más lejos jugando (24.9 % del nivel): decide en 408 ms y apunta mejor. El 9B tarda más, y Gemma 4 E4B, aunque es el más rápido, salta de más. En tiempo real, saber más no alcanza.

Un video así sirve para contrastar modelos de verdad: no solo cuánto saben, sino cómo se comportan bajo presión.

Lo construí con Claude Opus 5.5 (código y medición) y GPT-6 Astra (diseño gráfico).
Código y datos: https://github.com/abxda/ambar-reflex-sistema-1

— Dr. Coronado (@abxda)

#JEV #InteligenciaArtificial #IALocal #Videojuegos #CódigoAbierto

---

## X / Twitter

**Tuit principal** (≤ 280 caracteres):

> ¿Quién decide mejor? 3 modelos locales, sin pensamiento, en la misma partida de mi clon de #JEV: Qwen3.5-9B es el más listo (82.7 %), pero Qwen3.5-4B llega más lejos (24.9 %): en tiempo real pesan velocidad, puntería y sesgos. — Dr. Coronado (@abxda) https://github.com/abxda/ambar-reflex-sistema-1

**Hilo:**

1/ Mismo juego, misma partida, mismas preguntas, mismo servidor compatible con #JEV. Solo cambia el modelo: Qwen3.5-4B, Gemma 4 E4B y Qwen3.5-9B, todos sin pensamiento. — Dr. Coronado (@abxda)

2/ Sin presión de tiempo (554 decisiones etiquetadas): 9B 82.7 %, Gemma 81.6 %, 4B 77.8 %. Jugando en tiempo real: 4B 24.9 %, 9B 17.5 %, Gemma 14.4 %. — Dr. Coronado (@abxda)

3/ ¿Por qué? El 9B tarda 591 ms por decisión contra 408 ms del 4B, y Gemma salta en el 74 % de las jugadas. Ojo: las preguntas se afinaron con el 4B, así que juega de local. — Dr. Coronado (@abxda)

4/ El benchmark en video como forma de contrastar modelos: se ve quién decide, cuándo duda y cuándo muere. Hecho con Claude Opus 5.5 y GPT-6 Astra (diseño). https://github.com/abxda/ambar-reflex-sistema-1 — Dr. Coronado (@abxda)

#JEV #IA #LLM #OpenSource

---

## LinkedIn

**¿Más inteligente significa mejor decisor? Un benchmark en video con tres modelos locales**

En la publicación anterior presenté mi clon local de #JEV, el «Sistema 1» de TypeSafe AI: preguntas tipadas y probabilidades, sin generar texto. Ahora lo uso para contrastar modelos. Qwen3.5-4B, Gemma 4 E4B y Qwen3.5-9B juegan la misma partida de Ámbar Reflex, con las mismas preguntas, la misma política y sin pensamiento, en una RTX 3060.

Resultados:
• Sin presión de tiempo (554 decisiones etiquetadas): Qwen3.5-9B 82.7 %, Gemma 4 E4B 81.6 %, Qwen3.5-4B 77.8 %.
• En tiempo real: Qwen3.5-4B llega al 24.9 % del nivel (408 ms por decisión); Qwen3.5-9B, al 17.5 % (591 ms); Gemma 4 E4B, al 14.4 % (312 ms, pero salta en el 74 % de las decisiones).

La lección: la exactitud en un conjunto de prueba no predice el desempeño cuando la latencia, la calibración y los sesgos por pregunta importan. Una salvedad honesta: las preguntas se afinaron con el modelo de 4B.

Ver a los modelos decidir lado a lado, con cada probabilidad y cada llamada JSON en pantalla, es una forma concreta de elegir modelo para ruteo, moderación o agentes en tiempo real.

Construido con Claude Opus 5.5 (arquitectura, código y medición) y GPT-6 Astra (diseño gráfico).
Código, logs y videos reproducibles: https://github.com/abxda/ambar-reflex-sistema-1

— Dr. Coronado (@abxda)

#JEV #InteligenciaArtificial #LLM #IALocal #Benchmark #OpenSource

---

## Texto alternativo del video

Video comparativo: tres versiones del mismo videojuego retro de 8 bits, apiladas (o lado a lado), cada una con una franja ámbar con el nombre del modelo que juega (Qwen3.5-4B, Gemma 4 E4B, Qwen3.5-9B). Junto a cada juego, la latencia, la decisión y las probabilidades en barras, y el JSON de cada llamada. Cuando un modelo pierde, su pantalla queda congelada con «GAME OVER» mientras los demás siguen. Marca de agua @abxda. — Dr. Coronado (@abxda)

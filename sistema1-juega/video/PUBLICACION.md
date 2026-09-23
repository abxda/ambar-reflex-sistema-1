# Publicación — Ámbar Reflex: un clon local de Jev jugando un videojuego retro

Autor: **Dr. Coronado (@abxda)** · Repositorio: https://github.com/abxda/ambar-reflex-sistema-1

Cifras tomadas de `../results.md`: 5 partidas en tiempo real con la misma semilla, RTX 3060.

## Qué video usar en cada red

| Red | Archivo | Formato |
|---|---|---|
| Facebook (feed y reels) | `sistema1_vertical_1080x1920.mp4` | 1080×1920, 27 s |
| X / Twitter | `sistema1_momentos_clave.mp4` | 1920×1080, 35 s (con repeticiones en cámara lenta) |
| LinkedIn | `sistema1_1080p60.mp4` | 1920×1080 a 60 fps, 27 s |

Los tres muestran la misma partida real: a la izquierda el juego, a la derecha las probabilidades de
cada decisión y, abajo, el **flujo JSON real** de cada llamada a `/v1/systemone` (petición → respuesta).

---

## Facebook

Construí un **clon local de Jev** y lo puse a jugar un videojuego retro 🎮

Jev es el modelo «Sistema 1» de TypeSafe AI: en lugar de escribir texto, responde preguntas cerradas con
probabilidades, en milisegundos. Solo existe como servicio en la nube, así que armé mi propia versión
compatible con su API. Corre en mi computadora, con un modelo abierto de 4B parámetros en una RTX 3060.

Para probarlo creé un juego original de disparos al estilo de consola de los 80: **Ámbar Reflex**. En
cada jugada, la IA recibe una descripción de la pantalla y seis preguntas: ¿avanzo?, ¿salto?, ¿me agacho?,
¿a dónde apunto?, ¿disparo?, ¿qué tan peligroso está? Responde con probabilidades en **408 ms**, sin
generar ni una palabra.

¿Cómo funciona por dentro? El cerebro es **Qwen3.5-4B**, un modelo abierto pequeño, comprimido a 8 bits
para que quepa en la tarjeta de video. No lo dejo escribir: le muestro las opciones y leo directamente
qué tan probable considera cada una. Las seis preguntas comparten una sola lectura de la pantalla, por eso
se resuelven juntas.

¿Qué tal juega? Honestamente, regular: llegó en promedio al **24.9 %** del nivel. Pero la misma IA
escribiendo sus respuestas en JSON tardó **1041 ms** por jugada y llegó solo al **10.3 %**. Un jugador al
azar llega al 4.6 %.

Y ojo: esto es con un modelo chiquito de 4B. Con modelos más grandes debería decidir mejor, a cambio de
más memoria y un poco más de tiempo por jugada. Es lo siguiente que quiero probar.

En el video se ve en vivo lo que «piensa» en cada decisión, incluido el JSON real que viaja entre el
juego y el modelo. La lección: el formato está garantizado; la corrección no.

Todo el código es abierto: https://github.com/abxda/ambar-reflex-sistema-1

— Dr. Coronado (@abxda)

#InteligenciaArtificial #IA #Videojuegos #PixelArt #CódigoAbierto #IALocal

---

## X / Twitter

**Tuit principal** (≤ 280 caracteres):

> Hice un clon local de Jev: Qwen3.5-4B a 8 bits en una RTX 3060, sin generar texto. En un run-and-gun ochentero decide en 408 ms y llega al 24.9 % del nivel; escribiendo JSON: 1041 ms y 10.3 %. ¿Con un modelo más grande? Voy por eso 👇 — Dr. Coronado (@abxda)

**Hilo:**

1/ Jev (TypeSafe AI) es un modelo «Sistema 1»: no escribe, decide. Le das un estado y preguntas cerradas,
y te devuelve probabilidades. Armé un clon local con la misma API (POST /v1/systemone): Qwen3.5-4B
cuantizado a 8 bits sobre llama.cpp, en una RTX 3060. — Dr. Coronado (@abxda)

2/ Por dentro: no genera tokens. Lee la probabilidad del siguiente token restringida a las letras de las
opciones. El estado se procesa una vez y las 6 preguntas salen como ramas de esa misma pasada.
— Dr. Coronado (@abxda)

3/ Para medirlo en serio hice un juego original de 8 bits. En cada jugada, una sola petición con 6
preguntas: mover, saltar, agacharse, apuntar, disparar y peligro. 408 ms, 0 tokens generados.
— Dr. Coronado (@abxda)

4/ Lo que funcionó: disparar acierta el 97 %. Lo que no: «saltar» tiene un sesgo y apenas 18 % de
precisión. Y la redacción importa más que el modelo: sin decirle la meta, se quedó quieto para siempre.
— Dr. Coronado (@abxda)

5/ Describir dónde estarán las balas cuando llegue la respuesta (compensación de latencia) subió el
avance de 15.6 % a 26.2 %. El formato está garantizado; la corrección no. — Dr. Coronado (@abxda)

6/ Y todo esto con un modelo de solo 4B. La arquitectura acepta cualquier modelo abierto: con uno más grande
(9B, 27B) debería decidir mejor, a cambio de memoria y latencia. Es el siguiente experimento.
https://github.com/abxda/ambar-reflex-sistema-1 — Dr. Coronado (@abxda)

#IA #LLM #GameDev #OpenSource

---

## LinkedIn

**¿Qué pasa si a un modelo de lenguaje no le pides texto, sino decisiones?**

TypeSafe AI lanzó Jev, un modelo «Sistema 1»: recibe un estado y preguntas tipadas (elige una opción,
califica, sí/no) y devuelve probabilidades calibradas en una sola pasada, sin generar texto. Solo está
disponible como API en la nube, así que construí un **clon local compatible con su API**.

La arquitectura, en breve:
• Servidor con la misma interfaz que Jev (POST /v1/systemone), así que el SDK oficial funciona sin cambios.
• Modelo: **Qwen3.5-4B** cuantizado a 8 bits (GGUF Q8_0), sobre llama.cpp con CUDA, en una RTX 3060.
• Sin generación: se lee la probabilidad del siguiente token restringida a las letras de las opciones
  (método abierto SemIf).
• El estado se procesa una sola vez y las preguntas se resuelven como ramas de esa misma pasada.

Para evaluarlo en condiciones exigentes diseñé **Ámbar Reflex**, un videojuego original de estilo 8 bits
que el modelo juega en tiempo real. En cada jugada recibe una descripción compacta de la pantalla y seis
preguntas cerradas en una sola petición.

Resultados medidos (5 partidas, misma semilla):
• **408 ms** por decisión y **24.9 %** de avance medio, sin generar un solo token.
• El mismo tamaño de modelo generando JSON: **1041 ms** y **10.3 %**. El JSON nunca falló; perdió por
  tiempo de reacción.
• 0 de 290 respuestas fuera de esquema, pero con errores reales dentro del esquema: disparar acierta el
  97 %; saltar, apenas 18 % de precisión.
• La redacción pesó más que el modelo, y compensar la latencia subió el avance de 15.6 % a 26.2 %.

Todo esto con un modelo pequeño, de 4B. La arquitectura es independiente del modelo: con uno más grande
(9B o 27B) es razonable esperar mejores decisiones, a cambio de más memoria y latencia. En benchmarks
públicos de este tipo de modelos, las versiones de 27B puntúan más alto en calidad de decisión. Es el
siguiente experimento.

La lección práctica va más allá de los videojuegos: ruteo, moderación y pipelines de alto volumen pueden
resolverse en local, sin costo por petición y con salidas que nunca rompen el esquema. Eso sí: el formato
está garantizado; la corrección no, y hay que medirla con datos propios.

Código, datos, logs y video (reproducibles) en: https://github.com/abxda/ambar-reflex-sistema-1

— Dr. Coronado (@abxda)

#InteligenciaArtificial #LLM #IALocal #MLOps #OpenSource #Benchmark

---

## Texto alternativo del video

Video en pantalla dividida. A la izquierda, un videojuego de estilo 8 bits al atardecer en una refinería:
un comando de chaleco turquesa avanza y dispara contra soldados de armadura roja, con un abanico de
flechas ámbar que muestra la probabilidad de cada dirección de disparo. A la derecha, una terminal ámbar
con barras de probabilidad (mover, saltar, agacharse, disparar), una rosa de puntería, un medidor de
peligro, métricas de latencia y, abajo, el JSON de cada llamada al modelo desplazándose en tiempo real.
Marca de agua @abxda. — Dr. Coronado (@abxda)

## Nota de transparencia (para comentarios)

Este proyecto es un clon **independiente** de Jev: reproduce su API y su idea de «Sistema 1» con modelos
abiertos. No está afiliado a TypeSafe AI ni usa su código o sus pesos. El juego y todos sus assets son
originales. — Dr. Coronado (@abxda)

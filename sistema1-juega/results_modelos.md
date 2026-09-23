# ¿Quién decide mejor? Tres modelos locales jugando Ámbar Reflex (Sistema 1, sin pensamiento)

Mismo juego, misma partida (semilla 1987), misma variante de preguntas (D), misma política v2 y el mismo servidor compatible con Jev. Solo cambia el modelo. — Dr. Coronado (@abxda)

## Resultados

| | Qwen3.5-4B (Q8_0) | Gemma 4 E4B (Q6_K) | Qwen3.5-9B (Q5_K_M) |
|---|--:|--:|--:|
| Exactitud en 554 decisiones etiquetadas (sin presión de tiempo) | 77.8 % | 81.6 % | 82.7 % |
| Exactitud balanceada (554) | 75.1 % | 85.8 % | 86.5 % |
| Avance medio en tiempo real | 24.9 % | 14.4 % | 17.5 % |
| Mejor partida | 27.3 % | 15.1 % | 19.6 % |
| Partidas en tiempo real (N) | 5 | 3 | 3 |
| Latencia media por decisión (6 preguntas) | 408 ms | 312 ms | 591 ms |
| Frames por decisión (mediana) | 25 | 19 | 36 |
| Bajas por partida | 11.6 | 7.3 | 14.7 |
| Disparar: exactitud contra el oráculo | 97.1 % | 96.8 % | 97.9 % |
| Apuntar: exactitud contra el oráculo | 86.4 % | 54.3 % | 19.0 % |
| Saltar: % de decisiones con salto | 32 % | 74 % | 16 % |
| Decisiones en FALLBACK | 32 % | 82 % | 99 % |
| Factor de recalibración del juego (T efectiva) | 1.55 (1.16) | 0.5 (3.60) | 0.8 (2.25) |

## Lectura

- **El más listo sin presión de tiempo es Qwen3.5-9B** (82.7 % en las 554 decisiones), pero **el que llega más lejos jugando es Qwen3.5-4B** (24.9 %). En tiempo real, saber más no alcanza: pesan la latencia, los sesgos por pregunta y la calibración.
- **Qwen3.5-9B** decide mejor en texto y elimina más enemigos (14.7 por partida), pero tarda 591 ms por decisión (una cada 36 frames) y apunta mal en el juego (19.0 %). Con la recalibración del juego, el 99 % de sus decisiones cae en FALLBACK (quieto y disparar al frente).
- **Gemma 4 E4B** es el más rápido (312 ms) y muy bueno en texto, pero en el juego salta en el 74 % de las decisiones, un sesgo que lo expone. Su calibración tocó el límite de la búsqueda (factor 0.5): es el más sobreconfiado.
- **Qwen3.5-4B** acierta menos en texto (77.8 %), pero apunta mejor en el juego (86.4 %) y reacciona en 408 ms.

## Límites honestos

- **Ventaja de local:** la redacción de las preguntas (variante D) y la política de umbrales se iteraron con el Qwen3.5-4B. Los otros dos modelos juegan con preguntas que no se ajustaron para ellos.
- Qwen3.5-4B tiene N=5 partidas (el benchmark publicado); los otros, N=3. Una sola semilla y un solo nivel.
- Cuantizaciones distintas para que cada modelo quepa junto al escritorio en una RTX 3060 (Q8_0, Q6_K, Q5_K_M). Para dejar margen al escritorio, el watchdog redujo el contexto y las ramas: Gemma 4 E4B 8192 tokens y 8 ramas; Qwen3.5-9B 4096 tokens y 8 ramas (Qwen3.5-4B: 16384 y 16). Las peticiones del juego usan menos de 1,000 tokens, así que no se truncó nada.
- Todos corren **sin pensamiento**: plantilla de chat oficial con el pensamiento desactivado (verificada contra cada GGUF). 0 tokens generados.

## Videos

- `video/comparacion_modelos_vertical_1080x1920.mp4`: los tres en pila, sincronizados. Si un modelo muere, su juego queda congelado en «GAME OVER» mientras los demás siguen.
- `video/comparacion_modelos_horizontal_1920x1080.mp4`: los mismos, lado a lado.
- `video/modelos/<modelo>_1080p60.mp4`: la mejor partida de cada modelo, con su panel completo.

Reproducir: `bench/compare_models.py` (GPU, un modelo a la vez) y luego `bench/compare_video.py`. — Dr. Coronado (@abxda)

# Sistema 1 juega

**Ámbar Reflex**: un run-and-gun original de estilo consola de finales de los 80, jugado en tiempo real por
un modelo de **decisiones tipadas** (System One, API compatible con Jev de TypeSafe AI) que corre en local.
El modelo no genera texto: en cada decisión recibe una descripción compacta del frame y **seis preguntas
cerradas en una sola petición** (mover, saltar, agacharse, apuntar, disparar y peligro) y devuelve probabilidades.

Autoría: **@abxda**. Resultados en [results.md](results.md) y textos para redes en [social.md](social.md).

Nombres propuestos para el juego: **Ámbar Reflex** (usado), **Frontera Sigma** e **Iron Tempo**.

## Propiedad intelectual
Es un homenaje original al género, no un clon: no usa nombres, personajes, sprites, música, logotipos ni
niveles de ninguna franquicia. **Todos los assets se generan por código en este repositorio**:

- pixel art dibujado como matrices de caracteres (`game/sprites.py`);
- fuente bitmap de 5×7 propia (`game/font.py`);
- escenarios procedurales (`game/render.py`);
- chiptune compuesto y sintetizado con numpy (`game/audio.py`).

No hay assets CC0 externos.

## Edición visual arcade — septiembre de 2026

Sprites originales de comando con chaleco turquesa y soldados con armadura roja; carrera de cuatro
poses, arma orientable y destello ligado a los proyectiles. La refinería combina cielo tramado,
montañas, depósitos, torres y conductos con parallax; el terreno incorpora acero, remaches y marcas
de precaución. Explosiones por fases, humo y chispas se dibujan desde los efectos de la partida.
El panel conserva los datos originales, mejora el contraste y compacta sus instrumentos en vertical.
Las tarjetas de entrada y resultado usan el escenario como fondo.

El sistema visual se documenta en [DESIGN.md](DESIGN.md). Para regenerar los tres videos y cuatro
capturas de la misma partida, sin servidor ni GPU:

```bash
.venv/bin/python -m pytest -q tests
md5sum -c runs/.game_code.md5
nice -n 10 .venv/bin/python -m bench.make_videos --run runs/bench/realtime/rt-D-1987-2
```

`tests/test_render.py` comprueba que dibujar cada uno de los 1,147 fotogramas no modifica el mundo
y que volver a pintar un mismo fotograma produce los mismos píxeles. Las huellas antiguas de los
MP4 en `../REGENERAR_VIDEOS.md` corresponden al diseño previo; las duraciones y formatos se conservan.

## Estructura
```
game/      simulación determinista 60 Hz (core), nivel, render 256×240 ×4 + CRT, sprites, fuente, audio,
           describe (frame → state en texto), play_human (modo teclado)
agent/     client (esquema real validado con fixture), questions (variantes A–D), policy (umbrales y
           recalibración), oracle (etiquetas exactas y contrafactuales), modes (tiempo real, turnos,
           aleatorio, repetición), system2 (LLM generativo + JSON)
hud/       panel de terminal ámbar y abanico de flechas
bench/     server.sh, gpu_guard (watchdog), benchmark, run_variants, calibrate, analyze, report,
           render_video, make_videos, system2_phase, state_tokens
runs/      logs JSONL por decisión + meta (repetibles frame a frame)
figures/   diagramas de confiabilidad, latencia, avance      video/  3 MP4      screenshots/  4 PNG
fixtures/  respuestas reales del servidor (models.json, systemone_6q*.json)
```

## Uso
```bash
make setup                                  # venv con pygame-ce, numpy, matplotlib, pytest
bench/server.sh start                       # prerrequisito: servidor System One (jevlocal)
export JEV_BASE_URL=http://127.0.0.1:8765
make benchmark                              # todo: calibración, variantes, N=5, análisis, reporte, videos
make human                                  # línea base humana: juega y queda registrada (repetir 5 veces)
bench/server.sh stop && make system2        # opcional: Sistema 2 (Ollama qwen3.5:4b), con jevlocal detenido
make report                                 # regenerar results.md / social.md con lo que haya
```
Controles humanos: flechas (mover y apuntar en 8 direcciones), Z o espacio (saltar), X (disparar),
abajo (agacharse), Esc (salir).

## Diseño clave
- **Una petición = 6 preguntas** sobre el mismo `state`. El servidor las resuelve en un árbol de ramas
  (una pasada compartida).
- **Tiempo real asíncrono.** El juego corre a 60 FPS sin pausarse y la acción vigente se mantiene hasta
  que llega la siguiente respuesta. El log guarda el frame de la petición y el de la llegada.
- **Repetición determinista.** El video se renderiza después, frame a frame y sin ventana, a partir del
  log. Juego, flechas y panel muestran exactamente lo que el servidor respondió y cuándo llegó.
- **Oráculo exacto.** El simulador se clona para etiquetar cada decisión con rollouts contrafactuales de
  30 frames. Así se miden la exactitud práctica y la calibración sin adivinar.
- **Umbrales de confianza.** Mayor a 0.9 ACTÚA, entre 0.5 y 0.9 DUDA, menor a 0.5 FALLBACK
  (quieto + disparo al frente). La confianza se recalibra para el juego de forma exacta en el cliente
  (p' ∝ p^f).

## Seguridad de la GPU
La RTX 3060 también dibuja el escritorio, y una carga sostenida la congeló una vez (NVRM Xid 56). Por eso:

- el servidor corre en modo seguro (ubatch 512 y ≥ 2.5 GB de VRAM libres);
- se juega una partida a la vez, con enfriamiento entre ellas;
- el watchdog (`bench/gpu_guard.py`) revisa Xid, temperatura (80 °C) y VRAM, y aborta si algo falla;
- Sistema 2 nunca comparte la VRAM con System One.

— @abxda

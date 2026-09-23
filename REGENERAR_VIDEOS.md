# Regenerar los videos de la mejor partida — instrucciones para un agente

> **Objetivo:** volver a producir, idénticos, los 3 videos y las 4 capturas de la **mejor partida en
> tiempo real** de «Sistema 1 juega» (Ámbar Reflex), a partir de sus logs.
> **No** se juega de nuevo, **no** se usa la GPU y **no** hace falta el servidor System One.
> Autoría: @abxda.

## 1. Qué se regenera y por qué es exacto

Cada partida quedó registrada en dos archivos:

- `<run>.meta.json`: semilla, línea de tiempo de acciones por frame, eventos y resultado.
- `<run>.jsonl`: una línea por decisión, con la respuesta cruda del servidor, la latencia y los frames
  de petición y de llegada.

La simulación (`game/core.py` + `game/level.py`) es **determinista**. Con esos logs, la partida se
**repite frame a frame** en CPU y se renderiza sin ventana (SDL `dummy`). Las cifras del panel salen del
log, no se recalculan con el modelo.

Se verificó el 22/09/2026: regenerar en otra carpeta dio **MD5 idénticos** en los 3 MP4 y capturas
idénticas byte a byte.

| Salida | Formato | Duración |
|---|---|---|
| `video/sistema1_1080p60.mp4` | 1920×1080, 60 fps, H.264 + AAC | 27.12 s (título 3 s + juego 19.1 s + cierre 5 s) |
| `video/sistema1_vertical_1080x1920.mp4` | 1080×1920, 60 fps, H.264 + AAC | 27.12 s |
| `video/sistema1_momentos_clave.mp4` | 1920×1080, 60 fps, H.264 + AAC | 35.12 s (partida + 2 repeticiones a 0.5x) |
| `screenshots/01_inicio.png`, `02_alta_confianza.png`, `03_fallback.png`, `04_accion.png` | PNG 1920×1080 | — |
| `video/video_meta.json` | JSON (partida y momentos clave) | — |

## 2. La mejor partida (fija, no la cambies)

- **Partida:** `runs/bench/realtime/rt-D-1987-2`, la mejor de las 5 en tiempo real.
- **Resultado:** 27.3 % de avance, puntaje 1650, 12 bajas, 19.1 s de juego (1147 frames).
- **Configuración:** variante de preguntas **D** (B + compensación de latencia), política v2, semilla 1987.
- **Momentos clave detectados:** confianza alta 0.9477 en el frame 124, FALLBACK en el frame 324,
  primera baja en el 136, primera muerte en el 315, primer salto en el 199. No hubo jefe.

Directorio de trabajo: **`sistema1-juega/`** dentro de la raíz del repositorio.
Todos los comandos siguientes se ejecutan desde ahí.

### Entradas y huellas (verificar antes de empezar)

```
f21f956aa893b28c2dfe057fc29f7d62  runs/bench/realtime/rt-D-1987-2.jsonl
4f24f3a125bc3fac27dbee1f907e3217  runs/bench/realtime/rt-D-1987-2.meta.json
91dbed84d8cf25e6322b4f5a4f682c94  game/core.py
f1e89eb862f9852abd1804ed29ea8619  game/level.py
```

```bash
md5sum runs/bench/realtime/rt-D-1987-2.jsonl runs/bench/realtime/rt-D-1987-2.meta.json
md5sum -c runs/.game_code.md5          # core.py y level.py: deben decir OK
```

Si `core.py` o `level.py` **no** dicen OK, la simulación cambió y la repetición no reproducirá la
partida. Detente y restaura esos dos archivos; no «arregles» los logs.

## 3. Requisitos

- Linux con `ffmpeg` que tenga `libx264` y `aac` (se comprueba con `ffmpeg -encoders | grep -E "libx264|aac"`).
- El venv del proyecto en `.venv` (Python 3.12, pygame-ce, numpy, matplotlib). Si falta: `make setup`.
- **No** hacen falta GPU, CUDA, el servidor `jevlocal`, Ollama ni internet.

## 4. Procedimiento

```bash
cd sistema1-juega        # desde la raíz del repositorio

# 1) comprobaciones (deben pasar las 10 pruebas; incluyen que la repetición coincide con los logs)
.venv/bin/python -m pytest -q tests

# 2) regenerar los 3 videos + 4 capturas de la mejor partida (unos 70 s de CPU; con nice para no estorbar)
nice -n 10 .venv/bin/python -m bench.make_videos --run runs/bench/realtime/rt-D-1987-2

# 3) (opcional) reescribir results.md y social.md para que citen la partida del video
.venv/bin/python -m bench.report
```

Para regenerar **en otra carpeta** sin tocar los publicados, por ejemplo para comparar:

```bash
nice -n 10 .venv/bin/python -m bench.make_videos --run runs/bench/realtime/rt-D-1987-2 --out-dir /tmp/regen
```

## 5. Verificación

```bash
for f in video/*.mp4; do echo "$f  $(md5sum < $f | cut -c1-12)  $(ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration -of csv=p=0 $f | tr '\n' ' ')"; done
```

Valores esperados si el código de render **no** cambió (mismo ffmpeg/libx264):

| Archivo | MD5 (12 primeros caracteres) | Vídeo | Duración |
|---|---|---|---|
| sistema1_1080p60.mp4 | `c9d3d47a5ddf` | h264 1920×1080 60/1 + aac | 27.116667 |
| sistema1_momentos_clave.mp4 | `d59a277f04eb` | h264 1920×1080 60/1 + aac | 35.116667 |
| sistema1_vertical_1080x1920.mp4 | `ba255395f865` | h264 1080×1920 60/1 + aac | 27.116667 |

Si los MD5 difieren solo porque cambió la versión de ffmpeg/libx264, basta con que coincidan resolución,
fps, códecs y duración. Además, revisa visualmente un fotograma:

```bash
ffmpeg -loglevel error -y -ss 12 -i video/sistema1_1080p60.mp4 -frames:v 1 /tmp/check.png
```

Qué debe verse:

- a la izquierda, el juego en pixel art con CRT;
- a la derecha, el panel ámbar con barras, rosa de puntería, medidor de peligro, métricas y log;
- el abanico de flechas saliendo del soldado;
- la marca **@abxda** en minúsculas, semitransparente, en el juego y en el panel.

## 6. Qué NO hacer

- **No** correr `make benchmark`, `make system2` ni nada que juegue partidas nuevas. Usan la GPU, que
  también dibuja el escritorio: una carga sostenida ya congeló la máquina (NVRM Xid 56). Regenerar
  videos no necesita la GPU.
- **No** editar `game/core.py` ni `game/level.py`: rompe la repetición.
- **No** elegir otra partida, salvo que el usuario lo pida. `make_videos` sin `--run` toma la de mayor
  avance, que hoy es la misma, pero fijarla evita sorpresas.
- **No** detener procesos con `pkill -f <patrón>`, porque puede matar al propio shell. Usa PID.
- **No** modificar los logs de `runs/`: son la evidencia de las cifras publicadas.

## 7. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `replay diverged` o la prueba `test_replay_matches_log` falla | cambió `core.py` o `level.py` | restaurarlos; `md5sum -c runs/.game_code.md5` |
| `ffmpeg failed` | falta libx264 o no hay espacio en disco | instalar ffmpeg completo; revisar `df -h` |
| `No module named pygame` | venv ausente | `make setup` |
| aparece `?` en un texto | carácter sin glifo en `game/font.py` | agregar el glifo o mapearlo en `ACCENTS` (ver ARQUITECTURA_GRAFICA.md) |
| error de pantalla o display de SDL | falta el modo sin ventana | los scripts ya fijan `SDL_VIDEODRIVER=dummy`; no ejecutar `game/play_human.py` |

Para **cambiar el diseño** (colores, panel, sprites, tipografía, tarjetas) y luego regenerar, lee
`ARQUITECTURA_GRAFICA.md`.

— @abxda

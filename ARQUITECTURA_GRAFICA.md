# Arquitectura gráfica de «Sistema 1 juega» — guía para mejorar el diseño y regenerar el video

> **Para quién:** un agente que va a **rediseñar lo visual** (pixel art, escenarios, panel, flechas,
> tipografía, tarjetas de título y cierre, audio) y **volver a generar** los videos de la mejor partida,
> **sin alterar los datos ni la partida**. Para regenerar sin cambios, ve a `REGENERAR_VIDEOS.md`.
> Proyecto: `sistema1-juega/` (raíz del repositorio). Autoría: @abxda.

---

## 1. Idea central: el render es una capa sobre una repetición determinista

```
 runs/bench/realtime/rt-D-1987-2.meta.json ──┐  (semilla + línea de tiempo de acciones + eventos)
 runs/bench/realtime/rt-D-1987-2.jsonl ──────┤  (una decisión por línea: respuesta cruda del servidor,
                                             │   latencia, frame de petición y de llegada)
                                             ▼
                           agent/modes.py: replay(meta, on_frame)
                  re-simula game/core.py frame a frame (60 Hz, determinista)
                                             │  on_frame(world, applied, current)  ← cada frame
                                             ▼
   ┌──────────────────────────── bench/render_video.py: compose() ────────────────────────────┐
   │ game/render.py  draw_world(256×240) → upscale(×4, CRT) ─┐                                 │
   │ hud/panel.py    draw_overlay(abanico de flechas) ───────┼→ lienzo 1920×1080 o 1080×1920  │
   │ hud/panel.py    draw_panel(terminal ámbar)  ←── RunView (decisiones llegadas ≤ frame) ────┤
   │ hud/panel.py    watermark("@abxda", 40 %)  ─────────────┘                                 │
   └───────────────────────────────────────────────────────────────────────────────────────────┘
                                             │  RGB crudo por stdin
                                             ▼
          ffmpeg (libx264 crf 18, yuv420p, 60 fps) + audio.wav (game/audio.py: chiptune + SFX por eventos)
                                             ▼
             video/*.mp4  ·  screenshots/*.png   (bench/make_videos.py orquesta los 3 videos)
```

**Consecuencia clave:** puedes cambiar *cómo se ve* todo sin tocar *qué pasó*. La partida, las
probabilidades y las latencias vienen de los logs; el render solo las dibuja. Todo corre en CPU, sin GPU
ni servidor.

---

## 2. Mapa de archivos: qué puedes tocar

| Archivo | Rol | ¿Editable para diseño? |
|---|---|---|
| `game/render.py` (218 líneas) | mundo a 256×240: cielo, siluetas con parallax, terreno, plataformas, enemigos, balas, explosiones, HUD interno; `upscale()` ×4 + scanlines CRT | ✅ sí |
| `game/sprites.py` (75) | pixel art como matrices de caracteres + paleta `PAL`; `sprite()` con caché, espejo y tinte | ✅ sí |
| `game/font.py` (137) | fuente bitmap propia de 5×7 (mayúsculas, minúsculas, dígitos, signos) + `ACCENTS` | ✅ sí |
| `hud/panel.py` (223) | panel de terminal (`draw_panel`), abanico de flechas (`draw_overlay`), `watermark`, colores y `RunView` | ✅ sí (sin cambiar de dónde salen los datos) |
| `bench/render_video.py` (173) | `LAYOUTS` (geometría), `card` (título y cierre), `compose`, `Writer` (ffmpeg), `render` (clips y cámara lenta) | ✅ sí |
| `bench/make_videos.py` (104) | elige momentos clave y capturas; arma los 3 videos | ✅ con cuidado (ver §7) |
| `game/audio.py` (118) | chiptune original (La menor, 150 BPM) y SFX sintetizados con numpy | ✅ sí |
| `bench/preview_frame.py` (79) | **vista previa rápida** (0.5 s) de fotogramas y tarjetas | ✅ herramienta |
| `game/core.py`, `game/level.py` | **simulación**: física, colisiones, enemigos, nivel | ⛔ **NO**: rompe la repetición |
| `agent/*`, `game/describe.py` | agente, política y texto del estado | ⛔ no aplica al video |
| `runs/**` | logs = evidencia de las cifras | ⛔ solo lectura |

> **Ojo con los tamaños de sprite:** las cajas de colisión viven en `core.py`, no en los sprites. Puedes
> redibujar sprites de otro tamaño sin afectar la física, pero mantenlos anclados igual: centro en `x`,
> pies en `y`. Así lo visual sigue coincidiendo con lo que ocurre.

---

## 3. Contratos de datos que el render consume (solo lectura)

**Registro de decisión** (`*.jsonl`, una por línea), claves que usa el HUD:
- `req_frame`, `arr_frame`: frame en que se pidió y frame en que llegó (el panel cambia en `arr_frame`).
- `raw.answers.move|aim`: `{type, choice, probabilities{opción: p}, confidence}`.
- `raw.answers.jump|crouch|shoot`: `{type: "noul", noul: p}`.
- `raw.answers.danger`: `{type: "score", score, legend, probabilities, confidence}`.
- `action`: `{move ∈ {-1,0,1}, jump, crouch, aim ∈ {E,NE,N,NW,W,SW,S,SE}, shoot}` (lo que ejecutó).
- `tag` ∈ {`ACTUA`, `DUDA`, `FALLBACK`}; `conf` (confianza calibrada mínima de mover/apuntar); `danger` 0–1.
- `rtt_ms` (latencia de ida y vuelta), `input_tokens`, `state` (texto enviado).
- `labels` / `outcome`: etiquetas del oráculo (no se muestran; sirven para el análisis).

**Meta** (`*.meta.json`): `seed`, `timeline` `[[frame, acción], …]`, `events` `[[frame, nombre], …]`
(`shoot`, `jump`, `hit`, `explode`, `die`, …), `frames`, `result{progress, score, kills, deaths, seconds, …}`,
`variant`, `policy`, `factor`.

**`RunView`** (`hud/panel.py`) entrega al panel, en cada frame, `last` (la última decisión llegada) y
`metrics(frame)` (n, latencia actual/media/p95, decisiones/s, % FALLBACK/DUDA, serie de latencias). Si
agregas un indicador nuevo, **calcúlalo aquí desde los logs**; nunca inventes ni suavices cifras.

**Objeto `world`** (solo lectura durante el render): `px, py, cam, facing, on_ground, crouching, aim,
weapon, shield, invuln, dead_timer, lives, score, kills, enemies[], eshots[], pshots[], pickups[], fx[],
frame, progress()`. En `render.py` hay ejemplos de uso.

---

## 4. Geometría y sistema visual actual

**Resolución del juego:** 256×240 nativos, escalados ×4 con vecino más cercano (1024×960) + scanlines.

**Diseños** (`bench/render_video.py → LAYOUTS`):

| Layout | Lienzo | Juego (x, y, w, h) | Panel (x, y, w, h) |
|---|---|---|---|
| `landscape` | 1920×1080 | (64, 60, 1024, 960) | (1136, 24, 760, 1032) |
| `vertical` | 1080×1920 | (28, 60, 1024, 960) | (28, 1040, 1024, 852) |

**Paleta de la terminal** (`hud/panel.py`): `AMBER (255,176,0)` · `BRIGHT (255,224,140)` · `DIM (120,82,0)` ·
`FAINT (52,36,0)` · `ORANGE (255,136,32)` para DUDA · `RED (255,84,60)` para FALLBACK · `BG (8,6,2)`.

**Paleta de sprites** (`game/sprites.py → PAL`, un carácter por color): `K` contorno, `T/D` armadura verde
azulado del protagonista, `V` visor ámbar, `b/B/R/r` soldado enemigo (arena y rojo), `G/g` metal, `Y/O`
luces, `W/C` cápsula de mejora.

**Temas del escenario** (`game/render.py → THEMES`), uno por sección: `REFINERIA` (atardecer naranja),
`CANON` (morado), `REACTOR` (azul petróleo oscuro), `NUCLEO` (magenta). Cada tema tiene 4 franjas de
cielo, silueta lejana, estructuras intermedias y tierra (borde, cuerpo y tramado). La mejor partida solo
recorre **REFINERÍA**, porque avanza 27 %.

**Tipografía:** fuente propia de 5×7 en celdas de 6×9 px escaladas ×1 a ×7. `font.draw(surface, texto, x, y, color, escala, alpha)`.
Todo carácter sin glifo sale como `?`: agrégalo a `G` o mapéalo en `ACCENTS`, como se hizo con `×` → `x`.

**Elementos del panel** (de arriba abajo en `draw_panel`):
1. título «SISTEMA 1 JUEGA», modelo y «0 TOKENS GENERADOS · 1 PETICIÓN = 6 PREGUNTAS»;
2. MOVER con 3 barras y su `confidence`;
3. SALTAR, AGACHARSE y DISPARAR como P(sí);
4. rosa de 8 direcciones (APUNTAR) y medidor analógico de PELIGRO;
5. etiqueta ACTÚA / DUDA / FALLBACK con la confianza calibrada;
6. métricas en cuadrícula de 3×3;
7. gráfica de latencia;
8. log con desplazamiento.

**Abanico de flechas** (`draw_overlay`): 8 flechas desde el pecho del soldado, con opacidad igual a la
probabilidad de cada dirección de `aim`, más la flecha de movimiento. Se desvanecen en 0.4 s desde
`arr_frame`.

**Tarjetas** (`card`): título de 3 s (nombre del juego que se escribe letra por letra) y cierre de 5 s
con las cifras de `summary()`. En el corte de momentos clave duran 2 s y 4 s.

**Audio:** `render_track()` genera la música en loop más los SFX en el frame exacto de cada evento. Las
repeticiones a 0.5x llevan solo música.

---

## 5. Reglas obligatorias (no negociables)

1. **Propiedad intelectual:** homenaje original. Sin nombres, sprites, logotipos, música ni niveles de
   ninguna franquicia. Todo asset nuevo se dibuja o sintetiza en el repositorio, o es CC0 con su licencia
   documentada en `sistema1-juega/README.md`.
2. **Marca de agua `@abxda`** al ~40 % de opacidad (`alpha≈102`), en minúsculas, visible en el juego y en
   el panel de todas las versiones, y en capturas y gráficas.
3. **Veracidad:** todo número o probabilidad en pantalla sale de los logs (`RunView`, `summary`).
   ACTÚA, DUDA y FALLBACK se muestran tal como quedaron registrados. No ocultes los fallos: son parte
   del mensaje («el formato está garantizado; la corrección no»).
4. **Sincronía:** el panel y las flechas cambian en `arr_frame`, no en `req_frame`. Eso muestra la
   latencia real.
5. **Legibilidad en móvil:** texto de escala ≥ 2 en el panel horizontal y valores siempre legibles sobre
   las barras (hoy llevan una placa oscura propia).
6. **No tocar** `game/core.py`, `game/level.py` ni `runs/**`. Tampoco lances partidas nuevas: usan la GPU,
   que también dibuja el escritorio y ya se congeló una vez.

---

## 6. Ciclo de trabajo recomendado

```bash
cd sistema1-juega        # desde la raíz del repositorio

# 1) antes de cambiar nada: línea base
.venv/bin/python -m pytest -q tests                       # 10 pruebas; incluye repetición == logs
.venv/bin/python -m bench.preview_frame --frames 124 324 600 --layout landscape vertical
.venv/bin/python -m bench.preview_frame --card title
.venv/bin/python -m bench.preview_frame --card outro
#    → preview/landscape_f124.png, preview/vertical_f124.png, preview/card_title.png, …

# 2) editar render.py / sprites.py / panel.py / render_video.py / font.py / audio.py
# 3) volver a previsualizar (0.5 s por llamada) y mirar los PNG; repetir hasta estar conforme
# 4) comprobar que la simulación sigue intacta
md5sum -c runs/.game_code.md5 && .venv/bin/python -m pytest -q tests

# 5) regenerar los videos en una carpeta aparte, revisarlos y luego publicar sobre video/
nice -n 10 .venv/bin/python -m bench.make_videos --run runs/bench/realtime/rt-D-1987-2 --out-dir /tmp/diseno_v2
ffmpeg -loglevel error -y -ss 12 -i /tmp/diseno_v2/video/sistema1_1080p60.mp4 -frames:v 1 /tmp/diseno_v2/check.png
nice -n 10 .venv/bin/python -m bench.make_videos --run runs/bench/realtime/rt-D-1987-2   # publica en video/
```

**Fotogramas útiles para revisar:**

| Frame | Qué ocurre |
|---|---|
| 124 | decisión de confianza alta (0.95, ACTÚA): contacto con enemigos |
| 136 | primera explosión |
| 199 | primer salto |
| 315 | primera muerte |
| 324 | FALLBACK |
| 600 | juego en curso |
| 1146 | último frame |

**Tiempo de regeneración:** unos 70 s de CPU para los 3 videos.

**Tras un rediseño los MD5 cambian** (es lo esperado). Valida con `ffprobe`: 1920×1080 y 1080×1920 a
60 fps, H.264 + AAC, y duraciones de 27.12 / 27.12 / 35.12 s, salvo que cambies a propósito la duración
de las tarjetas.

---

## 7. Cómo extender sin romper nada

- **Nuevo elemento del panel:** agrégalo en `draw_panel` y respeta el flujo vertical con `y`. Comprueba
  que quepa en **ambos** layouts: el vertical es más bajo (852 px) y hoy muestra pocas líneas de log.
- **Nuevo layout** (por ejemplo 1080×1080 cuadrado): agrega una entrada en `LAYOUTS`, pruébalo con
  `preview_frame --layout cuadrado` y añade un `render(...)` en `make_videos.main()`.
- **Nuevo tema o paleta:** edita `THEMES` y `PAL`. El render usa `section_at(cam+128)` para escoger el
  tema.
- **Sprites animados:** añade matrices y alterna por `world.frame // n`, como `PLAYER_RUN` o `SOLDIER_WALK`.
- **Efectos (partículas, sacudida de cámara):** derívalos de `world.fx` y `meta["events"]`. Una sacudida
  debe desplazar solo el dibujo, nunca el `world`.
- **Subtítulos o leyendas explicativas:** usa clips con `caption` en `render()`. Los clips aceptan
  `(inicio, fin, velocidad, leyenda)`; la velocidad 0.5 repite cada frame dos veces con solo música.
- **Cambiar momentos clave o capturas:** `key_moments()` y `highlight_clips()` en `make_videos.py`. Deben
  salir de los logs; el corte debe durar 30–60 s.
- **Rendimiento:** cada frame del panel dibuja cientos de glifos. Si crece mucho, pre-renderiza lo
  estático en una `Surface` y reutilízala.

---

## 8. Ideas de mejora priorizadas (sugerencias)

1. **Layout vertical:** reorganizar el panel (rosa y medidor más chicos, lado a lado) para que quepan
   5–6 líneas de log; hoy cabe 1.
2. **Protagonista con más frames:** carrera de 4 frames, retroceso del arma al disparar y destello en el
   cañón.
3. **Explosiones con más estilo:** anillos de 3 colores y chispas que dependan de `world.fx`, más un
   *hit-flash* blanco en el enemigo.
4. **Panel más legible a distancia:** barras con marcas en 0.5 y 0.9 (los umbrales de la política) y la
   opción ganadora con un borde brillante.
5. **Línea de tiempo de latencia en el video:** una barra delgada bajo el juego que marque `req_frame` y
   `arr_frame` de la decisión vigente, para *ver* los 25 frames de retraso.
6. **Tarjeta de cierre comparativa:** Sistema 1 (408 ms, 24.9 %) frente a Sistema 2 (1041 ms, 10.3 %) y
   aleatorio (4.6 %), con cifras leídas de `results.json`, no escritas a mano.
7. **Parallax con tercera capa y tramado de cielo** en `_background`.
8. **Audio:** sidechain simple (bajar la música 30 % durante 100 ms en cada `explode`) y un jingle para
   la tarjeta de título.

Cualquier cifra nueva que aparezca en pantalla debe existir también en `sistema1-juega/results.md` o
calcularse desde `runs/`. Las pruebas `tests/test_consistency.py` vigilan esto para `social.md`.

— @abxda

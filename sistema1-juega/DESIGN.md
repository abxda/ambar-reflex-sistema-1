---
name: Ámbar Reflex — Sistema 1 juega
description: Arcade militar original de finales de los ochenta, con telemetría ámbar verificable.
colors:
  instrument-amber: "#ffb000"
  instrument-bright: "#ffe08c"
  instrument-dim: "#b88941"
  instrument-faint: "#342400"
  instrument-bg: "#080602"
  doubt-orange: "#ff8820"
  fallback-red: "#ff543c"
  canvas-navy: "#0a111a"
  outline-ink: "#0c121d"
  vest-teal: "#287d89"
  vest-shadow: "#174252"
  hostile-red: "#c83018"
  hostile-shadow: "#781810"
  skin-copper: "#eda363"
  skin-light: "#ffd593"
  gun-steel: "#aabbbe"
  gun-shadow: "#45596a"
  refinery-dusk: "#202641"
  refinery-copper: "#ec9569"
  ground-steel: "#2a3843"
  ground-rim: "#aab7ae"
typography:
  label:
    fontFamily: "Ámbar Reflex bitmap 5x7 (game/font.py)"
    fontSize: "9px"
  body:
    fontFamily: "Ámbar Reflex bitmap 5x7 (game/font.py)"
    fontSize: "18px"
  title:
    fontFamily: "Ámbar Reflex bitmap 5x7 (game/font.py)"
    fontSize: "36px"
rounded:
  square: "0px"
spacing:
  panel-inset: "20px"
  move-gap: "6px"
components:
  telemetry-panel:
    backgroundColor: "{colors.instrument-bg}"
    textColor: "{colors.instrument-amber}"
    rounded: "{rounded.square}"
    padding: "{spacing.panel-inset}"
  probability-track:
    backgroundColor: "{colors.instrument-faint}"
    textColor: "{colors.instrument-amber}"
    rounded: "{rounded.square}"
---

# Design System: Ámbar Reflex

## Overview

**Creative North Star: "Refinería al atardecer, instrumentos ámbar"**

El combate grabado dirige la experiencia: un arcade militar de finales de los ochenta, con brazos descubiertos, chaleco verde azulado, enemigos rojos y armas mecanizadas. El referente de género elegido es Super Contra; los personajes, escenarios, tipografía y demás assets son originales del proyecto.

La densidad procede del pixel art y de instrumentos que muestran decisiones reales. Este documento captura la implementación nativa en pygame; no describe una interfaz web. Las fuentes de producto son `README.md` y `../ARQUITECTURA_GRAFICA.md`; para valores visuales vigentes manda el código.

**Key Characteristics:**

- Pixel art nativo y ampliación entera sin suavizado.
- Acero azul, cielo cobrizo y terminal ámbar.
- Profundidad mediante siluetas, parallax, tramado y detalles mecánicos.
- Telemetría sincronizada con la llegada real de cada decisión.

## Colors

El ámbar une los instrumentos; el mundo contrapone acero frío y luz cálida.

- **Primary:** `instrument-amber` para probabilidades y lecturas; `instrument-bright` para títulos, valores y selección; `instrument-dim` para etiquetas secundarias; `instrument-faint` para pistas vacías.
- **Secondary:** `vest-teal` y `vest-shadow` distinguen al protagonista; `hostile-red` y `hostile-shadow` caracterizan enemigos. `skin-copper` y `skin-light` modelan brazos y rostro, con `gun-steel` y `gun-shadow` en armas.
- **Tertiary:** `doubt-orange` identifica DUDA y `fallback-red` FALLBACK. ACTÚA usa `instrument-bright`. Los nombres de estado siguen visibles junto al color.
- **Neutral:** `instrument-bg` protege las cifras; `canvas-navy` enmarca el video; `outline-ink` separa siluetas. `ground-steel` y `ground-rim` definen el suelo de refinería.

Los tokens del cielo recogen los extremos de REFINERIA; la rampa completa y los temas CANON, REACTOR y NUCLEO viven en `game/render.py:THEMES`. No sustituirlos por colores generados. La paleta efectiva de sprites incluye las sobreescrituras de `PAL.update()`.

## Typography

Una sola fuente bitmap propia de 5×7, dibujada en celdas de 6×9 píxeles. Los tamaños de frontmatter expresan la altura de celda, no métricas de una fuente CSS. Cada carácter avanza seis píxeles por unidad de escala; no hay antialiasing ni familia de respaldo del sistema.

Escala 1 para HUD nativo; escala 2 para el cuerpo del panel; escala 3 para el nombre sobre el juego y estados; escala 4 para «SISTEMA 1 JUEGA». Las tarjetas aceptan escalas mayores y las reducen según el ancho. Conservar minúsculas en `@abxda` y los acentos españoles admitidos en `game/font.py`.

## Layout

El mundo mide 256×240 píxeles, con tiles de 16 píxeles. La ampliación ×4 produce un juego de 1024×960. Son composiciones de video fijas, no breakpoints de navegador:

| Formato | Lienzo | Juego: x, y, ancho, alto | Panel: x, y, ancho, alto |
| --- | --- | --- | --- |
| Horizontal | 1920×1080 | 64, 60, 1024, 960 | 1136, 24, 760, 1032 |
| Vertical | 1080×1920 | 28, 60, 1024, 960 | 28, 1040, 1024, 852 |

El panel tiene borde de 3 píxeles, inset de 20, tres barras de movimiento separadas por 6 píxeles y métricas en cuadrícula de tres columnas. Por debajo de 900 píxeles de alto reduce la rosa de 80 a 54 píxeles de radio y la gráfica de 50 a 32 píxeles. El HUD interno ocupa los primeros 25 píxeles del mundo.

## Elevation & Depth

La profundidad se construye con montañas lejanas, torres, depósitos, tuberías y suelo remachado. El parallax usa factores de cámara 0.2, 0.5 y 0.75; el sol se desplaza a 0.08. El cielo tiene bandas tramadas. No hay sombras difusas de interfaz; el título grande usa una copia desplazada de la fuente como sombra dura.

La ampliación CRT superpone una fila negra con alpha 70 cada cuatro filas de salida. Las explosiones derivan de `world.fx`: humo, núcleos cálidos y chispas. El destello del arma depende de proyectiles realmente emitidos; la animación de carrera tiene cuatro poses y cambia cada cinco frames cuando el jugador se mueve.

## Shapes

Contornos de un píxel, placas rectangulares, cantos claros, ranuras y remaches. Los instrumentos circulares se reservan para la rosa de dirección y el peligro; las barras conservan esquinas rectas. Los sprites se anclan al centro horizontal y a los pies de la entidad. Su dibujo no redefine cajas de colisión.

## Components

- **Mundo arcade:** orden de dibujo: fondo, terreno, enemigos, jugador, disparos/efectos y HUD. Conservar la separación de siluetas y proyectiles.
- **Panel de telemetría:** título y modelo, probabilidades, rosa de ocho direcciones, peligro, estado, métricas, latencia y log. El borde se ilumina durante cuatro frames al llegar una respuesta.
- **Barras de probabilidad:** marcas en 0.5 y 0.9; borde brillante para selección. Etiqueta y valor tienen placas oscuras propias para permanecer legibles sobre el relleno.
- **Abanico de decisión:** opacidad proporcional a la probabilidad; desvanecimiento de 0.4 segundos desde `arr_frame`. No anticipar la respuesta al frame de petición.
- **Tarjetas:** escenario de refinería oscurecido, placa azul oscura y líneas ámbar. Los títulos grandes se revelan por caracteres; las cifras de cierre proceden de `summary()`.
- **Autoría:** `@abxda` en juego, panel y tarjetas, con alpha 102 de 255. Mantenerla en ambas composiciones.

## Do's and Don'ts

- **Do** conservar resolución nativa, ampliación entera y fuente bitmap propia.
- **Do** comprobar legibilidad y encaje en horizontal y vertical, incluidas cifras sobre barras.
- **Do** derivar estados, cifras y tiempos de los logs; el render solo lee la simulación.
- **Do** mantener originales los assets y visible la autoría `@abxda`.
- **Don't** modificar `game/core.py`, `game/level.py`, políticas o `runs/**` para mejorar el aspecto.
- **Don't** ocultar FALLBACK, inventar probabilidades o anticipar decisiones a `req_frame`.
- **Don't** importar personajes, sprites, logotipos, música o niveles de franquicias.
- **Don't** añadir controles web, fuentes suavizadas o paneles redondeados ajenos al sistema nativo.

# Verificación de la edición arcade — 2026-09-22

Se regeneraron y publicaron los tres videos, cuatro PNG y `video/video_meta.json` a partir de
`runs/bench/realtime/rt-D-1987-2`, en CPU y sin lanzar partidas nuevas.

## Partida intacta

`pytest -q tests`: **13 passed**. La prueba añadida recorre los 1,147 fotogramas del log, compara
el mundo serializado antes y después del dibujo y verifica que repintarlo produce píxeles idénticos.
Las pruebas existentes comprueban que la repetición coincide con los logs.
Dos casos adicionales verifican que el panel dibuja exactamente una marca con alpha 102,
tanto antes de la primera respuesta como después de recibir decisiones.

Las huellas de entrada y simulación siguen siendo las documentadas:

| Archivo | MD5 |
|---|---|
| `game/core.py` | `91dbed84d8cf25e6322b4f5a4f682c94` |
| `game/level.py` | `f1e89eb862f9852abd1804ed29ea8619` |
| `rt-D-1987-2.jsonl` | `f21f956aa893b28c2dfe057fc29f7d62` |
| `rt-D-1987-2.meta.json` | `4f24f3a125bc3fac27dbee1f907e3217` |

No se editaron `agent/`, `runs/`, física, colisiones, nivel ni audio. El panel sigue avanzando en
`arr_frame`; las métricas y probabilidades conservan sus fuentes originales.

## Entregables comprobados

| Video | Resolución | FPS | Fotogramas | Duración | MD5 |
|---|---|---|---|---|---|
| `sistema1_1080p60.mp4` | 1920×1080 | 60 | 1627 | 27.116667 s | `1698eb5f16b2684139dec4e73e17b3f5` |
| `sistema1_vertical_1080x1920.mp4` | 1080×1920 | 60 | 1627 | 27.116667 s | `4be425cbbc7a398e17b9fb41a374719e` |
| `sistema1_momentos_clave.mp4` | 1920×1080 | 60 | 2107 | 35.116667 s | `0c473a4015f2a205b8077ae0d1aef3d8` |

`ffprobe` confirmó H.264 y AAC en los tres archivos. `ffmpeg -v error -xerror -i VIDEO -f null -`
decodificó cada archivo completo sin errores. Se inspeccionaron fotogramas extraídos de los MP4
horizontal y vertical a los 12 s, y de momentos clave a los 24 s (repetición a 0.5×).

Capturas regeneradas de 1920×1080: `01_inicio.png`, `02_alta_confianza.png`, `03_fallback.png`,
`04_accion.png`. `video_meta.json` conserva la partida y momentos 124 / 324 / 136 / 315 / 199.
Se comprobó igualdad byte a byte entre las salidas revisadas y los archivos publicados.

## Revisión de diseño

| Área | Dictamen de la revisión independiente |
|---|---|
| Fidelidad arcade militar | Pass |
| Legibilidad y distribución horizontal/vertical | Pass |
| Restricciones de la capa visual | Pass |
| Hallazgos materiales | Ninguno |

Se revisaron seis previews: combate, explosión, salto, FALLBACK vertical, título y cierre.
Se conservan marcas `@abxda` en minúsculas y alfa 102 en juego/panel; las tarjetas también llevan
marca. Los sprites son matrices originales dibujadas en el repositorio. Impeccable orientó la
jerarquía, el contraste y la revisión visual; su detector no reportó hallazgos en los archivos Python.

Copia temporal de las salidas anteriores: `/tmp/ambar-arcade-axhGEf/anteriores/`.

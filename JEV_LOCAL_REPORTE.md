# Jev local: análisis, selección y servidor compatible

*Fecha: 22 de septiembre de 2026 · Máquina: "la bestia" (RTX 3060 12 GB, 128 CPU, 247 GB RAM)*

## 1. Qué es Jev (según el PDF)

**Jev** es el primer modelo "System One" de **TypeSafe AI**, lanzado el 15 de septiembre de 2026 con una
ronda semilla de 40 M USD liderada por DCVC. Hay que aclarar tres cosas:

- **No es un chatbot ni genera texto.** Recibe un `state` (texto o JSON) y un mapa de preguntas tipadas, y
  en una sola pasada devuelve probabilidades para respuestas fijadas de antemano:
  - **Choice:** una opción de un conjunto (2 a 255 opciones) → `choice`, `probabilities`, `confidence`
  - **Score:** niveles ordenados (2 a 10) → `score` (media ponderada), `legend`, `probabilities`, `confidence`
  - **Noul:** sí/no → `noul` ∈ [0,1]
- Está entrenado con **RLCD** (aprendizaje por refuerzo con reglas de puntuación propias) para que sus
  probabilidades estén calibradas.
- **Es cerrado:** solo API hospedada, con lista de espera, sin pesos, sin paper y sin parámetros publicados.
  Correrlo localmente es imposible, así que lo único posible es **emularlo**.

El PDF advierte que las cifras de 445× más barato y 194× más rápido son autorreportadas. La reproducción
independiente más cuidadosa encontró ~2.9× más rápido y ~12× más barato, con menor exactitud que Haiku 4.5.
Su valor depende mucho de cómo se diseñen las preguntas.

## 2. Emuladores ordenados por benchmark (JevBench v1.3.0)

JevBench mide 534 decisiones (220 difíciles) y combina Intelligence, Calibration, Speed y Cost en un
puntaje (media geométrica). La columna **"¿Cabe aquí?"** considera ~10 GB útiles de VRAM, porque la
misma GPU dibuja el escritorio.

| # | Sistema | Score | Intel. | Calib. | Pesos | Base / tamaño | ¿Cabe aquí? |
|--:|---|--:|--:|--:|---|---|---|
| 1 | Jev 1.13.0 (TypeSafe) | 74.4 | 85.7 | 82.7 | cerrado | no publicado | ✗ solo API |
| **2** | **SemIf (Qwen3.5-4B)** | **73.1** | 79.0 | 72.6 | abiertos | Qwen3.5-4B congelado | **✓ elegido** |
| 3 | djev (Maisa) | 73.0 | 82.7 | 65.4 | abiertos | DiffusionGemma 26B-A4B (25.2B totales) | ✗ ~15 GB en Q4; requiere vLLM |
| 4 | Winnow-12B Q8 | 71.2 | 82.0 | 72.0 | abiertos | 12B Q8 (~13 GB) | ✗ |
| 5 | reflex 4B | 70.3 | 80.1 | 75.2 | abiertos (MIT) | Qwen3.5-4B congelado + prompt markdown | ✓ integrado como perfil |
| 6 | jqv | 68.6 | 79.3 | 79.0 | abiertos | Qwen3-32B | ✗ |
| 7 | decision-machine-1 | 68.3 | 62.1 | 70.4 | cerrado | API | ✗ |
| 8 | decider-35b-a3b | 67.6 | 79.6 | 71.5 | abiertos | 35B-A3B FP8 | ✗ |
| 9 | open-alternative-jev | 67.0 | 64.0 | 63.2 | abiertos | Qwen3.5-4B | ✓ (inferior) |
| 10 | system-one-open | 66.6 | 69.5 | 56.7 | abiertos | Gemma 4 E2B LoRA | ✓ (inferior) |
| 11 | OpenJev (razorback16) | 66.4 | 79.2 | 64.8 | abiertos | DiffusionGemma 26B-A4B | ✗ |
| 12 | SimpleJev | 66.3 | 84.7 | 81.1 | abiertos | Qwen3.8-27B | ✗ |
| 13 | zerank-2 (adaptador) | 66.0 | 63.0 | 76.5 | abiertos | reranker | ✓ (inferior) |
| 14 | GPT-5.6 Luna | 65.9 | 95.3 | 89.8 | cerrado | API | ✗ |
| 15 | openjev-sglang | 65.3 | 83.4 | 77.4 | abiertos | Qwen3.6-35B-A3B | ✗ |
| 16 | Qwen3-Reranker-4B | 63.8 | 64.0 | 67.0 | abiertos | 4B | ✓ (inferior) |
| 17–18 | reflex-27b / LitJev | 63.3 / 62.7 | 85.8 / 82.4 | 86.2 / 83.5 | abiertos | 27B | ✗ |
| 19 | kev 0.6B | 62.5 | 51.9 | 51.1 | abiertos | 0.6B | ✓ (muy inferior) |
| 22 | jev-local (us/jev-local) | 61.8 | 70.8 | 68.7 | abiertos | Qwen3.5-9B | ≈ solo cuantizado, al límite |
| 23 | decider-2b | 61.7 | 61.2 | 46.6 | abiertos | Qwen3.5-2B | ✓ (inferior) |
| 24 | Bespoke Nimble 9B | 60.5 | 77.9 | 65.3 | abiertos | 9B LoRA | ≈ solo cuantizado, al límite |
| 33 | Laya | 54.4 | 45.8 | 62.5 | abiertos | ModernBERT 421M | ✓ CPU (muy inferior) |

*(Fuente: benchmarkheaven.com/jev-models, medido el 21/09/2026. Se omiten las filas 20–21 y 25–48; todas
son más grandes que la GPU o puntúan menos.)*

### Decisión

**Usaremos el que cabe, y es el mejor que podemos correr: el método SemIf (#2 de 48, a 1.3 puntos del
Jev oficial) sobre Qwen3.5-4B.** Todo lo que supera a SemIf o está cerca en calidad bruta (djev, Winnow-12B,
jqv, decider-35b, los 27B) necesita entre 13 y más de 30 GB de VRAM. El único con mejor *Intelligence* y
*Calibration* que sí cabe es **reflex 4B (#5)**. Al revisar su código vimos que su configuración `stable`
usa **el mismo Qwen3.5-4B congelado** (`adapter: null`) con otro formato de prompt. Por eso lo integramos
como perfil alternativo del mismo motor en lugar de tratarlo como otro modelo.

Aclaración de nombres: nuestro servidor se llama `jevlocal` y **no es** el proyecto `us/jev-local` (#22).

## 3. Qué construimos

### Motor (`jevlocal/src/jevlocal/engine.py`)
- **llama.cpp CUDA** sobre **GGUF Q8_0** (4.3 GB). El perfilado mostró que con prompts de ~150 tokens el
  límite es el cómputo de los GEMM, no la memoria. Los kernels int8 MMQ de llama.cpp llegan a **2,600 tok/s**
  y superan a cuBLAS fp16 (2,150 tok/s) y a HF/transformers bf16 (1,400–2,500 tok/s). Q8_0 resultó igual
  o más rápido que Q4_K_M y conserva la calidad de bf16.
- **Árbol de secuencias:** el system prompt queda residente en la GPU (secuencia 0). Cada `state` se
  ramifica desde ahí con `seq_cp`, que comparte las celdas KV y hace copy-on-write del estado recurrente
  de Gated DeltaNet. Cada pregunta se ramifica desde su `state`. Todas las ramas de una ola comparten un
  solo `llama_decode`.
- **Padding de hojas después de la posición de respuesta:** evita la fragmentación de ubatch que causa
  `split_equal` en modelos recurrentes (+15–20 % en peticiones con varias ramas). Es exacto porque los
  tokens posteriores no alteran los logits de la respuesta.
- **Más de 26 opciones (hasta 255, como Jev):** se usan códigos numéricos de ancho fijo leídos dígito
  por dígito, con P(código) = ∏ P(dígito | prefijo). Probado con 130 opciones.
- **Sin torch ni transformers:** se tokeniza con el vocabulario del GGUF.
- **Protección de GPU compartida:** consulta `nvidia-smi`, reserva 2.5 GB si la GPU maneja pantalla y
  limita el ubatch a 512 para que el compositor no se quede sin turnos (ver §6).

### API (`server.py`): el estándar de facto, idéntico a TypeSafe
- `POST /v1/systemone`, `GET /v1/models`, `GET /health`; `Authorization: Bearer` opcional.
- Mismos esquemas de request y response que docs.typesafe.ai/api. `confidence = (K·p_max−1)/(K−1)`,
  la fórmula publicada por TypeSafe.
- Errores 401, 422 y 529 con cuerpo `{"detail": ...}`.
- Batching entre peticiones concurrentes: un hilo es dueño de la GPU y fusiona la cola en cada pasada.
- **Verificado con el SDK oficial `typesafe-sdk` 0.7.1 sin modificarlo:** `TYPESAFE_BASE_URL=http://127.0.0.1:8765`,
  `system_one()` con Choice, Score y Noul, `models.list()` y el error 401.

### Herramientas de comparación (sirven igual contra el Jev real)
- `bench/eval_labeled.py`: exactitud, exactitud balanceada, NLL, Brier y ECE, más el ajuste de temperatura.
  Acepta `--url` para evaluar `https://api.typesafe.ai` con las mismas filas.
- `bench/load.py`: carga HTTP concurrente con percentiles, contra cualquier endpoint.
- `bench/latency.py`: latencia en proceso con formas realistas de petición.

## 4. Resultados medidos en esta máquina

### Calidad (554 decisiones etiquetadas: authored144 + WANLI256 + Every154, las mismas filas que SemIf)

Paridad del motor Q8_0 contra las predicciones bf16 publicadas por SemIf, con el mismo prompt:

| Dataset | Q8_0 (nosotros) | bf16 (SemIf) | Acuerdo de argmax | Variación total |
|---|--:|--:|--:|--:|
| authored144 | 0.8125 | 0.806 | 97.9 % | 0.014 |
| WANLI256 | 0.641 | 0.637 | 97.7 % | 0.019 |
| Every154 | 0.942 | 0.942 | 100 % | 0.002 |

Perfiles evaluados (mismo modelo; "2 órdenes" promedia el orden de opciones invertido):

| Perfil | Órdenes | Exactitud | Exac. balanceada | ECE crudo | T óptima | ECE calibrado | ms/decisión |
|---|--:|--:|--:|--:|--:|--:|--:|
| **semif (default)** | 1 | **0.785** | 0.754 | 0.090 | 1.8 | 0.024 | ~57 |
| semif | 2 | 0.782 | 0.771 | 0.066 | 1.35 | **0.015** | ~105 |
| reflex | 1 | 0.767 | **0.807** | 0.042 | 1.35 | 0.044 | **~52** |
| reflex | 2 | 0.783 | 0.806 | **0.032** | 1.05 | 0.034 | ~95 |

Lectura de la tabla:
- **semif** (el default) da la mejor exactitud simple y, con T = 1.8, la mejor calibración a costo de
  una rama. `option_style=key` (mostrar "opción: descripción") le sumó 3 puntos en WANLI respecto al
  prompt original de SemIf.
- **reflex** es menos sesgado entre clases (+5 puntos de exactitud balanceada) y sale mejor calibrado sin
  ajuste. Conviene si las clases están desbalanceadas: `--profile reflex --temperature 1.35`.
- Promediar dos órdenes duplica el costo y mejora poco. Queda como opción (`--debias all`), no como default.
- El debias en Noul no mejoró la exactitud en Every (0.942 → 0.929) y costó 64 % más. Está desactivado.

### Velocidad (RTX 3060, Q8_0, en proceso)

| Carga | Mediana |
|---|--:|
| 1 Choice (≈95 tokens) | **43–46 ms** |
| 1 Choice por HTTP, punta a punta | **~42 ms** |
| Ejemplo de la documentación de Jev (Noul + Choice + Score) | ~117 ms |
| 21 preguntas sobre un estado de ~1.4k tokens | ~1.38 s |
| Ráfaga de 64 peticiones | ~22 decisiones/s (≈19/s con ubatch 512 en modo pantalla) |

Como referencia: HF/transformers bf16 (SemIf original) daba ~101 ms por decisión en esta misma GPU. El
estudio independiente que cita el PDF midió ~239 ms de mediana para Jev por red.

**Límite de hardware:** el motor alcanza la velocidad bruta de `llama-bench` (~2,600 tok/s de prefill), así
que ya no queda margen en los kernels. Lo único que acelera más es usar menos tokens: estados compartidos,
preguntas cortas y menos opciones.

Una muestra real contra el ejemplo de la documentación de TypeSafe: Jev responde billing 0.88 /
technical 0.12, confidence 0.81. Nuestro motor dio billing 0.875 / technical 0.123, confidence 0.81.

## 5. Uso

### En esta máquina
```bash
cd /mnt/data_4tb/JEV-CODING
.venv-jl/bin/jevlocal selftest
.venv-jl/bin/jevlocal serve --port 8765        # http://127.0.0.1:8765/v1/systemone
```

### Paquete portátil para otra máquina Linux
`dist/jevlocal-1.0.0-linux-x86_64-cuda12.tar.zst` (~5.8 GB) incluye Python 3.12 standalone,
llama.cpp CUDA (kernels para sm_75 a sm_120), el runtime CUDA 12.8 y cuBLAS, y el modelo.
Todo va dentro, con RPATH `$ORIGIN`. En destino solo hace falta el **driver NVIDIA ≥ 570**.
```bash
tar --zstd -xf jevlocal-1.0.0-linux-x86_64-cuda12.tar.zst
cd jevlocal-1.0.0-linux-x86_64-cuda12
bin/jevlocal selftest
bin/jevlocal serve --host 0.0.0.0 --api-key SECRETO
```
Probado extrayéndolo en otra ruta y corriéndolo con un entorno vacío (`env -i`): funcionó y verifica
checksums. El resultado de la prueba de glibc en otra distribución está en §7.

### Comparar contra Jev cuando tengas acceso
```bash
export TYPESAFE_API_KEY=...
bin/jevlocal eval --url https://api.typesafe.ai --api-key $TYPESAFE_API_KEY --data filas.jsonl --out jev.json
bin/jevlocal eval --url http://127.0.0.1:8765 --data filas.jsonl --out local.json
bin/jevlocal load --url https://api.typesafe.ai --api-key $TYPESAFE_API_KEY --clients 1 4 16
```
Recomendación del PDF que sigue vigente: probar con datos propios etiquetados, descomponer los juicios
complejos en preguntas simples y recalibrar `--temperature` con esos datos.

## 6. Incidente y medidas de seguridad

Durante las evaluaciones largas la computadora se congeló y hubo que reiniciar. Revisamos el registro del
kernel (`journalctl -k -b -1`) y descartamos falta de RAM: el sistema tenía 240 GB libres y no hubo
eventos de OOM. Lo que aparece son errores **NVRM Xid 56** del motor de pantalla, desde las 15:33. La
RTX 3060 dibuja el escritorio (gnome-shell) y al mismo tiempo recibía ráfagas largas de kernels
(ubatch 2048, 32 ramas, ~8.5 GB de VRAM, evaluaciones encadenadas); el compositor se quedó sin recursos.

Medidas incorporadas en el código:
1. **Defaults conservadores:** `ctx=16384`, `seqs=16` (~6 GB de VRAM en lugar de ~8.5 GB).
2. **Protección de VRAM** (`_fit_gpu`): antes de cargar consulta `nvidia-smi` y reduce ramas y contexto
   para dejar **2.5 GB libres si hay pantalla** (0.75 GB si no la hay). Si no cabe, se niega a arrancar.
3. **Kernels cortos con pantalla activa:** ubatch ≤ 512, para que el compositor reciba turnos (cuesta
   ~10 % de throughput en ráfagas).
4. Procedimiento: no encadenar benchmarks largos en la GPU del escritorio, no compilar mientras la GPU
   trabaja, y compilar con tope de memoria (`systemd-run -p MemoryMax=64G`, `nice`).

Para servir en producción conviene una GPU sin pantalla (servidor sin gráficos), o dejar el escritorio
en la iGPU si existe.

## 7. Estado final y límites conocidos
- Validado: 15 pruebas automáticas (validación, formas de respuesta, paridad batch contra individual,
  re-enraizado con solo 4 secuencias, códigos de 3 dígitos) y el SDK oficial de TypeSafe.
- Las probabilidades se calibran con una sola temperatura, no con entrenamiento tipo RLCD. En WANLI
  (NLI difícil) el modelo es sobreconfiado sin T.
- Contexto por defecto de 16k tokens (configurable; Jev acepta 64k). Primera petición tras arrancar:
  el warm-up ya precalienta los CUDA graphs.
- Paquete: la primera versión exigía glibc ≥ 2.38 (el sysroot de conda era 2.39) y falló en Rocky 8.
  Se recompiló contra el **sysroot 2.28** para cubrir RHEL/Rocky 8, Ubuntu 20.04+ y Debian 11+
  Verificado: el máximo símbolo requerido ahora es GLIBC_2.27, y `bin/jevlocal selftest` pasó dentro de
  un contenedor **Rocky Linux 8.9 (glibc 2.28)** con la GPU (113.6 ms para 3 preguntas), sin errores Xid.

## Fuentes
- PDF local: *Jev by TypeSafe AI: Verification, Analysis, and Competitive Landscape*
- TypeSafe API: https://docs.typesafe.ai/api · Confidence: https://docs.typesafe.ai/confidence
- JevBench v1.3.0: https://benchmarkheaven.com/jev-models
- SemIf: https://github.com/TheoLeeCJ/SemIf · reflex: https://github.com/kshetrajna12/reflex
- djev: https://github.com/mmastrac/djev · awesome-jev-family: https://github.com/notsointresting/awesome-jev-family

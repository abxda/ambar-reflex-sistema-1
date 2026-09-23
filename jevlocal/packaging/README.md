# jevlocal 1.0.0: decisiones System One locales con API compatible con Jev

Servidor autocontenido que implementa la API de TypeSafe Jev (`POST /v1/systemone`, `GET /v1/models`)
sobre **Qwen3.5-4B (GGUF Q8_0)** usando el método de lectura directa de logits de SemIf, ejecutado con
llama.cpp CUDA. No genera texto: lee en una pasada la probabilidad de cada opción declarada.

## Requisitos de la máquina destino
- Linux x86_64, glibc ≥ 2.28 (RHEL/Rocky 8+, Ubuntu 20.04+, Debian 11+)
- GPU NVIDIA con ≥ 8 GB de VRAM libre (probado en RTX 3060 12 GB; kernels para sm_75 a sm_120:
  Turing, Ampere, Ada, Hopper y Blackwell)
- Driver NVIDIA ≥ 570 (el runtime CUDA 12.8 y cuBLAS van incluidos en el paquete)
- No necesita Python, CUDA toolkit, conda ni internet: todo va dentro

## Instalación
```bash
tar --zstd -xf jevlocal-1.0.0-linux-x86_64-cuda12.tar.zst
cd jevlocal-1.0.0-linux-x86_64-cuda12
bin/jevlocal selftest        # carga el modelo, responde el ejemplo de la documentación y mide el tiempo
```

## Servidor
```bash
bin/jevlocal serve                                   # http://127.0.0.1:8765
bin/jevlocal serve --host 0.0.0.0 --api-key SECRETO  # acceso en red, con Bearer obligatorio
```
Como servicio: ver `jevlocal.service` (unidad systemd de usuario).

```bash
curl -s localhost:8765/v1/systemone -H 'Content-Type: application/json' -d '{
  "state": "Help! My payouts have been failing for 3 days.",
  "model": "jev-latest",
  "questions": {
    "department": {"type": "choice", "instructions": "Which team should handle this?",
                   "criteria": {"billing": "Payments, invoicing, refunds",
                                "technical": "Bugs, outages, integrations",
                                "sales": "Pricing, upgrades, new accounts"}},
    "is_urgent":  {"type": "noul",  "instructions": "Does this convey urgency?"},
    "frustration":{"type": "score", "instructions": "How frustrated is the customer?",
                   "criteria": ["Calm", "Frustrated", "Very angry"]}}}'
```

### SDK oficial de TypeSafe (sin cambios)
```bash
export TYPESAFE_BASE_URL=http://127.0.0.1:8765
export TYPESAFE_API_KEY=SECRETO        # cualquier valor si el servidor no exige clave
```
`typesafe-sdk` (Python) 0.7.1 fue verificado: `client.system_one(...)` con Choice, Score y Noul,
`client.models.list()` y el error 401. Cualquier cliente que hable la API HTTP de Jev funciona igual.

## Compatibilidad con la API de Jev
| Aspecto | Jev (TypeSafe) | jevlocal |
|---|---|---|
| Endpoint | `POST /v1/systemone`, `GET /v1/models` | igual (+ `GET /health`) |
| Request | `state` (string/objeto/arreglo), `model`, `questions{}` | igual |
| Choice | 2–255 opciones, `choice`, `probabilities`, `confidence` | igual (más de 26 opciones: códigos numéricos leídos dígito por dígito) |
| Score | 2–10 niveles, `score`, `legend`, `probabilities`, `confidence` | igual |
| Noul | `noul` ∈ [0,1], `criteria.true/false` opcionales | igual |
| confidence | `(K·p_max − 1)/(K − 1)` (documentado para Choice) | misma fórmula para Choice y Score |
| Errores | 401, 422, 429, 529 | 401, 422, 529 (cola llena) |
| `usage` | `input_tokens`, `output_tokens` | tokens del prompt (el estado compartido se cuenta una vez); output = número de preguntas |

## Configuración (flag o variable `JEVLOCAL_<NOMBRE>`)
| Opción | Default | Nota |
|---|---|---|
| `--temperature` | 1.8 | minimiza el NLL en 554 decisiones etiquetadas (ECE de 0.081 a 0.021) |
| `--option-style` | key | "opción: descripción"; `desc` = solo descripción (paridad con SemIf) |
| `--debias` | none | `noul`/`all` promedian el orden invertido de opciones (+1 rama por pregunta) |
| `--ctx` | 16384 | tokens de contexto compartidos por todas las ramas |
| `--seqs` | 16 | ramas paralelas; se reducen solas para dejar margen de VRAM |
| `--profile` | semif | `reflex` = prompt markdown (mejor exactitud balanceada; usar `--temperature 1.35`) |
| `--max-jobs` | 16 | peticiones concurrentes fusionadas en un batch de GPU |

## Seguridad en GPUs con pantalla
Si la GPU también dibuja el escritorio, jevlocal lo detecta con `nvidia-smi`: deja 2.5 GB de VRAM libres
y limita el ubatch a 512 para que el compositor no se congele. Para producción conviene una GPU sin pantalla.

## Comparar contra el Jev real
Las mismas herramientas funcionan contra cualquier endpoint compatible:
```bash
bin/jevlocal eval --url https://api.typesafe.ai --api-key $TYPESAFE_API_KEY --data mis_filas.jsonl
bin/jevlocal eval --url http://127.0.0.1:8765 --data mis_filas.jsonl
bin/jevlocal load --url https://api.typesafe.ai --api-key $TYPESAFE_API_KEY --clients 1 4 16
```
Formato de filas etiquetadas (JSONL): `{"id","state","question","options":[{"id","description"}],"label":<índice>}`.
Con `--as-noul`, las filas binarias sí/no se envían como Noul.

## Rendimiento medido (RTX 3060 12 GB, Q8_0)
| Carga | Latencia |
|---|---|
| 1 Choice (≈95 tokens), en proceso | ~43 ms |
| 1 Choice por HTTP, punta a punta | ~42–45 ms |
| Ejemplo de la documentación (3 preguntas) | ~117 ms |
| 21 preguntas sobre un estado de ≈1.4k tokens | ~1.38 s |
| Throughput sostenido | ~2,600 tokens/s de prompt (≈23 decisiones cortas/s) |

## Calidad (554 decisiones etiquetadas; mismas filas que SemIf)
| Dataset | Exactitud | Referencia SemIf bf16 |
|---|---|---|
| authored144 | 0.8125 | 0.806 |
| WANLI256 | 0.672 | 0.637 |
| Every154 | 0.942 | 0.942 |

Límites: estas probabilidades no provienen de un entrenamiento tipo RLCD. Se calibran con una sola
temperatura, así que conviene recalibrar `--temperature` con datos propios (`bin/jevlocal eval` reporta
la temperatura óptima). Máximo 16k tokens de contexto por defecto (Jev acepta 64k).

# Hallazgos — Contabilidad de tokens (R6)

- **Fecha:** 2026-09-01
- **Herramienta:** Claude Code `2.1.257`
- **Riesgo evaluado:** [R6](./RESEARCH.md#10-riesgos-e-hipótesis-a-validar) — *¿se pueden contabilizar los tokens de forma programática?*
- **Veredicto:** ✅ **R6 superado.** El banco de medición es viable.

---

## 1. Método

```bash
claude -p "responde solo: ok" --output-format json > r6.json
python3 -m json.tool r6.json
```

Prompt deliberadamente trivial, para aislar el **coste base** de una invocación de cualquier trabajo real.

---

## 2. Campos disponibles

Claude Code expone en `--output-format json` todo lo que el banco necesita, y más:

| Campo | Uso en el banco |
|---|---|
| `usage.input_tokens` · `usage.output_tokens` | Tokens de la tarea |
| `usage.cache_creation_input_tokens` | Contexto escrito a caché |
| `usage.cache_read_input_tokens` | Contexto releído de caché |
| **`total_cost_usd`** | **Métrica primaria** — ver §4 |
| `num_turns` | Fuga #3 (ciclos de reintento) |
| `usage.iterations[]` | Desglose por turno |
| `modelUsage` | Modelo, ventana de contexto, base de precio |
| `is_error` · `subtype` · `stop_reason` | Éxito o fallo de la ejecución |
| `duration_ms` · `ttft_ms` | Latencia |
| `session_id` · `uuid` | Trazabilidad y reproducibilidad |
| `subagent_stats` | Contabiliza el trabajo delegado a subagentes |
| `permission_denials` | Ejecuciones bloqueadas que invalidarían la medición |

También hay `--output-format stream-json` para observación en tiempo real, útil si más adelante hace falta instrumentación por turno.

---

## 3. El resultado que importa

Salida real del prompt trivial:

```json
"usage": {
    "input_tokens": 2,
    "output_tokens": 4,
    "cache_creation_input_tokens": 8695,
    "cache_read_input_tokens": 10126
},
"total_cost_usd": 0.092123,
"num_turns": 1
```

Desglosado:

| Concepto | Tokens |
|---|---|
| Trabajo real (entrada + salida) | **6** |
| Contexto (creación + lectura de caché) | **18.821** |
| **Proporción de overhead** | **99,97 %** |

> **Responder `ok` costó 9,2 centavos de dólar y movió 18.821 tokens de contexto.**

### Por qué esto valida la tesis del proyecto

Es una confirmación empírica directa de [RESEARCH.md §3](./RESEARCH.md#3-dónde-se-gastan-realmente-los-tokens): **el coste vive en el contexto que se arrastra, no en el trabajo que se pide.**

Y refuerza P2 (presupuesto duro) más de lo que anticipábamos. Cada token que ArquiGraph inyecte no se paga una vez: entra en el contexto y se vuelve a pagar como `cache_read` **en todos los turnos posteriores de esa sesión**. Un exceso de 500 tokens en el turno 3 sigue costando en el turno 40.

Esto es exactamente el mecanismo por el que el `AGENTS.md` inflado sube el coste un 20 % (§2.2), medido ahora en nuestra propia instalación.

---

## 4. Decisión: `total_cost_usd` es la métrica primaria

Con caché de por medio, "tokens totales" es una métrica ambigua: un token de `cache_read` no cuesta lo mismo que uno de entrada normal, ni que uno de `cache_creation`.

`total_cost_usd` ya pondera cada categoría con su precio real. Es una sola cifra, comparable y auditable.

**Consecuencia para el banco:**

- **Métrica primaria:** `total_cost_usd` (A vs B)
- **Métricas de apoyo:** desglose de `usage` (para explicar *dónde* se fue el coste) y `num_turns`
- El criterio de kill de R1 —"sube el coste más de un 10 %"— se evalúa sobre `total_cost_usd`

---

## 5. Riesgo derivado: presupuesto del banco

El coste base observado obliga a estimar antes de lanzar.

Aritmética del banco tal como está diseñado:

```
20–30 tareas × 3 repeticiones × 2 modos (A/B) = 120–180 ejecuciones
```

Una tarea real —con lectura de archivos, ejecución de tests y varios turnos— cuesta bastante más que un `ok`. **El banco completo no es gratis y hay que presupuestarlo antes de correrlo.**

### Mitigaciones

1. **Fijar el modelo, y que sea Sonnet.** La ejecución de prueba usó `claude-opus-5` con ventana de 1M. Para el banco conviene Sonnet por tres razones:
   - Coste sustancialmente menor
   - Es el modelo por defecto de la mayoría de usuarios → resultados más representativos
   - El estudio de ETH Zurich que motiva el proyecto usó Sonnet 4.5 → comparabilidad

2. **Fijar el modelo es además un requisito de validez.** Comparar el modo A con un modelo y el B con otro invalida la medición. El modelo se declara en la configuración del banco y se registra en cada resultado.

3. **Piloto antes del banco completo.** Correr 3 tareas × 3 repeticiones, medir el coste real por tarea, extrapolar, y decidir el tamaño definitivo del corpus con datos en la mano.

---

## 6. Estado de las preguntas abiertas

| Pregunta | Estado |
|---|---|
| #1 — R6, contabilidad de tokens | ✅ **Resuelta.** Viable vía `-p --output-format json` |
| #2 — Captura de trayectorias (hooks) | ⏳ Pendiente. `stream-json` es un candidato adicional a los hooks |

---

## 7. Siguientes acciones

1. Fijar el modelo del banco en configuración y registrarlo en cada resultado.
2. Implementar `bench/ledger/` parseando estos campos.
3. **Piloto de coste** (3 tareas × 3 repeticiones) antes de dimensionar el corpus.
4. Continuar con el Paso 2 de [PHASE-0.md](./PHASE-0.md): hooks del agente.

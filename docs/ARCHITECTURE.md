# ArquiGraph — Arquitectura

> **Estado:** diseño inicial · **Fecha:** 2026-09-01
> **Base de evidencia:** [`docs/RESEARCH.md`](./RESEARCH.md) — cada decisión de este documento cita el principio (`P1`–`P7`) o la sección (`§n`) que la justifica.
> **Decisiones formales:** [`docs/adr/`](./adr/)

---

## 0. Qué es ArquiGraph en una frase

> Un arquitecto de software persistente para agentes de programación: un **grafo determinista** del código, una **memoria procedural verificada** de cómo se trabaja en este repositorio, y un **guardián de invariantes** que impide que el agente rompa las decisiones ya tomadas.

Las tres piezas son inseparables. El grafo sin memoria es un mapa que nadie recuerda haber leído. La memoria sin grafo se pudre en silencio. Y sin guardián, nada sujeta al agente a lo acordado (§4.3).

---

## 1. Restricciones de partida

| # | Restricción | Origen |
|---|---|---|
| C1 | **Sistema propio.** Cero código de Graphify o Engram. Licencias limpias, sin acoplamiento a repos de terceros. | Decisión del proyecto |
| C2 | **Grafo 100% determinista.** Cero LLM y cero embeddings en la capa semántica. | §5.1, P6 |
| C3 | **Recuperación bajo demanda.** Nunca inyección en el prompt de sistema. | §2, P1 |
| C4 | **Presupuesto de tokens duro y auditable** en toda salida hacia el agente. | §2, §3, P2 |
| C5 | **Superficie de integración: MCP server + hooks.** | Decisión del proyecto |
| C6 | **Se mide antes de crecer.** El banco de medición es Fase 0, no un extra. | §5.2-C, P7, R1 |
| C7 | **Un solo lenguaje en Fase 0: Python.** TypeScript/JavaScript entra en Fase 1.5, después de validar R1. | Proteger la medición de R1 |
| C8 | **Proyecto público de portafolio.** Licencia Apache 2.0; los resultados del banco deben ser **reproducibles por terceros**. | ADR-007 |
| C9 | **ArquiGraph no requiere Docker ni servicios para usarse.** Docker es solo para reproducir el banco. | Adopción |

---

## 2. Vista de conjunto

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENTE (Claude Code · Codex · Cursor)                          │
└───────────────┬──────────────────────────────┬──────────────────┘
                │ MCP (bajo demanda, P1)       │ hooks (git + sesión)
                ▼                              ▼
┌─────────────────────────────┐   ┌──────────────────────────────┐
│  SUPERFICIE                 │   │  OBSERVADORES                │
│  arqui_recall               │   │  post-commit  → reparseo     │
│  arqui_trace                │   │  pre-commit   → guardián     │
│  arqui_check                │   │  fin de tarea → trayectoria  │
│  arqui_remember             │   │  inicio       → frescura      │
└──────────┬──────────────────┘   └──────────┬───────────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  NÚCLEO                                                          │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐│
│  │ RECUPERADOR│  │  GUARDIÁN  │  │ DESTILADOR │  │ CONTABLE   ││
│  │ P1 P2 P3 P4│  │  P6 (0 tok)│  │  P5        │  │ P7         ││
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘│
│        └───────────────┴───────────────┴───────────────┘        │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐  │
│  │  CAPAS DE CONOCIMIENTO                                    │  │
│  │  ① Semántica  — Grafo AST determinista   (qué existe)     │  │
│  │  ② Episódica  — Memory                   (qué se decidió) │  │
│  │  ③ Procedural — Procedure (verificado)   (cómo se hace)   │  │
│  │  ④ Normativa  — Invariant                (qué no romper)  │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                             ▼                                    │
│              SQLite  ·  .arquigraph/graph.db                     │
└─────────────────────────────────────────────────────────────────┘
                             ▲
                             │ tree-sitter (determinista, 0 tokens)
                    ┌────────┴────────┐
                    │  CÓDIGO FUENTE  │
                    └─────────────────┘
```

**La propiedad que lo sostiene todo:** las capas ②③④ están **ancladas a nodos de la capa ①**. Cuando el código cambia, el ancla cambia de hash y el conocimiento colgado de él se marca sospechoso **solo** (P3). Eso convierte la obsolescencia de un problema operativo (§5.2-B) en una propiedad del sistema.

---

### 2.1 Cómo se ahorra realmente: buscar frente a navegar

Sin mapa, un agente que recibe *"arregla el bug de refresco de token"* hace esto:

```
grep "token"  →  47 coincidencias
  leer auth/service.py      (completo, ~4.000 tokens)   no era
  leer auth/middleware.py   (completo, ~3.000 tokens)   no era
  leer api/session.py       (completo, ~5.000 tokens)   tampoco
  leer core/security.py     (completo, ~6.000 tokens)   aquí estaba
```

**18.000 tokens para encontrar un archivo.** Y aquí está lo que la medición de R6 hizo evidente: esos cuatro archivos **no se pagan una sola vez**. Quedan en el contexto y se recobran como `cache_read` en **cada turno posterior de la sesión**. Un archivo leído por error en el turno 3 se sigue pagando en el turno 40.

Con mapa, la misma pregunta se resuelve navegando:

```
arqui_trace --symbol refresh_token
  → core.security.TokenService.refresh      core/security.py:88
    ← llamado por auth.service.renew        auth/service.py:142
    ← llamado por api.session.refresh       api/session.py:31
```

**~200 tokens**, con rutas citables y verificables. El agente abre un archivo, no cuatro.

#### La aritmética honesta

| | Sin grafo | Con grafo |
|---|---|---|
| Coste de construir el mapa | — | **0 tokens de LLM** (AST determinista, local) |
| Coste de localizar el archivo | ~18.000 tokens | ~200 tokens |
| Reintentos por leer lo equivocado | frecuentes | poco frecuentes |
| Arrastre en turnos posteriores | los 18.000, cada turno | los 200, cada turno |

**Esto no elimina el gasto de tokens.** El agente sigue teniendo que leer el archivo correcto, razonar y escribir el parche. Lo que cambia es la **relación señal/ruido**: se deja de pagar por lo que no servía.

#### El matiz que hay que vigilar

> El grafo por sí solo **no garantiza** el ahorro.

Si `arqui_trace` devuelve 30 nodos cuando bastaban 3, reintroducimos exactamente el problema que veníamos a resolver, solo que con mejor formato. Por eso **P2 (presupuesto de tokens) se aplica también a `trace`**, no solo a `recall` — cualquier herramienta que devuelva texto al agente vive bajo techo.

#### Dónde nos parecemos a Graphify y dónde no

| | Graphify | ArquiGraph |
|---|---|---|
| Mapa AST determinista, navegar en vez de grepear | ✅ | ✅ |
| Coste de extracción | 0 tokens | 0 tokens |
| **El mapa recuerda decisiones y procedimientos** | ❌ | ✅ capas ②③ |
| **El mapa vigila que no rompas lo acordado** | ❌ | ✅ capa ④ |

La navegación es el **sustrato**, no el producto. Graphify demostró que funciona; ArquiGraph parte de ahí y añade que ese mapa además **recuerde** y **vigile**.

---

## 3. Capa ① — Grafo semántico

### 3.1 Regla dura

> Todo lo que entra al grafo se extrae del AST de forma determinista. Si no se puede extraer, se marca `AMBIGUOUS` y **no se afirma**.

Cero LLM, cero embeddings, cero tokens. Un grafo que alucina es peor que no tener grafo, porque el agente lo cita con confianza.

### 3.2 Nodos

| Tipo | Ejemplos |
|---|---|
| `File` · `Module` · `Package` | unidades de organización |
| `Class` · `Interface` · `TypeAlias` | tipos |
| `Function` · `Method` | unidades de comportamiento |

```python
Node {
    node_id:        str   # identidad estable — ver §3.4
    kind:           str
    qualified_name: str   # "app.auth.service.TokenService.refresh"
    path:           str   # ruta relativa al repo
    signature_hash: str   # hash de la firma normalizada
    body_hash:      str   # hash del cuerpo normalizado
    span:           tuple # (línea_inicio, línea_fin) — VOLÁTIL, solo navegación
    layer:          str?  # etiqueta arquitectónica, opcional
}
```

### 3.3 Aristas

| Arista | Significado |
|---|---|
| `DEFINES` | contención (módulo define clase, clase define método) |
| `CALLS` | invocación |
| `IMPORTS` | dependencia de módulo |
| `INHERITS` / `IMPLEMENTS` | herencia / contrato |
| `REFERENCES` | uso de símbolo sin invocación |

```python
Edge {
    src, dst:    node_id
    kind:        str
    evidence:    (path, line)   # citable y auditable — siempre presente
    confidence:  float          # 1.0 = extraído; <1.0 = resuelto heurísticamente
    resolution:  EXTRACTED | INFERRED | AMBIGUOUS
}
```

Toda arista `INFERRED` (imports dinámicos, duck typing, reflexión) se marca como tal y el recuperador la degrada en el ranking. Nunca se presenta como hecho.

Las reglas concretas por caso —qué es `EXTRACTED`, qué es `INFERRED` y con qué `confidence`, y qué queda en `AMBIGUOUS`— están en [ADR-008](./adr/ADR-008-resolucion-de-aristas.md). La regla que lo gobierna: **`confidence` mide certeza de resolución sintáctica, nunca verosimilitud estadística.**

### 3.4 Identidad de nodo — la decisión más delicada

El `node_id` **no puede** derivarse de números de línea ni de offsets de bytes: cualquier edición trivial invalidaría todas las memorias del archivo y el sistema se volvería inútil (riesgo R2).

```
node_id = blake2b(path + "::" + qualified_name + "::" + kind)[:16]
```

Propiedades que esto nos da:

| Evento en el código | ¿Cambia `node_id`? | ¿Correcto? |
|---|---|---|
| Se añaden líneas encima | No | ✅ la memoria sobrevive |
| Se reformatea | No | ✅ |
| Cambia el cuerpo | No (cambia `body_hash`) | ✅ señal suave |
| Cambia la firma | No (cambia `signature_hash`) | ✅ señal fuerte |
| Se renombra la función | Sí | ✅ es otra identidad |
| Se mueve de archivo | Sí | ⚠️ ver mitigación |

**Mitigación del renombrado/movimiento:** el reparseo compara nodos desaparecidos contra nodos nuevos por `body_hash`. Coincidencia exacta de cuerpo + distinto `node_id` = movimiento o renombrado → **se migran las anclas automáticamente** en vez de invalidarlas. Esto es lo que evita que un refactor rutinario borre la memoria del proyecto.

### 3.5 Los dos disparadores de invalidación

| Hash | Qué cubre | Efecto al cambiar |
|---|---|---|
| `signature_hash` | nombre, parámetros, tipos, retorno | **Fuerte** — el contrato cambió: memorias ancladas → `suspect` |
| `body_hash` | cuerpo normalizado (sin comentarios ni espacios) | **Suave** — la implementación cambió: procedimientos anclados → `suspect`; memorias de tipo `decision` sobreviven |

La distinción importa: una decisión arquitectónica ("este servicio no debe llamar a la BD directamente") sigue siendo válida aunque el cuerpo cambie. Un procedimiento ("para tocar esto, edita estas 4 líneas") no.

### 3.6 Reparseo incremental

Solo se reparsean los archivos que el diff toca. Un `post-commit` sobre un cambio de 3 archivos no debe costar más que unos milisegundos. El grafo completo se reconstruye desde cero solo con `arqui build --full`.

---

## 4. Capa ② — Memoria episódica

```python
Memory {
    id:               str
    kind:             decision | constraint | gotcha | context
    statement:        str          # UNA afirmación, ≤ 280 caracteres
    rationale:        str?         # el "por qué" — NO se recupera por defecto
    anchors:          [node_id]    # P3 — obligatorio, mínimo uno
    authority:        human | agent_verified | inferred
    evidence:         [commit_sha | pr_url | test_run_id]
    supersedes:       [memory_id]
    status:           active | suspect | retired
    created_at, last_confirmed_at
}
```

**Decisiones de diseño y su porqué:**

- **`statement` acotado a 280 caracteres.** Una memoria que no cabe en un tuit no es una memoria, es un documento — y los documentos largos son exactamente lo que degrada al agente (§2.3). El límite es una defensa estructural contra el `AGENTS.md` gordo.
- **`rationale` no se recupera por defecto.** El agente recibe la regla; pide el porqué solo si lo necesita. Ahorro directo de presupuesto (P2).
- **`anchors` obligatorio.** Una memoria sin ancla no puede caducar sola, y una memoria que no caduca es deuda (§5.2-B). Si no se puede anclar, no se guarda.
- **`supersedes` explícito.** Resuelve el conflicto de autoridad de §5.2-A por construcción, no por heurística: una memoria superseded nunca se recupera.

---

## 5. Capa ③ — Memoria procedural

Es el diferenciador (§7) y la única capa con evidencia causal de ahorro de tokens (§6).

```python
Procedure {
    id:                str
    intent:            str          # "añadir un endpoint REST autenticado"
    trigger:           [str]        # señales de que aplica
    steps:             [Step]       # {orden, acción, target_node_id, nota}
    touched_nodes:     [node_id]
    verification:      Verification # OBLIGATORIO — ver abajo
    uses, successes:   int
    discovery_cost:    int          # tokens que costó descubrirlo la primera vez
    status:            active | suspect | retired
}

Verification {
    tests_passed:  [str]    # identificadores de tests en verde
    commit_sha:    str      # el cambio se aplicó de verdad
    captured_at:   datetime
}
```

### 5.1 P5 es una regla de admisión, no una recomendación

> Una trayectoria que no terminó en **tests verdes o commit aplicado** se descarta. No se guarda "por si acaso".

Sin esta regla, la memoria procedural acumula los intentos fallidos del agente y los sirve como si fueran conocimiento — envenenando exactamente el recurso que debía ahorrar tokens. Es la diferencia entre memoria y basurero.

### 5.2 Ciclo de vida

```
trayectoria de la sesión
        │
        ▼
  ¿terminó verificada?  ── no ──▶ descartar
        │ sí
        ▼
  destilación (pasos → abstracción)
        │
        ▼
  ¿existe un Procedure con el mismo intent?
        │                       │
       sí                      no
        ▼                       ▼
  fusionar y                 crear
  subir confianza
        │
        ▼
  disponible para recall · se mide su reuso (P7)
```

La destilación es el único punto del sistema donde interviene un LLM, y ocurre **fuera de la ruta caliente** (asíncrono, tras la sesión). Nunca cuesta tokens al usuario mientras trabaja.

---

## 6. Capa ④ — Invariantes

```python
Invariant {
    id:          str
    description: str
    rule:        str          # DSL sobre el grafo
    severity:    error | warn
    adr_ref:     str?         # la ADR que lo justifica
}
```

### 6.1 DSL mínimo, declarativo

```
forbid  CALLS    from layer:domain     to layer:infrastructure
forbid  IMPORTS  from module:core      to module:web
require IMPLEMENTS Repository for Class matching "*Repository"
forbid  CALLS    to Function matching "*.raw_sql" from layer:domain
limit   fan_in(Function) <= 30
```

Deliberadamente pobre. Un DSL expresivo se convierte en un lenguaje de programación que nadie mantiene. Si una regla no se puede expresar aquí, probablemente no es un invariante: es una preferencia, y va como `Memory` de tipo `constraint`.

### 6.2 Evaluación

Recorrido de grafo sobre los nodos que el diff toca. **Coste: 0 tokens de LLM** (P6). Corre en `pre-commit` y en CI. Salida:

```
✗ ERROR  domain/order.py:42  CALLS → infrastructure.db.connect
         viola INV-003 (ADR-004: el dominio no accede a infraestructura)
         ruta: OrderService.confirm → _persist → db.connect
```

Ruta completa y citable. El agente puede arreglarlo sin adivinar.

---

## 7. El recuperador — el componente crítico

Aquí se gana o se pierde el proyecto (R1). Si este componente inyecta ruido, ArquiGraph reproduce la degradación medida del `AGENTS.md` (§2.2).

### 7.1 Contrato

```python
recall(
    task: str,
    changed_files: [str] = None,
    budget_tokens: int = 2000,
) -> Recall

Recall {
    items:          [RecallItem]   # cada uno con ancla, score y tipo
    tokens_used:    int
    omitted_count:  int            # cuántos candidatos NO cupieron
    graph_commit:   str            # frescura del grafo consultado
}
```

### 7.2 Pipeline

```
1. ANCLAJE      task + changed_files → nodos del grafo
                 · símbolos mencionados literalmente
                 · nodos definidos en los archivos tocados
                 · expansión de 1 salto por CALLS / IMPORTS
                 Determinista. Sin embeddings en Fase 1.

2. CANDIDATOS   memorias, procedimientos e invariantes anclados a esos nodos

3. FILTRO DURO  descartar status != active
                descartar superseded
                (una memoria sospechosa NO se sirve — nunca)

4. RANKING      score = w₁·relevancia_grafo      (distancia al ancla)
                      + w₂·autoridad             (human 1.0 · agent 0.7 · inferred 0.3)
                      + w₃·recencia              (decaimiento sobre last_confirmed_at)
                      + w₄·evidencia             (verificado > afirmado)
                P4 — la más confiable, no la más parecida (§5.2-A)

5. PRESUPUESTO  llenar por score descendente hasta budget_tokens
                P2 — techo duro, sin excepciones

6. TRAZA        cada ítem devuelto lleva su ancla y su score
                el Contable registra qué se sirvió y con qué coste
```

### 7.3 Por qué sin embeddings en Fase 1

Un vector store añade una dependencia pesada, indeterminismo y un modo de fallo (recuperar lo semánticamente cercano pero equivocado) que es justo el problema de §5.2-A. El anclaje por grafo es determinista y explicable. **Si la medición demuestra que el recall estructural no basta, se añade búsqueda semántica como señal adicional del ranking — nunca como criterio único.** Primero medimos, después complicamos.

---

## 8. Superficie MCP — cuatro herramientas, y no más

| Herramienta | Qué hace | Coste |
|---|---|---|
| `arqui_recall` | Recuperación con presupuesto. La principal. | acotado por `budget_tokens` |
| `arqui_trace` | Consulta estructural: *"¿quién llama a X?"*, *"¿qué rompo si cambio Y?"*. Rutas citables. **Es la herramienta de navegación de §2.1.** | `budget_tokens` (P2) **y** profundidad |
| `arqui_check` | Valida un diff o un plan contra invariantes. | 0 tokens de LLM |
| `arqui_remember` | Registra una decisión con anclas y autoridad. | escritura |

> **El manifiesto MCP cuenta contra el presupuesto.** Las descripciones de las herramientas viven en el prompt de sistema de cada sesión. Diez herramientas con descripciones generosas son un `AGENTS.md` entrando por la puerta de atrás (§2). Cuatro herramientas, descripciones de una línea, y esa cifra se defiende activamente en revisión.

---

## 9. Hooks

El flujo de trabajo del autor ya impone tres momentos de revisión —**antes de commit, antes de push, antes de merge**—, todos desde la terminal. El guardián se engancha exactamente a esos tres puntos: no inventamos un ritual nuevo, instrumentamos el que ya existe.

| Hook | Acción | Coste |
|---|---|---|
| `pre-commit` | **Compuerta 1.** `arqui_check` sobre el diff staged; bloquea en `severity: error`. Rápido y acotado. | 0 tokens |
| `pre-push` | **Compuerta 2.** Comprobación completa de invariantes + verificación de frescura del grafo. | 0 tokens |
| CI (Pull Request) | **Compuerta 3.** El mismo `arqui_check` en GitHub Actions. Es el registro público y la mejor demostración del portafolio. | 0 tokens |
| `post-commit` / `post-merge` | Reparseo incremental → recalcular hashes → migrar anclas movidas → marcar `suspect` | 0 tokens |
| **inicio de sesión** | **NO inyecta contexto.** Solo verifica frescura del grafo y avisa si está obsoleto. | ~0 |
| fin de tarea | Captura la trayectoria; si está verificada, la encola para destilación asíncrona | diferido |

Las tres compuertas ejecutan **el mismo código** del guardián. La diferencia es solo el alcance: `pre-commit` mira el diff staged, `pre-push` el rango completo de commits, CI el diff de la PR.

El hook de inicio de sesión es el que más tentación genera y el que más disciplina exige. **Inyectar ahí es exactamente el experimento que ETH Zurich ya corrió y que salió mal** (§2.2). Queda prohibido por diseño.

> **No es una preocupación teórica.** El hook `SessionStart` de Claude Code expone un campo `additionalContext` literalmente diseñado para inyectar texto en el prompt de cada sesión, y ya observamos un plugin de terceros usándolo en esta misma máquina ([FINDINGS-agent-hooks.md §4](./FINDINGS-agent-hooks.md)). ArquiGraph usará ese mismo hook con `additionalContext` **vacío**, señalando el grafo obsoleto por `exit_code`. Mismo canal, sin contenido.

---

## 10. Almacenamiento

**SQLite único en `.arquigraph/graph.db`.**

| Razón | Detalle |
|---|---|
| Adopción trivial | Cero servicios que levantar. `pip install` y funciona. |
| Suficiente | Las consultas del recuperador son de 1–2 saltos. No necesitamos un motor de grafos. |
| Travesías | Las CTE recursivas cubren `arqui_trace`. |
| Texto | FTS5 sobre `statement` e `intent`. |
| Desechable | Se ignora en git; reconstruible desde cero con `arqui build --full`. |

**Salida planificada:** si los invariantes acaban necesitando travesías profundas, [Kuzu](https://kuzudb.com) (embebido, Cypher, sin servidor) es la migración natural sin cambiar el modelo de datos. La decisión se toma con datos, no antes.

---

## 11. Estructura del proyecto

```
arquigraph/
├── core/
│   ├── parser/         # tree-sitter → nodos + aristas (determinista)
│   ├── identity/       # node_id, signature_hash, body_hash, normalización
│   └── graph/          # store SQLite, consultas, reparseo incremental
├── memory/
│   ├── episodic/       # Memory: CRUD, invalidación, supersede
│   ├── procedural/     # Procedure: captura, destilación, verificación
│   ├── ranking/        # P4
│   └── budget/         # P2
├── guardian/
│   ├── dsl/            # parser del DSL de invariantes
│   └── checker/        # evaluación sobre diff
├── bench/              # P7 + R1: harness A/B y contabilidad de tokens
├── mcp/                # servidor MCP (las 4 herramientas)
├── hooks/              # git + ciclo de sesión
└── cli/                # arqui build | check | recall | bench
```

---

## 12. Banco de medición — Fase 0

**Se construye primero.** Sin esto, ArquiGraph es un acto de fe y R1 queda sin falsear.

```
bench/
├── tasks/      # 20–30 issues cerrados del repo, con su commit de solución y sus tests
├── runner/     # ejecuta el agente en modo A (sin ArquiGraph) y B (con)
├── ledger/     # input_tokens, output_tokens, turnos, tool_calls, éxito
└── report/     # comparativa A/B
```

### 12.1 Métricas

| Métrica | Qué falsea |
|---|---|
| Tasa de éxito A vs B | ¿pasan los tests del commit de solución? |
| Tokens totales A vs B | **R1** |
| Turnos hasta la solución | fuga #3 (§3.1) |
| Tasa de invocación de `recall` | **R4** — ¿el agente usa la herramienta? |
| Precisión del recall | de lo inyectado, ¿cuánto apareció en la solución? |
| Tasa de invalidación por commit | **R2** — ¿el anclaje es demasiado frágil? |
| Coste de destilación vs ahorro por reuso | **R3** |

### 12.2 Criterio de kill

> Si el modo B **no mejora** la tasa de éxito y **sube el coste más de un 10%**, el recuperador está mal diseñado y se rehace antes de construir nada encima.

Esto no es pesimismo: es la única forma de no repetir el error que la literatura ya documentó.

---

## 13. Hoja de ruta por fases

| Fase | Contenido | Puerta de salida |
|---|---|---|
| **0a — Viabilidad** | **Verificar R6:** ¿se pueden contabilizar tokens de Claude Code en modo no interactivo? Prototipo del runner. | **Sin esto no hay proyecto medible** |
| **0b — Medir** | Banco con 20–30 tareas sobre repos OSS **Python**, en Docker. **Baseline A antes de construir nada.** | Baseline publicado y reproducible |
| **0c — Grafo** | Parser tree-sitter (**solo Python**), grafo SQLite, `node_id`/hashes, reparseo incremental | `arqui build` y `arqui trace` sobre el propio repo |
| **1 — Recuperar** | `Memory` + anclaje + ranking + presupuesto; `arqui_recall`, `arqui_remember` vía MCP | **Go/No-Go sobre R1** |
| **1.5 — Poliglota** | Parser de TypeScript/JavaScript. **Solo si R1 salió bien.** | Grafo sobre repos mixtos |
| **2 — Vigilar** | DSL de invariantes, checker, tres compuertas, `arqui_check`. **Esquema Supabase como nodos del grafo** (tablas, columnas, políticas RLS; aristas código→tabla) | Invariantes reales pasando en CI |
| **3 — Recordar cómo** | Captura de trayectorias, destilación, verificación, `Procedure` | Reuso medible y ahorro neto positivo |
| **4 — Escalar** | Más lenguajes, `arqui_trace` completo, migración de anclas fina | Uso en un repo ajeno |

**Fase 0a es una compuerta dura.** Verificar la contabilidad de tokens cuesta horas; descubrir que es imposible después de construir el parser cuesta el proyecto.

**El baseline (0b) se mide antes de construir el grafo (0c)**, porque no lo necesita. Eso da el número que todo lo demás debe batir y protege contra semanas de trabajo sobre una tesis sin probar.

→ Procedimiento detallado de arranque: [`docs/PHASE-0.md`](./PHASE-0.md)

La **Fase 2 es independiente** de la tesis de memoria: aporta valor aunque R1 salga mal. Es el seguro del proyecto y, para el portafolio, la pieza más demostrable — el guardián vigilando los PRs del propio ArquiGraph, visible en cada check de GitHub.

---

## 14. Verificación contra los principios

| | Cómo lo cumple la arquitectura |
|---|---|
| **P1** Bajo demanda | 4 herramientas MCP invocadas por el agente; el hook de inicio tiene prohibido inyectar (§9) |
| **P2** Presupuesto duro | `budget_tokens` en `recall` **y en `trace`** — toda herramienta que devuelva texto vive bajo techo (§2.1); el manifiesto MCP cuenta contra él (§8) |
| **P3** Anclada al grafo | `anchors` obligatorio; `signature_hash`/`body_hash` disparan `suspect` (§3.5) |
| **P4** Autoridad > similitud | Ranking de 4 señales; `supersedes` explícito; `suspect` nunca se sirve (§7.2) |
| **P5** Solo lo verificado | `Verification` obligatorio en `Procedure`; regla de admisión (§5.1) |
| **P6** Guardián determinista | DSL + recorrido de grafo, 0 tokens de LLM (§6.2) |
| **P7** Se mide a sí mismo | Contable + banco A/B como Fase 0, con criterio de kill (§12) |

### Verificación contra los anti-objetivos (§9 de RESEARCH.md)

| Anti-objetivo | Estado |
|---|---|
| Otro memory MCP genérico | ✅ Evitado — grafo AST + procedural verificado + guardián, no un `store`/`search` |
| Reimplementar parseo AST | ⚠️ **Lo hacemos a propósito** (C1: licencias e independencia). Coste asumido y acotado a un lenguaje en Fase 0. |
| Inyectar contexto al inicio | ✅ Prohibido por diseño (§9) |
| Optimizar por "recordar todo" | ✅ `statement` ≤ 280 chars; presupuesto duro; `suspect` no se sirve |
| Validación vía LLM | ✅ Guardián determinista; el LLM solo destila, y asíncrono |

---

## 15. Decisiones registradas

| ADR | Decisión |
|---|---|
| [ADR-001](./adr/ADR-001-grafo-propio.md) | Grafo propio determinista, sin dependencia de Graphify ni Engram |
| [ADR-002](./adr/ADR-002-stack.md) | Python 3.12 + SQLite |
| [ADR-003](./adr/ADR-003-identidad-nodo.md) | Identidad de nodo y disparadores de invalidación |
| [ADR-004](./adr/ADR-004-recuperacion.md) | Recuperación bajo demanda con presupuesto |
| [ADR-005](./adr/ADR-005-superficie.md) | MCP + hooks, cuatro herramientas |
| [ADR-006](./adr/ADR-006-verificacion.md) | Verificación obligatoria para persistir procedimientos |
| [ADR-007](./adr/ADR-007-licencia.md) | Licencia Apache 2.0 y banco reproducible por terceros |
| [ADR-008](./adr/ADR-008-resolucion-de-aristas.md) | Tres niveles de resolución de aristas con `confidence` |
| [ADR-009](./adr/ADR-009-parser-python-ast.md) | El parser de Python usa `ast`, no `tree-sitter` |

---

## 16. Cadena de herramientas

Decidida a partir del stack real del autor. La regla: **lo que ArquiGraph necesita para funcionar** se separa de **lo que necesita para demostrarse**.

### 16.1 Dependencias de ejecución (lo que un usuario instala)

| Herramienta | Rol |
|---|---|
| Python 3.12 + `uv` | Núcleo y distribución en un comando |
| `ast` (librería estándar) | Extracción AST de Python ([ADR-009](./adr/ADR-009-parser-python-ast.md)) |
| SQLite (librería estándar) | Almacenamiento |
| SDK de MCP | Servidor de las cuatro herramientas |
| Git | Hooks de las tres compuertas |

**Cero dependencias de ejecución.** Todo sale de la librería estándar. Sin Docker, sin servicios, sin base de datos externa (C9). Cada dependencia añadida es fricción de adopción, y la adopción es el objetivo del proyecto.

### 16.2 Dependencias de desarrollo y demostración

| Herramienta | Rol |
|---|---|
| `pytest` + cobertura | P5 exige verificación por tests; no podemos predicar lo que no practicamos |
| `ruff` | Lint y formato |
| **GitHub Actions** | Tres trabajos: tests · **guardián sobre los PRs del propio ArquiGraph** · banco reproducible |
| **Docker** | Aísla el entorno del banco para que un tercero obtenga los mismos números |
| Runner de agente | Ejecuta Claude Code en modo no interactivo y contabiliza tokens (ver R6) |

### 16.3 Fuera de alcance, y por qué

| Herramienta | Motivo |
|---|---|
| **Supabase como backend** | Nuestra BD es SQLite: independencia y cero setup. El **esquema** de Supabase sí entra al grafo como nodos (Fase 2) — son cosas distintas. |
| **n8n** | Modelar workflows de automatización es un nicho que diluye el mensaje del proyecto. Reconsiderar en Fase 4, si acaso. |
| **Vector store** | Descartado en ADR-004 hasta que la medición lo justifique. |
| **Neo4j / Kuzu** | SQLite basta para consultas de 1–2 saltos. Kuzu es la salida planificada, no el punto de partida (§10). |
| **Telemetría remota** | **Prohibida.** Ver §16.4. |

### 16.4 Métricas locales sí, telemetría remota nunca

P7 exige que el sistema mida su propio ahorro. Eso es **medición local**: el contable escribe en el `.arquigraph/` del usuario y nadie más lo ve.

> **Ningún dato sale de la máquina del usuario. Nunca.**

| | |
|---|---|
| Métricas locales (tokens ahorrados, reuso, invalidaciones) | ✅ En `.arquigraph/`, propiedad del usuario |
| Envío de cualquier dato a un servidor | ❌ Prohibido |

Razones:

1. **Adopción.** Una herramienta que lee todo el código y además envía datos fuera la bloquea cualquier departamento legal. Eso anula el objetivo de [ADR-007](./adr/ADR-007-licencia.md): cero fricción para que la prueben.
2. **Coherencia.** El proyecto se presenta como determinista, auditable y local. Un canal de salida lo contradice.
3. **Coste sin beneficio.** Servidor, privacidad, consentimiento y GDPR a cambio de datos que el proyecto no necesita.

**Nota para el banco:** la telemetría de Claude Code hacia Anthropic es irrelevante para la medición — todos los datos del banco vienen del stream JSON local. Desactivarla es opcional y solo reduce variables.

---

## 17. Preguntas abiertas

1. ~~**R6 — contabilidad de tokens.**~~ ✅ **Resuelta** (2026-09-01): `-p --output-format json` expone `usage`, caché, `total_cost_usd`, `num_turns`. Ver [FINDINGS-token-accounting.md](./FINDINGS-token-accounting.md).
2. ~~**Formato de captura de trayectorias.**~~ ✅ **Resuelta** (2026-09-01): `--output-format stream-json --include-hook-events` entrega `tool_use` con nombre e input, más el ciclo de vida de hooks. Ver [FINDINGS-agent-hooks.md](./FINDINGS-agent-hooks.md).
2b. **Memoria automática de Claude Code.** `init` reporta `memory_paths.auto`. Entender qué guarda antes de Fase 1 para no duplicar función. No bloqueante.
3. **Pesos del ranking (w₁–w₄).** Se calibran con el banco, no a mano. Fase 1.
4. **Aristas entre lenguajes.** Diferida a Fase 1.5. Una llamada de TypeScript a un endpoint Python no es extraíble del AST: se marca `AMBIGUOUS` y **no se afirma** (§3.1). Si resulta valiosa, se modela vía contratos declarados (OpenAPI), nunca por inferencia.
5. **Etiquetas de capa (`layer`).** ¿Se declaran en configuración o se infieren de la estructura de directorios? Prototipar 5 invariantes reales antes de decidir (R5).
6. **Selección de repos OSS para el banco.** Necesitan: **Python**, historial de issues cerrados enlazados a su commit de solución, y suite de tests que discrimine (falla antes del arreglo, pasa después). Fase 0b.
7. **Multi-repo.** Fuera de alcance hasta Fase 4.

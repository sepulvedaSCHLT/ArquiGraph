# Especificación — Fase 0

> Esquemas y contratos concretos para implementar. Todo lo de aquí se deriva de [`ARCHITECTURE.md`](./ARCHITECTURE.md); si algo se contradice, manda ARCHITECTURE.

---

## 1. Esquema SQLite

Archivo: `.arquigraph/graph.db` (ignorado por git, reconstruible con `arqui build --full`).

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Metadatos del grafo -------------------------------------------------------
CREATE TABLE graph_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- claves: schema_version | built_from_commit | built_at | parser_version

-- Control de reparseo incremental -------------------------------------------
CREATE TABLE files (
    path         TEXT PRIMARY KEY,   -- relativa a la raiz del repo, con "/"
    content_hash TEXT NOT NULL,
    parsed_at    TEXT NOT NULL
);

-- Nodos ---------------------------------------------------------------------
CREATE TABLE nodes (
    node_id        TEXT PRIMARY KEY,   -- ver seccion 2
    kind           TEXT NOT NULL,      -- module|class|function|method
    qualified_name TEXT NOT NULL,      -- "app.auth.service.TokenService.refresh"
    path           TEXT NOT NULL,
    signature_hash TEXT NOT NULL,      -- disparador FUERTE
    body_hash      TEXT NOT NULL,      -- disparador SUAVE
    start_line     INTEGER NOT NULL,   -- VOLATIL: solo navegacion, nunca identidad
    end_line       INTEGER NOT NULL,
    layer          TEXT                -- etiqueta arquitectonica, opcional
);
CREATE INDEX idx_nodes_path      ON nodes(path);
CREATE INDEX idx_nodes_qname     ON nodes(qualified_name);
CREATE INDEX idx_nodes_body_hash ON nodes(body_hash);   -- migracion de anclas

-- Aristas -------------------------------------------------------------------
CREATE TABLE edges (
    src           TEXT NOT NULL,
    dst           TEXT NOT NULL,
    kind          TEXT NOT NULL,   -- DEFINES|CALLS|IMPORTS|INHERITS|REFERENCES
    evidence_path TEXT NOT NULL,   -- siempre presente: la arista es citable
    evidence_line INTEGER NOT NULL,
    confidence    REAL NOT NULL DEFAULT 1.0,
    resolution    TEXT NOT NULL
        CHECK (resolution IN ('EXTRACTED','INFERRED','AMBIGUOUS')),
    PRIMARY KEY (src, dst, kind, evidence_path, evidence_line)
);
CREATE INDEX idx_edges_src ON edges(src, kind);
CREATE INDEX idx_edges_dst ON edges(dst, kind);   -- "quien llama a X"
```

**Sin clave foránea en `edges.dst`**: puede apuntar a un símbolo externo (una librería) que no tiene nodo local. Esas aristas se marcan `resolution='INFERRED'` o `'AMBIGUOUS'` según se pueda resolver el origen.

Las tablas `memories`, `procedures` e `invariants` llegan en sus fases. **No crearlas ahora**: un esquema escrito antes de tener el caso de uso se escribe mal.

---

## 2. Identidad y hashes

Todo con **BLAKE2b, `digest_size=8`** → 16 caracteres hexadecimales. Debe ser estable entre ejecuciones y entre máquinas.

### 2.1 `node_id`

```python
node_id = blake2b(f"{path}::{qualified_name}::{kind}".encode(), digest_size=8).hexdigest()
```

`path` siempre relativa a la raíz del repositorio y con separador `/`, también en Windows.

**No entran**: número de línea, offset de bytes, contenido, orden de aparición.

### 2.2 `signature_hash` — disparador fuerte

Se construye desde la firma normalizada:

```
{kind}|{nombre}|{param1}:{anotacion1}{=} , {param2}:{anotacion2}{=} |{retorno}
```

- Los parámetros van **en orden** (posicionales) — reordenar es un cambio de contrato.
- Se incluye la anotación de tipo si existe; si no, cadena vacía.
- Se incluye **si el parámetro tiene valor por defecto** (marca `=`), pero **no el valor**.
- Se incluye la anotación de retorno.
- **No** se incluyen decoradores en Fase 0 (revisar en Fase 2: pueden ser relevantes para invariantes).

### 2.3 `body_hash` — disparador suave

Hash del cuerpo tras normalizar:

1. Eliminar comentarios.
2. Eliminar docstrings.
3. Colapsar todo espacio en blanco consecutivo a un solo espacio.
4. `strip()`.

Un cambio de formato o de comentarios **no** debe alterar `body_hash`. Esto es verificable con un test y debe tenerlo.

### 2.4 Migración de anclas

Al reparsear, comparar nodos desaparecidos contra nodos nuevos:

```
si body_hash(desaparecido) == body_hash(nuevo)
   y node_id(desaparecido) != node_id(nuevo):
       → renombrado o movimiento
       → MIGRAR las anclas (no invalidar)
```

Si un mismo `body_hash` coincide con **varios** nodos nuevos, es ambiguo: no migrar, invalidar. Registrarlo en las métricas de R2.

---

## 3. Formato de tarea del banco

`bench/tasks/<task_id>.json` — deliberadamente parecido a SWE-bench, para que los resultados sean comparables.

```json
{
  "task_id": "proyecto-1234",
  "repo": "https://github.com/org/proyecto",
  "language": "python",
  "base_commit": "a1b2c3d4",
  "solution_commit": "e5f6a7b8",
  "issue_url": "https://github.com/org/proyecto/issues/1234",
  "problem_statement": "Texto del issue, tal cual. Es el prompt del agente.",
  "setup_commands": ["pip install -e ."],
  "test_command": "python -m pytest -q",
  "fail_to_pass": ["tests/test_auth.py::test_refresh_expira"],
  "pass_to_pass": ["tests/test_auth.py::test_login_ok"],
  "docker_image": "arquigraph-bench/proyecto:a1b2c3d4"
}
```

### Criterio de admisión — obligatorio y automático

Una tarea entra al banco **solo si**:

| Comprobación | En `base_commit` | En `solution_commit` |
|---|---|---|
| `fail_to_pass` | **falla** | **pasa** |
| `pass_to_pass` | pasa | pasa |

Si no discrimina, no mide nada. Debe verificarse con un script, nunca a ojo.

---

## 4. Registro de ejecución (ledger)

`bench/runs/<run_id>.json`

```json
{
  "run_id": "2026-09-01T14-22-05_proyecto-1234_B_r2",
  "task_id": "proyecto-1234",
  "mode": "B",
  "repetition": 2,
  "started_at": "2026-09-01T14:22:05Z",

  "agent": {
    "claude_code_version": "2.1.257",
    "model": "claude-...",
    "plugins": [],
    "mcp_servers": ["arquigraph"],
    "tools": ["Read", "Edit", "Bash"],
    "permission_mode": "default"
  },

  "outcome": {
    "success": true,
    "fail_to_pass_ok": true,
    "pass_to_pass_ok": true,
    "is_error": false,
    "stop_reason": "end_turn"
  },

  "cost": {
    "total_cost_usd": 0.4231,
    "input_tokens": 412,
    "output_tokens": 3180,
    "cache_creation_input_tokens": 24118,
    "cache_read_input_tokens": 190442,
    "num_turns": 14,
    "duration_ms": 82311
  },

  "trajectory": [
    { "turn": 1, "tool": "Read", "input": { "file_path": "..." } },
    { "turn": 2, "tool": "Bash", "input": { "command": "pytest -q" } }
  ],

  "arquigraph": {
    "recall_calls": 2,
    "trace_calls": 1,
    "tokens_served": 1740,
    "items_served": 6,
    "items_omitted": 11
  }
}
```

### Reglas

- `agent` se rellena **desde el evento `system/init`** del stream, no desde lo que creíamos configurar. Si no coincide con lo esperado, **la ejecución se descarta**.
- `cost.total_cost_usd` es la **métrica primaria** del criterio de kill de R1. Con caché de por medio, "tokens totales" es ambiguo.
- En modo A, el bloque `arquigraph` va a `null`.

---

## 5. Invocación del agente

```bash
claude -p "<problem_statement>" \
  --settings bench/config/settings.bench.json \
  --model "<fijado>" \
  --allowedTools "Read,Edit,Bash,Glob,Grep" \
  --output-format stream-json \
  --include-hook-events \
  --verbose
```

`bench/config/settings.bench.json` — versionado en el repo:

```json
{
  "model": "sonnet",
  "enableWorkflows": false,
  "enabledPlugins": {}
}
```

> ⚠️ **Verificar, no asumir.** El esquema exacto de `settings.json` para desactivar plugins no está confirmado. Tras la primera ejecución, comprobar en el `init` que `plugins` viene vacío y que el modelo es el esperado. Si no, usar `--bare` como refuerzo. El aislamiento se **verifica en cada ejecución**, no se da por hecho.

### Parseo del stream

Las llamadas a herramientas viven **dentro** de `message.content`, como bloques `tool_use` / `tool_result` — no en el `type` de nivel superior.

| Evento | Qué extraer |
|---|---|
| `system` / `init` | Bloque `agent` completo |
| `assistant` → bloque `tool_use` | `name`, `input` → trayectoria |
| `user` → bloque `tool_result` | Salida de tests |
| `result` / `success` | `usage`, `total_cost_usd`, `num_turns` |

---

## 6. Contrato de la CLI

```
arqui build [RUTA]              Construye o actualiza el grafo (incremental)
arqui build --full              Reconstruye desde cero
arqui stats                     Nodos, aristas, commit de origen, frescura

arqui trace --symbol NOMBRE     Quien llama a X / a quien llama X
arqui trace --file RUTA         Nodos de un archivo y sus vecinos
    [--depth N]                 Profundidad (por defecto 1)
    [--budget-tokens N]         Techo de salida (P2, por defecto 2000)

arqui bench validate            Verifica que las tareas discriminan
arqui bench run --mode A|B --repetitions N
arqui bench report              Comparativa A/B
```

Toda salida acepta `--json` para consumo programático.

---

## 7. Orden de implementación

Cada paso con su test antes de pasar al siguiente.

| # | Qué | Test que lo cierra |
|---|---|---|
| 1 | `core/identity/` — hashes y normalización | Reformatear un archivo **no** cambia `body_hash`; renombrar un parámetro **sí** cambia `signature_hash` |
| 2 | `core/graph/schema.py` — DDL y migraciones | Crear BD vacía, verificar tablas e índices |
| 3 | `core/parser/python.py` — nodos | Un archivo de prueba produce los nodos esperados con su `qualified_name` |
| 4 | `core/parser/python.py` — aristas | `CALLS`, `IMPORTS`, `INHERITS` con evidencia correcta |
| 5 | `core/graph/store.py` — escritura y reparseo incremental | Cambiar un archivo solo reparsea ese archivo |
| 6 | `core/graph/queries.py` — travesía | "quién llama a X" devuelve la ruta correcta |
| 7 | `cli/` — `build`, `stats`, `trace` | `arqui build .` sobre el propio repo y `arqui trace` responde |
| 8 | `bench/ledger/` — parseo del stream | Con un `.jsonl` de ejemplo, extrae coste y trayectoria |
| 9 | `bench/runner/` — modo A | Piloto de coste: 3 tareas × 3 repeticiones |

**Los pasos 8 y 9 no dependen del 1–7.** Se pueden hacer en paralelo, y el baseline se mide antes de que el grafo exista.

---

## 8. Piloto de coste — antes del banco completo

R7 dice que el banco cuesta dinero real. Antes de lanzar 120–180 ejecuciones:

1. Correr 3 tareas × 3 repeticiones en modo A.
2. Medir el coste real por tarea.
3. Extrapolar: `coste_medio × n_tareas × repeticiones × 2 modos`.
4. **Decidir el tamaño del corpus con esa cifra en la mano**, no antes.

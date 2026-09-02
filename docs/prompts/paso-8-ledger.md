# Prompt — Paso 8: el ledger del banco

> Especificación ejecutable para `arquigraph/bench/ledger/`.
> Paso 8 de [SPEC-FASE-0 §7](../SPEC-FASE-0.md), formato en [§4](../SPEC-FASE-0.md).
> Base empírica: [FINDINGS-token-accounting.md](../FINDINGS-token-accounting.md) y [FINDINGS-agent-hooks.md](../FINDINGS-agent-hooks.md).
>
> **Alcance: solo parseo.** Nada de `subprocess`, nada de red, ningún proceso lanzado.
> Ejecutar el agente es el paso 9 y **no se implementa aquí**.

---

## Por qué este módulo importa

Es el que produce la cifra del criterio de kill de R1. Si mide mal, todo el proyecto avanza sobre un número falso.

---

## Objetivo

```python
# arquigraph/bench/ledger/stream.py

def parse_stream(lines: Iterable[str]) -> ParsedRun:
    """Convierte la salida stream-json de una ejecucion en un registro.

    Raises:
        IncompleteStreamError: si falta el evento `init` o el `result`.
    """
```

### Estructuras

```python
@dataclass(frozen=True)
class AgentInfo:
    claude_code_version: str
    model: str
    plugins: tuple[str, ...]        # "nombre@version"
    mcp_servers: tuple[str, ...]
    tools: tuple[str, ...]
    permission_mode: str
    cwd: str


@dataclass(frozen=True)
class Cost:
    total_cost_usd: float
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    num_turns: int
    duration_ms: int


@dataclass(frozen=True)
class ToolCall:
    turn: int
    tool: str
    tool_input: dict


@dataclass(frozen=True)
class ParsedRun:
    session_id: str
    agent: AgentInfo
    cost: Cost
    trajectory: tuple[ToolCall, ...]
    is_error: bool
    stop_reason: str | None
    malformed_lines: int     # lineas que no eran JSON, contadas y descartadas
```

---

## Forma real del stream

Estos son fragmentos **observados**, no inventados. Se corresponden con Claude Code `2.1.257`.

### `system` / `init` — una vez, al principio

```json
{
  "type": "system", "subtype": "init",
  "session_id": "05504ffe-...",
  "claude_code_version": "2.1.257",
  "model": "claude-opus-5[1m]",
  "cwd": "/tmp/r6test",
  "permissionMode": "default",
  "mcp_servers": [],
  "tools": ["Task", "Bash", "Edit", "Read"],
  "plugins": [{"name": "superpowers", "version": "6.3.0", "source": "..."}]
}
```

Ojo: la clave es **`permissionMode`** en camelCase, no `permission_mode`.

### `assistant` — las llamadas a herramientas van DENTRO

```json
{
  "type": "assistant",
  "message": {"content": [
    {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/x.txt"}}
  ]}
}
```

Un mensaje `assistant` puede traer varios bloques, y mezclar `text` con `tool_use`.

### `result` / `success` — una vez, al final

```json
{
  "type": "result", "subtype": "success",
  "is_error": false,
  "stop_reason": "end_turn",
  "num_turns": 1,
  "duration_ms": 1891,
  "total_cost_usd": 0.092123,
  "usage": {
    "input_tokens": 2,
    "output_tokens": 4,
    "cache_creation_input_tokens": 8695,
    "cache_read_input_tokens": 10126
  }
}
```

### Otros eventos

`user` (trae los `tool_result`), `system`/`hook_started`, `system`/`hook_response`, `rate_limit_event`. **Se ignoran en este paso.**

---

## Reglas de parseo

1. **Líneas vacías**: se saltan sin contar.
2. **Líneas que no son JSON válido**: se cuentan en `malformed_lines` y se descartan. Ocurre de verdad: el runner redirige `2>&1` y se cuela texto de stderr.
3. **Sin evento `init`** → `IncompleteStreamError`. Sin `agent` no hay reproducibilidad y la ejecución no vale.
4. **Sin evento `result`** → `IncompleteStreamError`. La ejecución se cortó; no hay coste que registrar.
5. **Numeración de turnos**: cada mensaje `assistant` incrementa el turno, empezando en 1. Todos los `tool_use` de un mismo mensaje comparten turno.
6. **Campos ausentes en `usage`**: se toman como `0`. No se inventan.
7. `plugins` se serializa como `"nombre@version"`; si falta la versión, solo el nombre.

---

## Verificación de aislamiento

```python
# arquigraph/bench/ledger/isolation.py

def check_isolation(agent: AgentInfo, expected: ExpectedEnvironment) -> list[str]:
    """Devuelve la lista de desviaciones. Vacia = ejecucion valida."""
```

```python
@dataclass(frozen=True)
class ExpectedEnvironment:
    model: str
    allow_plugins: bool = False
    allowed_mcp_servers: tuple[str, ...] = ()
```

Desviaciones que debe detectar, con mensaje legible cada una:

| Comprobación | Por qué |
|---|---|
| `agent.model` distinto del esperado | Comparar A y B con modelos distintos invalida la medición |
| Hay plugins y `allow_plugins` es falso | Mediríamos los plugins del autor, no ArquiGraph |
| Un servidor MCP fuera de los permitidos | En modo A no debe haber ninguno |

Esta función es la que hace creíbles las cifras publicadas. Sin ella, [ADR-007](../adr/ADR-007-licencia.md) no se cumple: nadie podría reproducirlas.

---

## Fixtures

En `tests/fixtures/`, escritos a mano y **versionados**, no generados en la ejecución del test:

| Archivo | Contenido |
|---|---|
| `stream_simple.jsonl` | init + un assistant con un `tool_use` + user + result exitoso |
| `stream_multiturno.jsonl` | tres mensajes assistant, dos con herramientas |
| `stream_sucio.jsonl` | igual que el simple, con dos líneas de texto de stderr intercaladas |
| `stream_sin_result.jsonl` | init y assistant, sin `result` |
| `stream_contaminado.jsonl` | init con dos plugins y un modelo distinto |

---

## Restricciones

1. **Sin `subprocess`, sin red, sin lanzar procesos.** Eso es el paso 9.
2. **Sin dependencias nuevas.** Librería estándar (ADR-009).
3. **No modificar** nada fuera de `arquigraph/bench/ledger/` y `tests/`.
4. **No inventar valores por defecto para el coste.** Un campo ausente en `usage` es `0`; un `total_cost_usd` ausente es un stream incompleto.
5. **Sin `print`.**

---

## Criterios de aceptación

Tests en `tests/test_ledger.py`.

### Parseo básico

- [ ] `stream_simple.jsonl` produce un `ParsedRun` con el `session_id` correcto
- [ ] `agent` se rellena desde `init`, incluida la clave camelCase `permissionMode`
- [ ] `cost` recoge los cuatro contadores de tokens, el coste y `num_turns`
- [ ] La trayectoria contiene la llamada a `Read` con su `input`

### Trayectoria

- [ ] `stream_multiturno.jsonl` numera los turnos 1, 2, 3 en orden
- [ ] Varios `tool_use` en un mismo mensaje comparten número de turno
- [ ] Un mensaje `assistant` con solo texto no aporta llamadas pero sí incrementa el turno
- [ ] Los eventos `user`, `hook_started`, `hook_response` y `rate_limit_event` se ignoran

### Robustez

- [ ] `stream_sucio.jsonl` parsea bien y reporta `malformed_lines == 2`
- [ ] Las líneas vacías no cuentan como malformadas
- [ ] `stream_sin_result.jsonl` lanza `IncompleteStreamError`
- [ ] Un stream sin `init` lanza `IncompleteStreamError`
- [ ] Un `usage` sin `cache_read_input_tokens` lo deja en 0, no falla

### Aislamiento

- [ ] Entorno correcto → lista vacía
- [ ] Modelo distinto → una desviación que nombra ambos modelos
- [ ] Plugins presentes con `allow_plugins=False` → una desviación que los nombra
- [ ] Servidor MCP no permitido → una desviación
- [ ] Varias desviaciones a la vez → todas en la lista, no solo la primera

---

## Verificación

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Los 125 tests existentes deben seguir pasando.

# Hallazgos — Hooks y captura de trayectorias

- **Fecha:** 2026-09-01
- **Herramienta:** Claude Code `2.1.257`
- **Pregunta evaluada:** [#2](./ARCHITECTURE.md#17-preguntas-abiertas) — *¿podemos observar lo que hace el agente para destilar procedimientos (P5)?*
- **Veredicto:** ✅ **Viable.** La Fase 3 procede como está diseñada.

---

## 1. Método

```bash
claude -p "lee prueba.txt y dime en una palabra que dice" \
  --output-format stream-json \
  --include-hook-events \
  --verbose \
  --allowedTools "Read"
```

Un solo canal —`stream-json` con `--include-hook-events`— entrega respuesta, llamadas a herramientas y ciclo de vida de hooks. No hacen falta hooks propios instalados para **observar**.

---

## 2. Captura de trayectorias: confirmada

```
ASSISTANT TOOL_USE ===== Read {"file_path": "/tmp/r6test/prueba.txt"}
USER TOOL_RESULT ===== "1\tcontenido de prueba\n2\t"
ASSISTANT TEXT     ===== "Prueba"
```

Vemos **el nombre de la herramienta y su input exacto**. Eso es todo lo que la destilación procedural necesita:

| Necesidad de la Fase 3 | Cubierta por |
|---|---|
| Qué archivos tocó y en qué orden | `tool_use` con `input` |
| Qué comandos ejecutó (tests incluidos) | `tool_use` de `Bash` |
| Si los tests pasaron | `tool_result` del comando de test |
| Dónde terminó | `result` con `subtype: success` |

Las llamadas viven **dentro** de `message.content` como bloques `tool_use` / `tool_result`, no en el `type` de nivel superior. El parser del `bench/ledger` debe descender a los bloques.

---

## 3. Eventos de hook observados

| Evento | Momento |
|---|---|
| `SessionStart:startup` | Al abrir la sesión |
| `Stop` | Al terminar el turno |

Estructura de la respuesta:

```json
{
  "hook_id": "...", "hook_name": "Stop", "hook_event": "Stop",
  "output": "", "stdout": "", "stderr": "",
  "exit_code": 0, "outcome": "success",
  "session_id": "..."
}
```

Solo aparecen los eventos con handler registrado. En esta instalación los registró el plugin `superpowers`; con más handlers instalados aparecerían más eventos del ciclo de vida.

**Lo relevante para ArquiGraph:** existe `SessionStart`, que es donde ADR-005 quiere colocar el aviso de frescura del grafo — y `exit_code`/`outcome` permiten que un hook comunique resultado sin inyectar contenido.

---

## 4. El hallazgo principal: el anti-patrón, capturado en vivo

La respuesta del hook `SessionStart` del plugin `superpowers`:

```json
"hookSpecificOutput": {
  "hookEventName": "SessionStart",
  "additionalContext": "<EXTREMELY_IMPORTANT>\nYou have superpowers.\n\n**Below is the full content of your …"
}
```

> Un plugin está **inyectando contexto en el prompt de cada sesión** mediante el hook `SessionStart`, usando el campo `additionalContext`.

Esto es exactamente el mecanismo que [RESEARCH.md §2](./RESEARCH.md#2-hallazgo-crítico-los-archivos-de-contexto-no-funcionan) documenta como perjudicial y que [ADR-005](./adr/ADR-005-superficie.md) **prohíbe por diseño** en ArquiGraph.

### Por qué importa

1. **Explica el coste medido en R6.** Los 18.821 tokens de contexto para responder `ok` no eran overhead del CLI: eran plugins, skills y `additionalContext` inyectados antes de que el usuario escribiera nada.

2. **Demuestra que la tentación es real y está normalizada.** El hook `SessionStart` ofrece un campo literalmente diseñado para inyectar. La disciplina de ADR-005 no es teórica: es resistir una API que invita a hacerlo.

3. **Y demuestra que el mismo mecanismo sirve bien.** ArquiGraph usará `SessionStart` con `additionalContext` **vacío** y `exit_code` para señalar grafo obsoleto. El canal es el mismo; la diferencia es no meter contenido.

### Coste del manifiesto, confirmado

El evento `init` lista lo que se carga en cada sesión de esta instalación:

- `tools`: Task, Bash, CronCreate, CronDelete, CronList, DesignSync, Edit, EnterWorktree, ExitWorktree, ListAgents, Monitor, NotebookEdit, PushNotification, Read, …
- `skills`: graphify, deep-research, superpowers:brainstorming, superpowers:dispatching-parallel-agents, superpowers:executing-plans, …
- `slash_commands`: una lista aún más larga
- `plugins`: 4 activos con sus versiones

Cada entrada lleva su descripción al prompt de sistema. Es la validación empírica de la **regla de las cuatro herramientas** de ADR-005: el manifiesto es contexto precargado, y crece sin que nadie lo note.

---

## 5. Reproducibilidad: qué registrar por ejecución

El evento `system/init` entrega todo lo necesario:

| Campo | Por qué se registra |
|---|---|
| `model` | Comparar A/B con modelos distintos invalida la medición |
| `claude_code_version` | Los resultados no son comparables entre versiones |
| `plugins` (con versión) | Cambian el prompt de sistema |
| `skills`, `slash_commands`, `tools` | Coste del manifiesto |
| `mcp_servers` | En modo B incluirá ArquiGraph |
| `permissionMode`, `cwd` | Condiciones de ejecución |
| `session_id`, `uuid` | Trazabilidad |

---

## 6. Consecuencia para el banco: aislamiento obligatorio

La configuración personal observada:

```json
{ "model": "opus[1m]", "enableWorkflows": true,
  "enabledPlugins": { "superpowers": true, "frontend-design": true,
                      "superdesign": true, "ralph-loop": true } }
```

Correr el banco así mediría **los plugins del autor**, no ArquiGraph. Y al cambiar cualquier plugin, los resultados dejarían de ser reproducibles — incumpliendo [ADR-007](./adr/ADR-007-licencia.md).

**Regla del banco:**

```bash
claude -p "<tarea>" \
  --settings bench/config/settings.bench.json \
  --model <fijado> \
  --allowedTools "<fijado>" \
  --output-format stream-json --include-hook-events --verbose
```

- `settings.bench.json` **versionado en el repo**: modelo fijo, cero plugins, sin workflows
- Considerar `--bare` para descartar además el `CLAUDE.md` automático
- El `init` de cada ejecución se guarda junto al resultado y **se verifica** que coincide con lo esperado; si no, la ejecución se descarta

---

## 7. Estado de las preguntas abiertas

| Pregunta | Estado |
|---|---|
| #1 — R6, contabilidad de tokens | ✅ Resuelta ([FINDINGS-token-accounting.md](./FINDINGS-token-accounting.md)) |
| #2 — Captura de trayectorias | ✅ **Resuelta.** `stream-json` + `--include-hook-events` |

**Fase 0a completada.** Las dos incógnitas que podían invalidar el plan están despejadas.

---

## 8. Nota lateral

`init` reporta `memory_paths.auto = ~/.claude/projects/<proyecto>/memory/`. Claude Code tiene su propia memoria automática por proyecto. Conviene entender qué guarda antes de la Fase 1, para no duplicar función ni entrar en conflicto. No es bloqueante.

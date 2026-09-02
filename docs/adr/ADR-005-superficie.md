# ADR-005 — MCP + hooks como superficie, con cuatro herramientas

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [RESEARCH.md §2, P1, P5, P6](../RESEARCH.md) · [ARCHITECTURE.md §8, §9](../ARCHITECTURE.md)

## Contexto

ArquiGraph necesita dos cosas que ninguna superficie única resuelve bien:

1. **Que el agente pida conocimiento cuando lo necesita** → MCP encaja: es el mecanismo estándar de herramientas bajo demanda (P1).
2. **Que el sistema observe lo que ocurre sin que el agente coopere** → captura de trayectorias (P5), invalidación tras commit (P3) y validación de diffs (P6). Nada de esto puede depender de que el agente se acuerde de invocarlo.

Solo MCP nos deja ciegos al ciclo de vida del código. Solo hooks nos obliga a que el agente ejecute comandos de shell, que es frágil y difícil de medir.

## Decisión

**MCP server + hooks de git y de sesión.**

### Las cuatro herramientas MCP

| Herramienta | Propósito |
|---|---|
| `arqui_recall` | Recuperación con presupuesto. La principal. |
| `arqui_trace` | Consulta estructural: *"¿quién llama a X?"*, *"¿qué rompo si cambio Y?"*. Rutas citables. |
| `arqui_check` | Valida un diff o un plan contra invariantes. 0 tokens de LLM. |
| `arqui_remember` | Registra una decisión con anclas y autoridad. |

### La regla de las cuatro

> **El manifiesto MCP cuenta contra el presupuesto de tokens.**

Las descripciones de las herramientas viven en el prompt de sistema de **cada** sesión. Diez herramientas con descripciones generosas son un `AGENTS.md` entrando por la puerta de atrás — el mismo mecanismo de degradación de §2, con otro nombre.

Compromisos vinculantes:
- Máximo **cuatro** herramientas. Añadir una quinta exige una ADR que justifique el coste permanente.
- Descripciones de **una línea**.
- El coste total del manifiesto se mide en el banco como parte del overhead.

### Los hooks

| Hook | Acción | Coste |
|---|---|---|
| `post-commit` / `post-merge` | Reparseo incremental → recalcular hashes → migrar anclas → marcar `suspect` | 0 tokens |
| `pre-commit` | `arqui_check` sobre el diff staged; bloquea en `severity: error` | 0 tokens |
| **inicio de sesión** | **NO inyecta contexto.** Solo verifica frescura del grafo. | ~0 |
| fin de tarea | Captura la trayectoria; si está verificada, la encola para destilación asíncrona | diferido |

### La prohibición explícita

> **El hook de inicio de sesión tiene prohibido inyectar conocimiento.**

Es el punto donde toda la arquitectura se puede echar a perder con una línea de código bienintencionada. Inyectar ahí es literalmente el experimento que ETH Zurich ya corrió y que salió mal (§2.2). Queda prohibido por diseño y debe verificarse en revisión de código.

## Consecuencias

**Positivas**
- Cubre los siete principios: MCP da P1/P2/P4, los hooks dan P3/P5/P6, el contable da P7.
- La captura de trayectorias no depende de la cooperación del agente.
- El guardián corre en `pre-commit` y en CI con el mismo código.

**Negativas**
- Instalación en dos pasos (servidor MCP + hooks), con más fricción que una sola pieza.
- Los hooks son específicos de git; un flujo sin git queda fuera de alcance.
- El formato de captura de trayectorias depende de qué exponga cada agente. **Hay que investigarlo en Fase 0** para no diseñar a ciegas.
- `pre-commit` en Python arranca lento; si supera 500 ms de forma consistente, el guardián se porta a un binario (ver ADR-002).

## Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| Solo MCP | Sin hooks no hay captura de trayectorias (P5) ni guardián automático (P6) — se pierden dos de los tres diferenciadores |
| CLI + hooks, sin MCP | Obliga al agente a ejecutar shell para recuperar: frágil, poco portable y difícil de instrumentar |
| Skill del agente (tipo `/comando`) | Atado a un único agente; contradice la portabilidad entre Claude Code, Codex y Cursor |

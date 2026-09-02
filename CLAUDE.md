# ArquiGraph

Grafo determinista + memoria anclada + guardián de invariantes para agentes de programación.

## Reglas del proyecto

- El grafo semántico es determinista. Cero LLM, cero embeddings. Lo que no se extrae del AST se marca `AMBIGUOUS` y no se afirma.
- Toda salida hacia el agente lleva presupuesto de tokens. Sin excepciones.
- Nada se inyecta en el prompt de sistema. La recuperación es bajo demanda.
- Máximo cuatro herramientas MCP. Una quinta exige una ADR.
- Solo se persiste conocimiento verificado: tests en verde o commit aplicado.
- Fase 0 es solo Python. TypeScript entra en Fase 1.5.

## Antes de cambiar el diseño

Las decisiones están en `docs/adr/` y se derivan de la evidencia en `docs/RESEARCH.md`. Si una propuesta contradice una ADR, se discute la ADR — no se ignora.

## Comandos

```bash
uv sync              # instalar
uv run pytest        # tests
uv run ruff check .  # lint
```

---

*Este archivo es corto a propósito. `docs/RESEARCH.md` §2 documenta por qué los archivos de contexto largos degradan a los agentes; sería incoherente que este proyecto tuviera uno.*

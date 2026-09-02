# Contribuir a ArquiGraph

## Certificado de origen (DCO)

Este proyecto usa [Developer Certificate of Origin](https://developercertificate.org/). Firma cada commit:

```bash
git commit -s -m "feat: ..."
```

El flag `-s` añade `Signed-off-by:` con tu nombre y correo de git. No se exige CLA: [ADR-007](docs/adr/ADR-007-licencia.md) renuncia explícitamente a la vía de licencia comercial, así que no hace falta transferir derechos.

## Flujo de trabajo

Todo entra por Pull Request. Tres compuertas de revisión:

| Momento | Qué corre |
|---|---|
| `pre-commit` | Lint, formato y (desde Fase 2) el guardián sobre el diff staged |
| `pre-push` | Tests y comprobación completa de invariantes |
| Pull Request | CI en GitHub Actions |

## Entorno

```bash
uv sync --all-extras --dev
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Reglas de diseño no negociables

Se derivan de la evidencia en [`docs/RESEARCH.md`](docs/RESEARCH.md) y están formalizadas en [`docs/adr/`](docs/adr/).

1. **El grafo semántico es determinista.** Nada de LLM ni embeddings en la capa semántica. Lo que no se extrae del AST se marca `AMBIGUOUS` y no se afirma.
2. **Nada se inyecta en el prompt de sistema.** Ni por hook de inicio de sesión, ni por `additionalContext`, ni por ningún otro canal. La recuperación es siempre bajo demanda.
3. **Toda salida hacia el agente lleva presupuesto de tokens.** Incluye `recall` y `trace`.
4. **Máximo cuatro herramientas MCP.** El manifiesto vive en el prompt de sistema de cada sesión: es contexto precargado. Añadir una quinta exige una ADR que justifique el coste permanente.
5. **Solo se persiste lo verificado.** Un procedimiento sin tests en verde o commit aplicado se descarta; no se guarda "por si acaso".
6. **Ningún dato sale de la máquina del usuario.** Las métricas de P7 son locales, en `.arquigraph/`. No se acepta telemetría remota, "analíticas anónimas" ni comprobación de versión que reporte uso. ArquiGraph lee todo el código del usuario: esa confianza no se negocia por datos que el proyecto no necesita.

Una propuesta que contradiga una ADR no se rechaza sin más: **se discute la ADR**. Si la evidencia cambió, la decisión cambia — y se registra.

## Commits

Formato [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(core): extraer aristas CALLS del AST de Python
fix(graph): migrar anclas al renombrar una funcion
docs(adr): ADR-008 sobre el DSL de invariantes
test(bench): validar que las tareas discriminan
```

## Añadir una decisión de arquitectura

```bash
cp docs/adr/ADR-001-grafo-propio.md docs/adr/ADR-00N-nombre.md
```

Debe citar la sección de `RESEARCH.md` de la que se deriva, y listar las alternativas descartadas con su motivo.

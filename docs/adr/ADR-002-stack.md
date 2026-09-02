# ADR-002 — Python 3.12 + SQLite

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [ARCHITECTURE.md §10, §12](../ARCHITECTURE.md)

## Contexto

El núcleo debe: parsear AST con tree-sitter, mantener un grafo consultable, servir un servidor MCP, ejecutar hooks de git y correr un banco de medición A/B. Las opciones reales eran Python, Go, TypeScript y Rust.

El factor decisivo no es el rendimiento en régimen, sino **la velocidad de iteración durante la Fase 0-1**, porque ahí es donde vive el riesgo existencial del proyecto (R1). Optimizar la distribución de un binario antes de saber si la tesis se sostiene es optimizar lo que quizá se tire.

## Decisión

**Python 3.12** para el núcleo, **SQLite** como almacenamiento único (`.arquigraph/graph.db`).

Distribución con `uv` / `uvx` para que la instalación sea de un solo comando.

## Justificación

| Factor | Valoración |
|---|---|
| `py-tree-sitter` | Binding maduro y mantenido |
| SDK de MCP | Implementación oficial en Python, de primera clase |
| SQLite | En la librería estándar. Cero servicios que levantar. |
| Banco de medición | Análisis de datos y reporting: es el terreno natural de Python |
| Arranque | **No es un problema**: el servidor MCP es un proceso de larga vida, no se lanza por invocación |

## Consecuencias

**Positivas**
- Iteración rápida justo donde está el riesgo.
- Ecosistema completo para el banco de medición.
- SQLite elimina toda fricción de adopción.

**Negativas**
- **Distribución más incómoda que un binario único.** Go daría un ejecutable sin dependencias; Python exige un entorno. Es el contra real de esta decisión.
- Los hooks de git en Python arrancan más lento que un binario (~100–300 ms). Aceptable para `post-commit`, a vigilar en `pre-commit`.

**Disparadores de reevaluación**
- Si el hook `pre-commit` supera los **500 ms** de forma consistente, se reescribe el guardián en Go como binario auxiliar. El guardián es autocontenido (recorrido de grafo puro), así que ese port es barato y no arrastra al resto.
- Si el grafo necesita travesías profundas, se evalúa Kuzu antes de cambiar de lenguaje.

## Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| **Go** | Binario único y arranque instantáneo, pero iteración más lenta y peor ecosistema de análisis para el banco. Sigue siendo el candidato para portar el guardián si el arranque duele. |
| **TypeScript / Node** | Buena distribución vía `npx` y alineado con el ecosistema de agentes, pero peor manejo de datos pesados que Python o Go. |
| **Rust** | Injustificable antes de validar R1: máxima velocidad de ejecución al precio de la mínima velocidad de desarrollo, en la fase donde solo importa lo segundo. |

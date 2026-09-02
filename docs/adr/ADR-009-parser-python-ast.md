# ADR-009 — El parser de Python usa `ast`, no `tree-sitter`

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Enmienda a:** [ADR-001](./ADR-001-grafo-propio.md)
- **Base:** [ADR-003](./ADR-003-identidad-nodo.md) · [ADR-008](./ADR-008-resolucion-de-aristas.md)

## Contexto

ADR-001 nombraba `tree-sitter` como la vía de extracción, pensando en la cobertura multilenguaje. Al implementar [ADR-003](./ADR-003-identidad-nodo.md) apareció una incoherencia: `body_hash` ya se deriva del módulo `ast` de la librería estándar, porque el volcado del AST descarta comentarios y formato **por construcción**. Teníamos dos árboles distintos para el mismo código.

Y al especificar [ADR-008](./ADR-008-resolucion-de-aristas.md) apareció el argumento decisivo: distinguir `EXTRACTED` de `INFERRED` exige **análisis de ámbito y resolución de imports**. El `ast` de Python entrega esa información de forma directa; hacerlo sobre el árbol concreto de tree-sitter es reconstruir a mano lo que el intérprete ya sabe.

## Decisión

**El parser de Python usa `ast` de la librería estándar.**

`tree-sitter` sale de las dependencias hasta que haga falta.

Cuando llegue TypeScript en Fase 1.5 —y solo si R1 sale bien— entrará con su propio módulo de extracción, que iba a ser código aparte en cualquier caso. La abstracción común entre lenguajes se diseñará entonces, con dos implementaciones reales delante en vez de una imaginada.

## Consecuencias

**Positivas**
- **Cero dependencias de ejecución** en Fase 0. `arquigraph` se instala y funciona con la librería estándar. Es la mínima fricción de adopción posible, y eso es el objetivo de [ADR-007](./ADR-007-licencia.md).
- Un solo árbol para `body_hash` y para la extracción: sin dos fuentes de verdad que puedan discrepar.
- Ámbitos e imports resueltos con exactitud, que es lo que ADR-008 necesita para no mentir.
- `ast.unparse` normaliza anotaciones de tipo gratis.

**Negativas**
- Dos caminos de extracción cuando llegue TypeScript. Asumido: iban a ser dos de todos modos, porque los modelos de módulo, clase y ámbito difieren entre ambos lenguajes.
- `ast` solo parsea código sintácticamente válido para la versión del intérprete. Un archivo con sintaxis de Python 3.13 falla en 3.12. Se registra el error por archivo y se continúa; no se aborta la construcción del grafo.
- El volcado de `ast` puede variar entre versiones mayores de CPython. Ya mitigado: `graph_meta.parser_version` lo registra.

## Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| `tree-sitter` para todo | Habría que reescribir `body_hash` sobre el CST y reconstruir el análisis de ámbito que `ast` ya da. Trabajo real a cambio de una abstracción multilenguaje que quizá no llegue nunca — Fase 1.5 depende de que R1 salga bien. |
| Ambos, con `ast` para Python y `tree-sitter` como respaldo | Dos fuentes de verdad para el mismo archivo. Cuando discrepen, no habrá forma barata de saber cuál miente. |
| LibCST | Conserva formato y comentarios, útil para reescritura de código. No lo necesitamos: solo leemos, y `body_hash` quiere justo lo contrario, que el formato desaparezca. Añade una dependencia pesada. |

## Revisión

Reevaluar al planificar la Fase 1.5. Si TypeScript entra, la pregunta será si conviene una interfaz común de extracción o si dos módulos independientes con la misma firma de salida bastan. La respuesta se decide con las dos implementaciones a la vista.

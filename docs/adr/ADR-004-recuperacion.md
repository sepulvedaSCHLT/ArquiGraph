# ADR-004 — Recuperación bajo demanda con presupuesto de tokens

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [RESEARCH.md §2, §3, §5.2-A, P1, P2, P4, R1](../RESEARCH.md) · [ARCHITECTURE.md §7](../ARCHITECTURE.md)

## Contexto

Esta es la ADR que decide si el proyecto tiene sentido.

El estudio de ETH Zurich ([arXiv 2602.11988](https://arxiv.org/pdf/2602.11988)) midió que los archivos de contexto a nivel de repositorio **degradan** el desempeño de los agentes: −3% de éxito y +20% de coste con archivos generados por LLM; apenas +4% de éxito y +19% de coste con archivos escritos por humanos.

El mecanismo de la falla es contraintuitivo: **el agente obedece bien**. Por eso ejecuta pasos correctos en abstracto e innecesarios para la tarea concreta.

Cualquier diseño de ArquiGraph que precargue conocimiento en el prompt de sistema está repitiendo ese experimento con la expectativa de un resultado distinto.

## Decisión

### 1. Bajo demanda, nunca precargado (P1)

El conocimiento se expone como **herramienta MCP que el agente invoca** (`arqui_recall`). Ningún componente inyecta contexto al inicio de sesión. El hook de inicio solo verifica la frescura del grafo.

### 2. Presupuesto de tokens duro (P2)

```python
recall(task, changed_files=None, budget_tokens=2000) -> Recall
```

El techo es **duro y sin excepciones**. La respuesta declara `tokens_used` y `omitted_count`, de modo que el agente sabe que hay más y puede pedirlo si lo necesita — en lugar de que el sistema lo decida por él.

El presupuesto incluye el coste del **manifiesto MCP**: las descripciones de las herramientas viven en el prompt de sistema de cada sesión y son, técnicamente, contexto precargado.

### 3. Anclaje determinista, sin embeddings en Fase 1

```
task + changed_files → símbolos mencionados
                     → nodos de los archivos tocados
                     → expansión de 1 salto por CALLS / IMPORTS
```

Sin vector store. Un embedding introduce indeterminismo y un modo de fallo —recuperar lo semánticamente cercano pero equivocado— que es exactamente la falla §5.2-A.

Si la medición demuestra que el recall estructural no basta, la búsqueda semántica se añade como **una señal más del ranking**, nunca como criterio único.

### 4. Ranking por autoridad, no por similitud (P4)

```
score = w₁·relevancia_grafo + w₂·autoridad + w₃·recencia + w₄·evidencia
```

- `autoridad`: human = 1.0 · agent_verified = 0.7 · inferred = 0.3
- `supersedes` explícito: una memoria superseded puntúa 0, no compite
- `status != active` se descarta **antes** del ranking, no se penaliza

Los pesos `w₁–w₄` se calibran con el banco de medición, no a mano.

## Consecuencias

**Positivas**
- Evita por construcción el modo de falla medido en §2.2.
- El coste por invocación es acotado y predecible.
- Recuperación explicable: cada ítem servido lleva su ancla y su score.
- La ausencia de vector store elimina una dependencia pesada y un modo de fallo.

**Negativas**
- **Depende de que el agente invoque la herramienta.** Es el riesgo R4 y es real: los servidores de memoria existentes sufren precisamente de baja tasa de invocación.
- El anclaje puramente léxico fallará en tareas descritas en lenguaje vago ("arregla el bug del login").
- Un presupuesto de 2.000 tokens puede quedarse corto en tareas amplias. Se calibra con datos.

**Mitigación de R4**
El hook de inicio de tarea puede **recordarle al agente que la herramienta existe** con una línea, sin inyectar contenido. Esa línea cuenta contra el presupuesto y su efecto se mide. Si no basta, se estudian disparadores más fuertes — pero la inyección de contenido queda descartada de antemano.

## Criterio de falsación (R1)

> Si el modo con ArquiGraph **no mejora** la tasa de éxito y **sube el coste más de un 10%** frente al baseline, esta ADR se rechaza y el recuperador se rediseña antes de construir nada encima.

Esta medición es la puerta de salida de la Fase 1. No es negociable.

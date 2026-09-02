# ArquiGraph — Investigación de respaldo

> **Estado:** base de decisiones de diseño
> **Fecha:** 2026-09-01
> **Alcance:** evidencia externa sobre las fallas reales de los agentes de programación, y derivación del hueco que ArquiGraph debe llenar.
> **Cómo usar este documento:** cada decisión de arquitectura (`docs/adr/`) debe citar la sección de la que se deriva. Si una afirmación de aquí queda refutada, la ADR que dependa de ella se revisa.

---

## Índice

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Hallazgo crítico: los archivos de contexto no funcionan](#2-hallazgo-crítico-los-archivos-de-contexto-no-funcionan)
3. [Dónde se gastan realmente los tokens](#3-dónde-se-gastan-realmente-los-tokens)
4. [Deriva arquitectónica y entropía agéntica](#4-deriva-arquitectónica-y-entropía-agéntica)
5. [Por qué las memorias existentes no lo resuelven](#5-por-qué-las-memorias-existentes-no-lo-resuelven)
6. [Memoria procedural: la evidencia positiva](#6-memoria-procedural-la-evidencia-positiva)
7. [El hueco: las tres capas que nadie une](#7-el-hueco-las-tres-capas-que-nadie-une)
8. [Principios de diseño derivados](#8-principios-de-diseño-derivados)
9. [Anti-objetivos](#9-anti-objetivos)
10. [Riesgos e hipótesis a validar](#10-riesgos-e-hipótesis-a-validar)
11. [Fuentes](#11-fuentes)

---

## 1. Resumen ejecutivo

La premisa original del proyecto — "ArquiGraph trabajará en conjunto con `CLAUDE.md` y `AGENTS.md` para que el agente no tenga que volver a leer la documentación" — es **parcialmente incorrecta según la evidencia disponible**.

Un estudio controlado de ETH Zurich (feb 2026) demuestra que los archivos de contexto a nivel de repositorio **degradan** el desempeño de los agentes de codificación y **encarecen** cada tarea. El problema no es que al agente le falte documentación: es que **obedece demasiado bien** a la documentación que le damos, y la mayor parte de esa documentación es irrelevante para la tarea concreta que tiene enfrente.

Por lo tanto, el valor de ArquiGraph **no está en guardar más contexto**, sino en:

1. **Recuperar poco y correcto**, bajo demanda, con un presupuesto de tokens explícito.
2. **Anclar la memoria a nodos verificables del grafo**, para que caduque sola cuando el código cambia.
3. **Destilar procedimientos verificados** (memoria procedural), que es la única capa con evidencia de ahorro real de tokens y donde el estado del arte está vacío en producto.
4. **Vigilar invariantes arquitectónicos de forma determinista**, sin gastar tokens de LLM.

---

## 2. Hallazgo crítico: los archivos de contexto no funcionan

### 2.1 El estudio

> **Gloaguen, T., Mündler, N., Müller, M., Raychev, V., Vechev, M. (2026).**
> *Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?*
> arXiv:2602.11988 [cs.SE]. Enviado el 12 feb 2026, revisado (v2) el 23 jun 2026. Licencia CC BY 4.0.
> **<https://arxiv.org/abs/2602.11988>**

**Metodología**, según el abstract: se evalúa el desempeño de agentes de codificación en **dos escenarios complementarios**:

1. Tareas de SWE-bench sobre repositorios populares, con archivos de contexto **generados por LLM**.
2. Una colección nueva de issues de repositorios que ya contenían archivos de contexto **escritos por desarrolladores**.

### 2.2 Resultados verificados

Todo lo de esta tabla es **cita directa del abstract**. Nada inferido.

| Hallazgo | Texto original |
|---|---|
| El coste sube | *"increasing inference cost by **over 20% on average**"* |
| El éxito no mejora | *"providing context files **does not generally improve** task success rates"* |
| Es general, no anecdótico | *"holds across different LLMs, coding agents, and for both LLM-generated and developer-committed context files"* |
| Los resúmenes de repositorio no ayudan | *"**repository overviews**, although popular and recommended by model providers, **are not helpful**"* |
| Y sin embargo, sirven para algo | *"context files **are** useful for specifying **non-standard coding practices**"* |

> ⚠️ **Nota de integridad.** Versiones anteriores de este documento citaban un desglose (−3% de éxito con archivos generados por LLM, +4% y +19% con archivos humanos). **Esas cifras procedían de resúmenes de terceros y no se han podido verificar contra el paper.** Se han retirado. Si alguien necesita el desglose por condición, hay que leer el PDF completo y citar la tabla concreta.

### 2.3 El mecanismo de la falla

El abstract lo dice sin ambigüedad: **las instrucciones se siguen bien** (*"instructions in the context files are well followed by coding agents"*). El problema no es que el agente ignore el archivo; es que lo obedece, y buena parte de lo que contiene no aplica a la tarea concreta.

Y lo que específicamente no funciona son los **resúmenes del repositorio** —el "aquí tienes una descripción de la arquitectura"— que es justo lo que los proveedores de modelos recomiendan poner.

### 2.4 Lectura precisa: qué autoriza y qué prohíbe

El paper **no dice que el contexto sea inútil**. Dice dos cosas distintas, y la diferencia gobierna el diseño de ArquiGraph:

| El paper | Consecuencia para ArquiGraph |
|---|---|
| Los **resúmenes de repositorio** no ayudan y cuestan | ArquiGraph **no es un overview precargado**. Ese patrón está refutado. |
| Las **prácticas no estándar** sí merecen especificarse | Servir hechos concretos y verificables, bajo demanda, es el uso que el paper avala. |
| Cualquier intento de mejorar el desempeño **debe evaluarse con rigor antes de desplegarse** | Es literalmente P7 y el criterio de kill de R1. |

La última fila es la más incómoda y la más útil: los propios autores concluyen que estas cosas hay que medirlas antes de creérselas. Este proyecto se somete a su propia regla.

### 2.4 Consecuencia directa para ArquiGraph

> **Si ArquiGraph inyecta contexto al inicio de cada sesión, la evidencia predice que empeorará el desempeño del agente y subirá el costo.**

Esto invalida el patrón "memoria como bloque de texto precargado" y obliga a un diseño de **recuperación bajo demanda** (el agente invoca una herramienta cuando la necesita) **con presupuesto de tokens acotado**.

Ver también: [Instruction Adherence in Coding Agent Configuration Files](https://arxiv.org/pdf/2605.10039), estudio factorial sobre variables de estructura de archivo, que refuerza que la longitud es un factor de degradación.

---

## 3. Dónde se gastan realmente los tokens

### 3.1 Las cuatro fugas principales

| # | Fuga | Mecanismo | Mitigación conocida |
|---|---|---|---|
| 1 | **Lectura de código** | Lecturas de archivo completo cuando bastaba una ventana dirigida. Es el mayor consumidor individual. | Grep + ventana acotada; techo por salida de herramienta (~2.000 tokens) |
| 2 | **Re-lectura post-compactación** | Al compactar se pierde un archivo ya leído o un mensaje de error; el agente lo vuelve a leer y **paga dos veces los mismos tokens** | Memoria externa persistente que sobreviva a la compactación |
| 3 | **Ciclos de reintento a contexto inflado** | Un fallo de test en el turno 40 no cuesta "un turno": cuesta un turno que ya arrastra 30.000+ tokens de entrada. Tres intentos fallidos = 3× ese costo. | Procedimientos verificados que eviten la exploración a ciegas |
| 4 | **Context rot** | La precisión decae conforme crece la entrada; los hechos enterrados a mitad del contexto se pierden ("lost in the middle"). La degradación se vuelve marcada al **70–80% de llenado**. | Compactación agresiva desde ~50% de utilización, no al 90% |

Fuentes: [Vantage — Hidden Cost Driver in Agentic Coding Sessions](https://www.vantage.sh/blog/agentic-coding-costs), [MindStudio — Context Rot in AI Coding Agents](https://www.mindstudio.ai/blog/context-rot-ai-coding-agents-how-to-prevent), [Sombra — Token Optimization for Agentic AI](https://sombrainc.com/blog/token-optimization).

### 3.2 La fuga #3 es la más cara y la menos atacada

Las fugas 1, 2 y 4 tienen mitigaciones conocidas y ya implementadas en los agentes comerciales. La #3 —**el costo compuesto de la exploración a ciegas**— es la que ninguna herramienta de memoria ataca hoy, y es donde la memoria procedural muestra evidencia de ahorro (§6).

### 3.3 Frustración medida en desarrolladores

- **66%** identifican como su mayor frustración las soluciones de IA "casi correctas, pero no del todo".
- **45%** reportan que **depurar el código de la IA tarda más que escribirlo a mano**.

Fuente: [The New Stack — Context is AI coding's real bottleneck in 2026](https://thenewstack.io/context-is-ai-codings-real-bottleneck-in-2026/).

**Lectura:** el dolor no es de velocidad de generación, es de **confiabilidad**. Una herramienta que genere más rápido no resuelve nada; una que reduzca la tasa de "casi correcto" sí.

### 3.4 El costo humano recurrente

El patrón descrito repetidamente: abrir una sesión nueva, pedir que extienda el módulo de autenticación, y tener que **explicar otra vez** la arquitectura de servicios, **aclarar otra vez** las convenciones de nombres, y **señalar otra vez** que la librería de validación compartida ya existe.

Causa estructural: los pesos del modelo están congelados, la ventana de contexto se reconstruye desde cero, y **la mayoría de las herramientas no escriben memoria entre sesiones por defecto**.

Fuente: [Inferensys — The Cost of Context Loss](https://inferensys.com/blog/ai-native-software-development-life-cycles-sdlc/the-cost-of-context-loss-in-ai-driven-development), [Augment Code — Why AI Agents Keep Asking the Same Questions](https://www.augmentcode.com/guides/why-ai-agents-repeat-questions).

---

## 4. Deriva arquitectónica y entropía agéntica

### 4.1 El modo de falla

Los agentes **optimizan para correctitud local mientras se alejan de la intención arquitectónica global**. Operan dentro de ventanas de contexto acotadas, logran correctitud funcional a nivel de módulo, y en el camino violan patrones de diseño sistémicos.

Síntomas documentados:

- Fronteras entre capas que se filtran
- Logging inconsistente
- Exposición accidental de datos
- Regresiones silenciosas de confiabilidad
- Dependencias en dirección prohibida

Fuentes: [Beyond the 'Diff': Agentic Entropy](https://arxiv.org/pdf/2604.16323), [techdebt.guru — AI Architecture Drift](https://techdebt.guru/ai-architecture-drift/).

### 4.2 Los dos modos de falla estructural

Según [The Spec Growth Engine](https://arxiv.org/pdf/2606.27045):

1. **Explosión de contexto** — el agente debe razonar sobre el repositorio entero de una vez, lo que degrada la calidad de salida.
2. **Deriva silenciosa spec-código** — el código evoluciona, la especificación no, y la divergencia permanece **invisible hasta que repararla es caro**.

### 4.3 Por qué la documentación sola no lo evita

> "Cuando la generación es rápida, solo sobreviven las convenciones expresadas explícitamente — el contexto por sí solo no previene la deriva arquitectónica, porque los agentes producen código funcional e inconsistente a menos que algo los sujete a las decisiones registradas."

La palabra clave es **sujete**. No basta con que la decisión esté escrita: hace falta un mecanismo que **verifique el diff contra la decisión**. Ese mecanismo puede ser determinista y por tanto costar cero tokens de LLM.

Fuente: [ai.gopubby — AGENTS.md vs Architecture Decision Records](https://ai.gopubby.com/agents-md-is-the-ew-architecture-decision-record-adr-3cfb6bdd6f2c).

---

## 5. Por qué las memorias existentes no lo resuelven

### 5.1 Panorama del estado del arte

| Sistema | Enfoque | Fortaleza | Límite |
|---|---|---|---|
| **Letta / MemGPT** | Edita bloques de texto y archivos | Simplicidad, control directo | No hay estructura consultable |
| **Mem0** | Vector store con pistas de entidades | Mayor comunidad; API `add`/`search` simple | Recuperación por chunks pierde en multi-hop; features de grafo tras muro de pago (Pro, $249/mes) |
| **Graphiti** | Hechos como relaciones con marca temporal | Razonamiento temporal | Orientado a conversación, no a código |
| **Cognee** | Pipeline ECL de extracción de entidades | 14 modos de recuperación; Apache 2.0 sin muro de pago; integraciones LangGraph y MCP | Genérico: no entiende AST ni semántica de código |
| **Graphify** | AST determinista con tree-sitter, 22 lenguajes | **0 tokens** de extracción; cada arista explicada y citable; sin vector store | Solo capa semántica; no recuerda decisiones ni procedimientos |

**Dato relevante:** para preguntas multi-hop (conectar hechos entre documentos), la **recuperación estructurada (Cognee, Graphiti) le gana por amplio margen a la recuperación por chunks (Mem0)** en corrección. Esto valida la apuesta por grafo sobre embeddings puros.

Fuentes: [Cognee — Knowledge Graph Memory Benchmarks](https://www.cognee.ai/blog/deep-dives/knowledge-graph-memory-benchmarks), [codepointer — Agent Memory Systems and Knowledge Graphs](https://codepointer.substack.com/p/agent-memory-systems-and-knowledge), [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify).

### 5.2 Las tres fallas transversales

#### Falla A — Recuperación sin ponderación de autoridad

Los servidores de memoria estándar almacenan y recuperan por **similitud semántica**. Funciona hasta que hay **memorias en conflicto**: una instrucción vieja que dice una cosa y una nueva que dice otra.

> Sin ponderación de autoridad, el agente recupera la que está semánticamente más cerca de la consulta, **no la que es más confiable**.

Esto es especialmente grave en código, donde las decisiones se supersede constantemente.

#### Falla B — El grafo se pudre y nadie lo detecta

El `GRAPH_REPORT.md` generado en este mismo repositorio lo admite explícitamente:

```
## Graph Freshness
- Built from commit: `817ddd36`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).
```

Es decir: **la detección de obsolescencia es manual**. El grafo actual tiene 21.311 nodos y 59.255 edges anclados a un commit; cualquier merge posterior lo desincroniza sin aviso.

Lo mismo aplica a la memoria en texto: la memoria integrada (`CLAUDE.md`, `.cursorrules`) tiene un techo práctico de ~200 líneas y **se queda obsoleta**.

#### Falla C — No hay medición de ahorro

Ninguna de las herramientas revisadas mide si le ahorró tokens al usuario. Se venden por capacidad ("recuerda todo"), no por resultado ("te costó 30% menos"). Es una oportunidad de diferenciación y, más importante, **la única forma de saber si ArquiGraph está funcionando o repitiendo el error del `AGENTS.md`**.

### 5.3 Saturación del mercado

Existen al menos **ocho proyectos distintos llamados "Engram"** en GitHub (`engram-memory/engram`, `syntax-syndicate/engram-agent-memory`, `thebtf/engram`, `Agentscreator/engram-memory`, `EngramMemory/engram-memory`, `Gentleman-Programming/engram`, `tstockham96/engram`, `tinqiao-oss/engramory`), con arquitecturas que van de SQLite+FTS5 a PostgreSQL a embeddings semánticos.

**Conclusión estratégica:** la capa de memoria episódica genérica está saturada y commoditizada. No hay ventaja defendible ahí.

---

## 6. Memoria procedural: la evidencia positiva

### 6.1 Qué es

Memoria **procedural** = destilar trayectorias de ejecución pasadas en procedimientos reutilizables ("cómo se hace X *en este repositorio*"), distinta de la memoria **episódica** ("qué pasó el martes") y de la **semántica** ("qué existe en el código").

### 6.2 La evidencia

| Trabajo | Mecanismo | Resultado medido |
|---|---|---|
| **Memp** | Destila trayectorias en instrucciones paso a paso + abstracciones tipo script | **−9 pasos** y **−685 tokens** por tarea |
| **ReMe** (Remember Me, Refine Me) | Reconocimiento de patrones de éxito, análisis de fallos, generación de insights comparativos | Experiencias estructuradas reutilizables |
| **Neural Procedural Memory** | Almacenamiento como *activation steering*: modulación a nivel de representación | Sin sobrecarga de tokens ni actualización de parámetros |
| **Skills evolucionadas** | Precarga de conocimiento procedural en el prompt | **−326k tokens (−62%)** en Claude; −48k (−16%) en Hermes, frente a skills escritas a mano |

> El hallazgo transversal: construir y recuperar memoria procedural permite **eliminar la exploración estéril y el ensayo-error**, lo que reduce sustancialmente tanto el número de pasos como el consumo de tokens.

Fuentes: [Remember Me, Refine Me (arXiv 2512.10696)](https://arxiv.org/html/2512.10696), [Managing Procedural Memory in LLM Agents (arXiv 2606.23127)](https://arxiv.org/html/2606.23127), [A Benchmark for Procedural Memory Retrieval (arXiv 2511.21730)](https://arxiv.org/pdf/2511.21730), [VentureBeat — How procedural memory can cut the cost of AI agents](https://venturebeat.com/ai/how-procedural-memory-can-cut-the-cost-and-complexity-of-ai-agents).

### 6.3 Por qué esto conecta con la fuga #3

La fuga más cara identificada en §3.1 es el **ciclo de reintento a contexto inflado**. La memoria procedural ataca exactamente eso: si el agente ya sabe que "para añadir un endpoint aquí hay que tocar estos 4 archivos en este orden y correr *este* test", no hay exploración a ciegas, no hay tres intentos fallidos a 30k tokens cada uno.

**Es la única capa con evidencia causal de ahorro, y es la que está vacía en producto.**

---

## 7. El hueco: las tres capas que nadie une

| Capa | Pregunta que responde | Tecnología | Estado del arte |
|---|---|---|---|
| **Semántica** | ¿Qué existe? (funciones, llamadas, herencia, imports) | AST determinista (tree-sitter) | ✅ **Resuelto** — Graphify: 0 tokens, 22 lenguajes, cada arista citable |
| **Episódica** | ¿Qué pasó? (decisiones, bugs, sesiones) | Vector store / grafo temporal | 🟡 **Medio resuelto y saturado** — engram (×8), mem0, Graphiti, Cognee |
| **Procedural** | **¿Cómo se hace *aquí*?** | Destilación de trayectorias verificadas | 🔴 **Vacío en producto** — solo investigación (§6) |

Y una capa transversal que **nadie tiene**:

| Capa | Función | Estado |
|---|---|---|
| **Guardián de invariantes** | Verificar el diff contra las decisiones registradas, de forma determinista | 🔴 Solo productos comerciales cerrados y parciales |

### 7.1 Formulación del hueco

> Existe una herramienta que sabe **qué hay** en el código (Graphify) y varias que recuerdan **qué pasó** (engram/mem0). No existe ninguna que recuerde **cómo se trabaja en este repositorio**, que **ancle ese conocimiento a nodos verificables del código** para que caduque solo, y que **verifique que el nuevo código no rompe las decisiones ya tomadas**.
>
> Ese es ArquiGraph.

---

## 8. Principios de diseño derivados

Cada principio está numerado y trazado a la sección que lo justifica. Son restricciones vinculantes, no sugerencias.

### P1 — Recuperación bajo demanda, nunca inyección permanente
*Deriva de §2.* La memoria se expone como **herramienta que el agente invoca**, no como bloque precargado en el prompt de sistema. Repetir el patrón `AGENTS.md` reproduce una degradación medida de −3% de éxito y +20% de costo.

### P2 — Presupuesto de tokens duro y auditable
*Deriva de §2, §3.* El recuperador tiene un techo explícito (p. ej. 2.000 tokens por invocación) y debe **justificar cada elemento que inyecta**. Sin techo, el sistema deriva hacia el `AGENTS.md` gordo por acumulación natural.

### P3 — Memoria anclada a nodos del grafo, no a texto libre
*Deriva de §5.2-B.* Cada memoria cuelga de uno o más nodos AST (función, clase, módulo). Si el nodo desaparece o cambia de firma, **la memoria se marca sospechosa automáticamente**. Esto convierte la obsolescencia de un problema manual en una propiedad del sistema.

### P4 — Ranking por autoridad + recencia + evidencia, no solo similitud
*Deriva de §5.2-A.* Ante memorias en conflicto debe ganar la más **confiable**, no la más **parecida**. Señales: quién la escribió (humano > agente), cuándo, y si hay evidencia de que funcionó.

### P5 — Solo se persiste lo verificado
*Deriva de §6.* Un procedimiento se guarda **únicamente si su trayectoria terminó en evidencia objetiva**: tests en verde, commit aplicado, PR mergeado. Guardar intentos fallidos como si fueran conocimiento es cómo se envenena la memoria.

### P6 — El guardián de invariantes es determinista
*Deriva de §4.3.* La validación del diff contra las reglas del grafo (capas permitidas, dependencias prohibidas, fronteras de módulo) se hace con recorrido de grafo, **sin llamar a un LLM**. Costo: 0 tokens. Esto es lo que "sujeta" al agente a las decisiones registradas.

### P7 — El sistema mide su propio ahorro
*Deriva de §5.2-C.* Métricas de primera clase: **tokens ahorrados por sesión**, **tasa de reuso de procedimientos**, **tasa de invalidación de memorias**. Sin esto no hay forma de distinguir entre "ArquiGraph funciona" y "ArquiGraph es un `AGENTS.md` más caro".

---

## 9. Anti-objetivos

Lo que ArquiGraph **no** debe ser, y por qué:

| Anti-objetivo | Razón |
|---|---|
| **Otro servidor MCP de memoria genérico** | Mercado saturado (§5.3: 8 proyectos "Engram" + mem0 + Cognee + Graphiti). Perderíamos en benchmarks contra equipos dedicados, sin ventaja defendible. |
| **Reimplementar el parseo AST** | Graphify ya lo resuelve con 22 lenguajes, determinista y a 0 tokens (§5.1). Construir encima, no al lado. |
| **Inyectar contexto al inicio de sesión** | Contradice directamente la evidencia de §2. Es el error que el proyecto existe para corregir. |
| **Optimizar por "recordar todo"** | El valor es recuperar **poco y correcto** (§2.3, §3.4). Volumen de memoria es una métrica de vanidad. |
| **Validación arquitectónica vía LLM** | Cara, no determinista, y no auditable. El recorrido de grafo da la misma respuesta a costo cero (§P6). |

---

## 10. Riesgos e hipótesis a validar

| # | Riesgo / Hipótesis | Cómo se falsea |
|---|---|---|
| R1 | **ArquiGraph reproduce la degradación de `AGENTS.md`** si la recuperación mete ruido | Benchmark A/B: agente con y sin ArquiGraph sobre el mismo conjunto de issues; medir éxito **y** costo. Si el éxito no sube o el costo sube >10%, el diseño está mal. |
| R2 | **El anclaje a nodos AST es demasiado frágil** — refactors masivos invalidarían toda la memoria de golpe | Medir tasa de invalidación por commit en un repo real. Si un refactor rutinario invalida >30% de memorias, hace falta anclaje a nivel de módulo además de función. |
| R3 | **La destilación de procedimientos cuesta más de lo que ahorra** | Contabilizar el costo de destilación contra el ahorro acumulado por reuso. Necesita un umbral mínimo de reuso para ser rentable. |
| R4 | **El agente no invoca la herramienta de recuperación** (problema conocido de los memory MCP) | Medir tasa de invocación. Si es baja, hace falta un disparador (hook de inicio de tarea) que no sea inyección de contexto. |
| R5 | **Los invariantes arquitectónicos son difíciles de expresar** en un formato que el grafo pueda verificar | Prototipar 5 invariantes reales de este repo antes de comprometerse con el formato. |
| R6 | ~~**No se pueden contabilizar los tokens.**~~ | ✅ **RESUELTO (2026-09-01).** Claude Code expone `usage`, desglose de caché, `total_cost_usd`, `num_turns` e `iterations[]` vía `-p --output-format json`. Ver [FINDINGS-token-accounting.md](./FINDINGS-token-accounting.md). |
| R7 | **El banco cuesta dinero real.** 120–180 ejecuciones a coste no trivial por tarea. | Fijar el modelo en Sonnet y correr un **piloto de coste** (3 tareas × 3 repeticiones) antes de dimensionar el corpus definitivo. |

**R1 es el riesgo existencial del proyecto.** Debe medirse antes de escribir la primera línea del recuperador.

**R6 era previo a R1** y quedó resuelto el primer día. La medición aportó además una confirmación empírica de §3: en una invocación trivial, **el 99,97 % de los tokens movidos fueron contexto, no trabajo**. El coste vive en lo que se arrastra, no en lo que se pide.

---

## 11. Fuentes

### Estudios primarios

- Gloaguen et al. (ETH Zurich, feb 2026) — [*Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?*](https://arxiv.org/pdf/2602.11988)
- [*Instruction Adherence in Coding Agent Configuration Files: A Factorial Study of Four File-Structure Variables*](https://arxiv.org/pdf/2605.10039)
- [*Remember Me, Refine Me: A Dynamic Procedural Memory Framework for Experience-Driven Agent Evolution*](https://arxiv.org/html/2512.10696)
- [*Managing Procedural Memory in LLM Agents: Control, Adaptation, and Evaluation*](https://arxiv.org/html/2606.23127)
- [*A Benchmark for Procedural Memory Retrieval in Language Agents*](https://arxiv.org/pdf/2511.21730)
- [*Neural Procedural Memory: Empowering LLM Agents with Implicit Activation Steering*](https://arxiv.org/html/2606.29824)
- [*Beyond the 'Diff': Addressing Agentic Entropy in Agentic Software Development*](https://arxiv.org/pdf/2604.16323)
- [*The Spec Growth Engine: Spec-Anchored, Code-Coupled, Drift-Enforced Architecture*](https://arxiv.org/pdf/2606.27045)
- [*Toward Efficient Agents: Memory, Tool Learning, and Planning*](https://arxiv.org/pdf/2601.14192)
- [*Always-On Agents: A Survey of Persistent Memory, State, and Governance in LLM Agents*](https://arxiv.org/pdf/2606.30306)

### Análisis de industria

- [The New Stack — *Context is AI coding's real bottleneck in 2026*](https://thenewstack.io/context-is-ai-codings-real-bottleneck-in-2026/)
- [Vantage — *The Hidden Cost Driver in Agentic Coding Sessions in 2026*](https://www.vantage.sh/blog/agentic-coding-costs)
- [MindStudio — *Context Rot in AI Coding Agents*](https://www.mindstudio.ai/blog/context-rot-ai-coding-agents-how-to-prevent)
- [Sombra — *Token Optimization for Agentic AI*](https://sombrainc.com/blog/token-optimization)
- [Inferensys — *The Cost of Context Loss in AI-Driven Development*](https://inferensys.com/blog/ai-native-software-development-life-cycles-sdlc/the-cost-of-context-loss-in-ai-driven-development)
- [Augment Code — *Why AI Agents Keep Asking the Same Questions*](https://www.augmentcode.com/guides/why-ai-agents-repeat-questions)
- [VentureBeat — *How procedural memory can cut the cost and complexity of AI agents*](https://venturebeat.com/ai/how-procedural-memory-can-cut-the-cost-and-complexity-of-ai-agents)
- [MarkTechPost — cobertura del estudio de ETH Zurich](https://www.marktechpost.com/2026/02/25/new-eth-zurich-study-proves-your-ai-coding-agents-are-failing-because-your-agents-md-files-are-too-detailed/)
- [techdebt.guru — *AI Architecture Drift: How AI Agents Erode Your Codebase*](https://techdebt.guru/ai-architecture-drift/)
- [ai.gopubby — *AGENTS.md vs Architecture Decision Records*](https://ai.gopubby.com/agents-md-is-the-ew-architecture-decision-record-adr-3cfb6bdd6f2c)

### Estado del arte / herramientas

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — grafo de conocimiento de código por AST determinista
- [Cognee — *AI Agent Memory Benchmarks: Cognee vs. Mem0, Graphiti, LightRAG*](https://www.cognee.ai/blog/deep-dives/knowledge-graph-memory-benchmarks)
- [codepointer — *Agent Memory Systems and Knowledge Graphs: Letta, Mem0, Graphiti, Cognee*](https://codepointer.substack.com/p/agent-memory-systems-and-knowledge)
- [Graphlit — *AI Agent Memory Frameworks in 2026: Memory vs. Context*](https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks)
- [Vectorize — *Mem0 vs Cognee: AI Agent Memory Compared (2026)*](https://vectorize.io/articles/mem0-vs-cognee)

### Interna

- `graphify-out/GRAPH_REPORT.md` — grafo del repositorio: 21.311 nodos, 59.255 edges, 932 comunidades; construido desde el commit `817ddd36` (2026-08-21); 94% EXTRACTED / 6% INFERRED; costo de tokens: 0.

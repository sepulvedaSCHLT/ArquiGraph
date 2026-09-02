# ArquiGraph

**Un arquitecto de software persistente para agentes de programación.**

Un grafo determinista del código, una memoria anclada a él que caduca sola, y un guardián que impide romper las decisiones ya tomadas.

> ⚠️ **Estado: Fase 0.** En construcción. Este README no afirma resultados que aún no se han medido. Las cifras aparecerán aquí cuando el banco de medición las produzca, con el harness público para que cualquiera las reproduzca.

---

## El problema

Abres una sesión nueva con tu agente. Le pides que extienda el módulo de autenticación. Y vuelves a explicarle la arquitectura, vuelves a aclarar las convenciones, y vuelves a señalarle que la librería de validación compartida ya existe.

La respuesta habitual es escribir un `AGENTS.md` más completo. **La evidencia dice que eso empeora las cosas.**

Un estudio de ETH Zurich (feb 2026) midió agentes de codificación sobre cientos de issues reales de GitHub:

| Condición | Tasa de éxito | Coste |
|---|---|---|
| `AGENTS.md` generado por LLM | **−3 %** | **+20 %** |
| `AGENTS.md` escrito por humano | +4 % | +19 % |

La causa es contraintuitiva: **el agente obedece bien**. Por eso ejecuta pasos correctos en abstracto e innecesarios para la tarea concreta.

El problema no es que le falte documentación. Es que le sobra contexto irrelevante.

---

## El enfoque

ArquiGraph no precarga conocimiento. Lo **sirve bajo demanda, con presupuesto y con fecha de caducidad**.

### Buscar frente a navegar

Sin mapa, encontrar dónde vive un bug cuesta esto:

```
grep "token"  →  47 coincidencias
  leer auth/service.py     (~4.000 tokens)   no era
  leer auth/middleware.py  (~3.000 tokens)   no era
  leer api/session.py      (~5.000 tokens)   tampoco
  leer core/security.py    (~6.000 tokens)   aquí estaba
```

Y esos 18.000 tokens no se pagan una vez: quedan en el contexto y se recobran **en cada turno posterior de la sesión**.

Con mapa:

```
arqui trace --symbol refresh_token
  → core.security.TokenService.refresh    core/security.py:88
    ← auth.service.renew                  auth/service.py:142
    ← api.session.refresh                 api/session.py:31
```

~200 tokens, con rutas citables. El grafo se construye con **0 tokens de LLM**: extracción AST determinista y local.

Esto no elimina el gasto. Cambia la **relación señal/ruido**.

### Las cuatro capas

| Capa | Responde | Estado |
|---|---|---|
| **Semántica** | ¿Qué existe? — grafo AST determinista | Fase 0 |
| **Episódica** | ¿Qué se decidió? — memoria anclada a nodos | Fase 1 |
| **Procedural** | ¿Cómo se hace *aquí*? — solo lo verificado | Fase 3 |
| **Normativa** | ¿Qué no se puede romper? — invariantes | Fase 2 |

Las tres últimas **cuelgan de nodos del grafo**. Cuando el código cambia, el ancla cambia de hash y el conocimiento colgado se marca sospechoso solo. La obsolescencia deja de ser un problema operativo y pasa a ser una propiedad del sistema.

---

## Principios

| | |
|---|---|
| **P1** | Recuperación bajo demanda. Nunca inyección en el prompt de sistema. |
| **P2** | Presupuesto de tokens duro y auditable en toda salida. |
| **P3** | Memoria anclada al grafo, no a texto libre. |
| **P4** | Ranking por autoridad, no por similitud semántica. |
| **P5** | Solo se persiste lo verificado: tests en verde o commit aplicado. |
| **P6** | El guardián de invariantes es determinista. Cero tokens de LLM. |
| **P7** | El sistema mide su propio ahorro, con criterio de kill explícito. |

---

## Honestidad metodológica

Este proyecto puede fallar, y el diseño dice cuándo:

> Si el modo con ArquiGraph **no mejora** la tasa de éxito y **sube el coste más de un 10 %** frente al baseline, el recuperador está mal diseñado y se rehace antes de construir nada encima.

El banco A/B corre sobre repositorios OSS públicos, en Docker, con configuración aislada y versionada. **Cualquiera puede clonar el repo y reproducir las cifras.**

---

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/RESEARCH.md`](docs/RESEARCH.md) | Evidencia que fundamenta el diseño, con riesgos falsables |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arquitectura completa |
| [`docs/PHASE-0.md`](docs/PHASE-0.md) | Procedimiento de arranque |
| [`docs/SPEC-FASE-0.md`](docs/SPEC-FASE-0.md) | Esquemas y contratos para implementar |
| [`docs/adr/`](docs/adr/) | Decisiones de arquitectura |
| [`docs/FINDINGS-token-accounting.md`](docs/FINDINGS-token-accounting.md) | Cómo se miden los tokens (R6) |
| [`docs/FINDINGS-agent-hooks.md`](docs/FINDINGS-agent-hooks.md) | Captura de trayectorias |

---

## Licencia

[Apache 2.0](LICENSE) — Copyright 2026 Alfonso Schultz. Ver [ADR-007](docs/adr/ADR-007-licencia.md) para el razonamiento.

Construido con [`tree-sitter`](https://tree-sitter.github.io/) (MIT). Sin código de terceros en el árbol.

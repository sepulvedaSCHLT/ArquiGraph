# ADR-008 — Tres niveles de resolución para las aristas

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [ARCHITECTURE.md §3.1, §3.3](../ARCHITECTURE.md) · [RESEARCH.md §3.3](../RESEARCH.md) · [ADR-001](./ADR-001-grafo-propio.md)

## Contexto

La regla del proyecto es tajante: **lo que no se extrae del AST se marca `AMBIGUOUS` y no se afirma**. Al escribir el parser aparece la pregunta incómoda de qué significa exactamente "extraer" en un lenguaje dinámico.

```python
from app.services import auth as a

def login(user):
    return a.verify(user)
```

El alias `a` es resoluble con certeza leyendo el `import` — está en el AST. Pero esto no lo es:

```python
def guardar(self, pedido):
    return self.repo.save(pedido)   # ¿que es self.repo?
```

Las dos posturas extremas fallan:

- **Resolver todo y afirmarlo.** El grafo miente, y una ruta falsa citada con confianza produce el "casi correcto, pero no del todo" que el 66% de los desarrolladores señala como su mayor frustración ([RESEARCH.md §3.3](../RESEARCH.md)).
- **No resolver nada dudoso.** `arqui trace` casi no encuentra nada, el mapa pierde su utilidad, y el ahorro descrito en [ARCHITECTURE.md §2.1](../ARCHITECTURE.md) no se materializa.

## Decisión

Tres niveles, con `confidence` numérica y reglas explícitas por caso.

### `EXTRACTED` — confidence 1.0

El destino se deduce del AST **sin suposiciones**. Si el código se ejecuta, la arista es cierta.

| Caso | Ejemplo |
|---|---|
| Llamada a símbolo del mismo módulo | `def login(): ...` y luego `login()` |
| Import explícito | `from app.auth import verify` → `verify()` |
| Import con alias | `import app.auth as a` → `a.verify()` |
| Herencia con base resoluble | `class X(Base)` con `Base` importado |
| `IMPORTS` | siempre |
| `DEFINES` | siempre (contención sintáctica) |

### `INFERRED` — confidence 0.3 a 0.8

El destino es **probable** y la evidencia está en el AST, pero depende de una suposición razonable. Se afirma con reserva y **el recuperador lo degrada en el ranking** (P4).

| Caso | confidence |
|---|---|
| `self.metodo()` con el método en la clase o una base conocida | 0.8 |
| Método sobre parámetro con anotación de tipo | 0.7 |
| Método sobre atributo anotado en `__init__` | 0.6 |
| Nombre que coincide con **un único** símbolo del repositorio | 0.4 |

### `AMBIGUOUS` — no se afirma el destino

Se registra que **hay una llamada** y su evidencia (archivo y línea), pero `dst` guarda el texto literal sin resolver.

| Caso |
|---|
| `from x import *` |
| Método sobre variable sin tipo conocido |
| Nombre que coincide con varios símbolos |
| `getattr`, despacho dinámico, `eval` |

**Estas aristas sí se almacenan.** Que `arqui trace` diga *"hay una llamada aquí que no pude resolver"* es información útil y honesta; borrarla haría creer al agente que el mapa está completo cuando no lo está.

## La regla que no se rompe

> La diferencia entre `EXTRACTED` e `INFERRED` es **cuánta certeza da el AST**, nunca si inventamos algo.

Ninguna arista se deriva de un LLM, de embeddings, ni de heurísticas de nombres sin respaldo sintáctico. `confidence` mide certeza de resolución, no verosimilitud estadística.

Corolario para el recuperador: **una arista `AMBIGUOUS` nunca se sirve como hecho.** Puede presentarse como llamada sin resolver, con esa etiqueta visible.

## Consecuencias

**Positivas**
- El grafo es útil sin mentir: resuelve la mayoría de los casos reales y declara los que no.
- `confidence` da al ranking (P4) una señal más, ya prevista en el esquema.
- La proporción `EXTRACTED / INFERRED / AMBIGUOUS` es un **indicador directo de calidad del parser**. Se expone en `arqui stats` y es un objetivo medible de las fases siguientes.

**Negativas**
- Más complejidad en el parser que un enfoque binario.
- Los umbrales de `confidence` (0.8, 0.7, 0.6, 0.4) son un juicio inicial, no una medición. Se calibran con el banco, igual que los pesos del ranking.
- Un `INFERRED` erróneo puede desorientar al agente. Mitigación: el ranking lo degrada, y la evidencia (archivo y línea) siempre acompaña, de modo que el error es verificable en un vistazo.

## Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| Resolver todo como `EXTRACTED` | El grafo miente con confianza. Es el modo de falla más caro. |
| Marcar `AMBIGUOUS` todo lo que no sea llamada directa | Descarta los imports con alias, que son deterministas y muy frecuentes. El grafo se vuelve casi inútil. |
| Inferencia de tipos completa (estilo mypy) | Meses de trabajo, y arrastra la complejidad de un verificador de tipos a un proyecto cuyo diferenciador está en otra parte. Reconsiderar si la medición demuestra que la resolución es el cuello de botella. |

## A validar

Medir sobre repositorios reales el reparto `EXTRACTED / INFERRED / AMBIGUOUS`.

> **Umbral orientativo:** si menos del **70%** de las aristas `CALLS` resultan `EXTRACTED` en código Python idiomático, la resolución es demasiado pobre para que `arqui trace` cumpla su función, y hay que reforzar el resolvedor antes de seguir.

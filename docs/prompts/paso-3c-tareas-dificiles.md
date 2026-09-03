# Prompt — Cuatro tareas difíciles para el banco

> Ampliación del corpus, derivada del piloto: [FINDINGS-piloto.md](../FINDINGS-piloto.md).
> Gobernado por [ADR-010](../adr/ADR-010-corpus-sintetico.md).
>
> **Alcance: cuatro tareas nuevas sobre el corpus existente.**
> No se toca `bench/corpus/`, ni las ocho tareas ya congeladas, ni `arquigraph/`.

---

## Por qué estas cuatro

El piloto midió **100% de éxito** en modo A sobre T001 y T007, y T007 —diseñada como la más difícil— salió **la más barata y rápida**, con una varianza del 1%.

La causa está en su enunciado:

> *"Pasa en cualquier calculo con porcentaje, y siempre en la misma direccion."*

Esa frase le dice al agente que hay **una causa común en código compartido**. Estrecha la búsqueda en vez de ampliarla.

## La regla que gobierna estas cuatro tareas

> **Síntoma local y concreto. Causa lejana. Ninguna pista de que lo esté.**

| Prohibido | Por qué |
|---|---|
| "pasa en todos los cálculos de X" | Anuncia causa común en código compartido |
| "siempre en la misma dirección" | Anuncia un único punto de fallo |
| "desde que se toca el descuento" | Anuncia la capa |
| Mencionar dos o más síntomas relacionados | El patrón resuelve la búsqueda |

| Obligatorio | |
|---|---|
| **Un solo** síntoma observable | Como lo reportaría un usuario que solo vio una cosa rara |
| Valor esperado y valor observado | Números concretos |
| La causa a **3 o más saltos** del síntoma | Es lo que hace que navegar pague |
| Nada de nombres de archivo, módulo o función | Igual que las ocho existentes |

---

## Las cuatro tareas: T009 a T012

Mismo formato que las existentes (`TXXX.json` + `TXXX.bug.patch`), mismo verificador.

| Tarea | Distancia síntoma → causa | Naturaleza del bug |
|---|---|---|
| **T009** | 3 saltos, api → dominio → infraestructura | El síntoma aparece en la respuesta de la API; la causa está en cómo el almacén ordena o filtra |
| **T010** | 3 saltos, cruzando a `compartido` | Un solo síntoma en un solo endpoint, causado por una utilidad compartida — **pero sin decir que afecta a más sitios** |
| **T011** | 3+ saltos, con un intermediario que enmascara | Una capa intermedia transforma el valor y hace que el síntoma no se parezca a la causa |
| **T012** | Condición de frontera lejana | El síntoma solo aparece con un dato concreto; la causa es una comparación en otra capa |

### Contraste con T007, para que se vea la diferencia

| T007 (fácil, ya congelada) | T010 (nueva, difícil) |
|---|---|
| "El IVA de 33.33 sale 6.99; el 5% de 10.15 sale 0.50; el IVA de portes de 4.95 sale 1.03. **Pasa en cualquier cálculo con porcentaje, y siempre en la misma dirección**." | "Un pedido de 3 unidades a 12.45 con envío estándar totaliza 47.86 y debería totalizar 47.87." |

La segunda tiene la causa en el mismo sitio que la primera, pero **no lo insinúa**. El agente tiene que llegar solo.

---

## Restricciones

1. **No modificar `bench/corpus/tienda/`.** Los bugs se inyectan por parche, como los existentes.
2. **No tocar T001–T008.** Están congeladas.
3. Cada tarea debe discriminar: `bench/verificar_tareas.py` debe seguir saliendo con código 0, ahora con 12.
4. Sin dependencias nuevas.
5. **No escribir el enunciado mirando la solución.** Primero el síntoma observable, después el bug que lo produce.

## Criterios de aceptación

- [ ] Cuatro tareas nuevas T009–T012 con su parche
- [ ] **Ningún enunciado menciona archivo, módulo ni función**
- [ ] **Ningún enunciado describe más de un síntoma**
- [ ] **Ningún enunciado insinúa que la causa sea común, compartida o de una capa concreta**
- [ ] Todos dan valor esperado y observado
- [ ] `hint_files` documenta la causa real, a 3+ saltos del punto donde se observa
- [ ] `python bench/verificar_tareas.py` → **12/12 discriminan**, código 0
- [ ] `cd bench/corpus/tienda && python -m pytest -q` sigue pasando en el estado sano
- [ ] `uv run pytest -q` → 188 sigue verde
- [ ] `uv run ruff check .` y `format --check` limpios

## Verificación

```bash
python bench/verificar_tareas.py
grep -h '"problem_statement"' bench/tasks/T0[01][0-9]*.json
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

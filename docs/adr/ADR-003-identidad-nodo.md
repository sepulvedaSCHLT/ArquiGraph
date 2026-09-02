# ADR-003 — Identidad de nodo y disparadores de invalidación

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [RESEARCH.md §5.2-B, P3, R2](../RESEARCH.md) · [ARCHITECTURE.md §3.4, §3.5](../ARCHITECTURE.md)

## Contexto

P3 exige que la memoria cuelgue de nodos del grafo para que caduque sola cuando el código cambia. Eso convierte la identidad del nodo en la decisión más delicada del sistema:

- Si la identidad es **demasiado volátil** (líneas, offsets), cualquier edición trivial invalida toda la memoria del archivo y el sistema es inútil. Este es el riesgo **R2**.
- Si es **demasiado estable**, no detectamos cambios reales y servimos memoria obsoleta — que es la falla §5.2-B que venimos a corregir.

## Decisión

### Identidad

```
node_id = blake2b(path + "::" + qualified_name + "::" + kind)[:16]
```

Explícitamente **no** entran en la identidad: número de línea, offset de bytes, contenido del cuerpo, ni orden de aparición.

### Dos disparadores separados

| Hash | Cubre | Al cambiar |
|---|---|---|
| `signature_hash` | nombre, parámetros, tipos, valor de retorno | **Fuerte** — el contrato cambió → memorias ancladas pasan a `suspect` |
| `body_hash` | cuerpo normalizado (sin comentarios ni espacios) | **Suave** — la implementación cambió → `Procedure` anclados pasan a `suspect`; las `Memory` de tipo `decision` sobreviven |

La separación es deliberada: una decisión arquitectónica sigue siendo válida aunque el cuerpo cambie; un procedimiento paso a paso, no.

### Migración de anclas ante refactors

Al reparsear, se comparan los nodos desaparecidos contra los nuevos:

```
nodo desaparecido D, nodo nuevo N
si body_hash(D) == body_hash(N) y node_id(D) != node_id(N):
    → es un movimiento o renombrado
    → MIGRAR las anclas de D a N (no invalidar)
```

Esta regla es la mitigación directa de R2 y no es opcional: sin ella, un refactor rutinario borra la memoria acumulada del proyecto.

### Estado `suspect`

Una memoria o procedimiento en `suspect` **nunca se sirve** en un `recall`. Solo vuelve a `active` por reconfirmación explícita (humana, o de un agente con evidencia nueva).

Servir conocimiento dudoso es peor que no servir nada: produce el "casi correcto, pero no del todo" que el 66% de los desarrolladores señala como su mayor frustración (§3.3).

## Consecuencias

**Positivas**
- La obsolescencia deja de ser un problema operativo manual (§5.2-B) y pasa a ser una propiedad del sistema.
- La granularidad de la invalidación es proporcional al tipo de cambio.
- Los refactors no destruyen la memoria acumulada.

**Negativas**
- Renombrar **y** modificar el cuerpo a la vez rompe la migración: se pierde el ancla. Aceptado — es un cambio genuino de identidad, y la invalidación es la respuesta segura.
- `qualified_name` en lenguajes muy dinámicos puede ser ambiguo. Se marca `AMBIGUOUS` y no se usa como ancla.
- El coste del `body_hash` normalizado se paga en cada reparseo. Acotado: solo archivos del diff.

## A validar (R2)

Medir en el banco la **tasa de invalidación por commit** sobre un repositorio real.

> **Umbral de alarma:** si un refactor rutinario invalida más del **30%** de las memorias, el anclaje a nivel de función es demasiado fino y hay que añadir anclaje a nivel de módulo como respaldo.

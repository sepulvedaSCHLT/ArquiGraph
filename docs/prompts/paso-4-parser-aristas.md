# Prompt — Paso 4: extracción de aristas (solo lo que el AST resuelve)

> Especificación ejecutable para `arquigraph/core/parser/edges.py`.
> Paso 4 de [SPEC-FASE-0 §7](../SPEC-FASE-0.md), gobernado por [ADR-008](../adr/ADR-008-resolucion-de-aristas.md).
>
> **Alcance: solo aristas `EXTRACTED` y `AMBIGUOUS`.**
> Ninguna arista `INFERRED` sale de este paso. Las suposiciones (`self.metodo()`,
> parámetros anotados, atributos) son el paso 4b y **no se implementan aquí**.

---

## Contexto que hay que leer antes

| Archivo | Qué aporta |
|---|---|
| `arquigraph/core/parser/python.py` | `ParsedNode`, `parse_module`. Se consume, no se modifica. |
| `arquigraph/core/identity/hashing.py` | `node_id`, `normalize_path` |
| `docs/adr/ADR-008-resolucion-de-aristas.md` | La política que este módulo implementa |
| `docs/SPEC-FASE-0.md` §1 | Esquema de la tabla `edges` |

---

## Objetivo

```python
# arquigraph/core/parser/edges.py

@dataclass(frozen=True)
class ParsedEdge:
    src: str            # node_id del nodo que contiene la referencia
    dst_name: str       # nombre cualificado del destino, TAL COMO SE RESOLVIO
    kind: str           # DEFINES | IMPORTS | INHERITS | CALLS
    evidence_path: str
    evidence_line: int
    confidence: float   # 1.0 (EXTRACTED) | 0.0 (AMBIGUOUS)
    resolution: str     # EXTRACTED | AMBIGUOUS


def extract_edges(source: str, path: str, nodes: list[ParsedNode]) -> list[ParsedEdge]:
    """Extrae las aristas de un archivo Python ya parseado en nodos.

    Raises:
        SyntaxError: si el archivo no es Python valido.
    """
```

### `dst_name` es un nombre, no un `node_id`

El parser ve **un solo archivo**: no puede conocer los `node_id` de otros módulos. Emite el mejor nombre cualificado que consigue resolver, y el paso 5 lo traduce a `node_id` cuando exista un nodo con ese `qualified_name`.

`src` sí es un `node_id`, porque el nodo contenedor está en este mismo archivo.

---

## Tabla de símbolos del módulo

Se construye **antes** de recorrer el cuerpo, a partir de los `import` de nivel de módulo.

| Sentencia | Enlaza | A |
|---|---|---|
| `import app.auth` | `app` | `app` |
| `import app.auth as a` | `a` | `app.auth` |
| `from app.auth import verify` | `verify` | `app.auth.verify` |
| `from app.auth import verify as v` | `v` | `app.auth.verify` |
| `from . import util` | `util` | `<paquete>.util` |
| `from .service import f` | `f` | `<paquete>.service.f` |
| `from ..core import g` | `g` | `<paquete padre>.core.g` |
| `from app.auth import *` | — | activa la marca de estrella |

El `<paquete>` sale del `path`: para `app/auth/service.py` es `app.auth`; para `app/auth/__init__.py` es `app.auth`. Cada nivel adicional de punto sube un paquete.

**Definiciones locales:** las clases y funciones definidas a nivel de módulo entran también en la tabla, y **tienen prioridad** sobre los imports (es lo que Python hace: la última asignación al nombre gana, y una definición local posterior sombrea el import).

**Marca de estrella:** si el módulo tiene un `from x import *`, cualquier nombre que no esté en la tabla pasa a `AMBIGUOUS`. Nunca se adivina de dónde viene.

---

## Las cuatro clases de arista

### `DEFINES` — contención sintáctica

Siempre `EXTRACTED`, `confidence = 1.0`.

| De | A |
|---|---|
| módulo | cada clase y función de nivel superior |
| clase | cada método y clase anidada |

`evidence_line` = línea de la definición contenida.

### `IMPORTS` — del módulo a lo importado

Siempre `EXTRACTED`, `confidence = 1.0`. `src` es el nodo `module`.

`dst_name` es el destino resuelto de la tabla de símbolos. Para `import x.y` el destino es `x.y`; para `from a import b`, `a.b`.

Un `from x import *` genera **una** arista `IMPORTS` a `x`, marcada `AMBIGUOUS` — sabemos de dónde importa, no qué.

### `INHERITS` — de la clase a su base

- Base resoluble por la tabla de símbolos o local → `EXTRACTED`, 1.0
- Base no resoluble (o hay marca de estrella) → `AMBIGUOUS`, 0.0, con `dst_name` = el texto literal (`ast.unparse` de la expresión base)

Una clase con varias bases genera una arista por base.

### `CALLS` — el caso que importa

Solo se resuelven dos formas. Todo lo demás es `AMBIGUOUS`.

| Forma | Condición | Resultado |
|---|---|---|
| `f(...)` | `f` está en la tabla de símbolos | `EXTRACTED` 1.0, `dst_name` = destino resuelto |
| `f(...)` | `f` **no** está en la tabla | `AMBIGUOUS` 0.0, `dst_name = "f"` |
| `a.b(...)` | `a` está en la tabla | `EXTRACTED` 1.0, `dst_name` = `<resuelto a>.b` |
| `a.b.c(...)` | `a` está en la tabla | `EXTRACTED` 1.0, `dst_name` = `<resuelto a>.b.c` |
| `a.b(...)` | `a` **no** está en la tabla | `AMBIGUOUS` 0.0, `dst_name` = `ast.unparse(func)` |
| `self.m(...)` | siempre en este paso | `AMBIGUOUS` 0.0 — **es el paso 4b** |
| `obj[0].m(...)`, `f()(...)`, lambdas | siempre | `AMBIGUOUS` 0.0 |

**`src` de una llamada** es el `node_id` del nodo que la contiene: el método, la función, o el módulo si está a nivel superior. Una llamada dentro de una función anidada se atribuye a la función padre indexada, no a la anidada (que no tiene nodo).

**Los builtins no se tratan aparte.** `len(x)` produce `AMBIGUOUS` con `dst_name = "len"`. Filtrarlos es una decisión del recuperador, no del parser: aquí no se descarta información.

---

## Duplicados — obligatorio

La clave primaria de `edges` es `(src, dst, kind, evidence_path, evidence_line)`. Estas líneas colisionan:

```python
resultado = calcular(a) + calcular(b)        # dos CALLS identicas
valores = [procesar(x) for x in items]       # dentro de un bucle
if verificar(a) or verificar(b): ...         # dos veces en la misma linea
```

`extract_edges` **debe devolver la lista deduplicada** por esa tupla de cinco campos. Es el mismo fallo que apareció en el paso 3 con `@overload`, y aquí es más frecuente.

---

## Restricciones

1. **Ninguna arista `INFERRED`.** Si no se resuelve con certeza, es `AMBIGUOUS`. El paso 4b promoverá algunas después.
2. **No resolver a través de archivos.** El parser ve un archivo. Que `dst_name` corresponda a un nodo real lo decide el paso 5.
3. **No modificar** `core/parser/python.py`, `core/identity/` ni `core/graph/`.
4. **Sin dependencias nuevas.** Solo librería estándar (ADR-009).
5. **Sin escribir en la base de datos.** `extract_edges` es pura.
6. **Sin `print`.**

---

## Criterios de aceptación

Tests en `tests/test_parser_edges.py`.

### DEFINES

- [ ] Módulo con una función y una clase → dos aristas `DEFINES` desde el módulo
- [ ] Clase con dos métodos → dos `DEFINES` desde la clase
- [ ] Clase anidada → `DEFINES` de la externa a la interna

### IMPORTS

- [ ] `import app.auth` → `IMPORTS` a `app.auth`
- [ ] `from app.auth import verify` → `IMPORTS` a `app.auth.verify`
- [ ] `from . import util` en `app/auth/service.py` → `app.auth.util`
- [ ] `from ..core import g` en `app/auth/service.py` → `app.core.g`
- [ ] `from x import *` → una arista `AMBIGUOUS` a `x`

### INHERITS

- [ ] `class A(Base)` con `Base` importado → `EXTRACTED` al nombre cualificado
- [ ] `class A(Base)` con `Base` definido en el mismo archivo → `EXTRACTED`
- [ ] `class A(desconocido.Base)` → `AMBIGUOUS`
- [ ] `class A(B, C)` → dos aristas

### CALLS

- [ ] Llamada a función del mismo módulo → `EXTRACTED`
- [ ] Llamada vía `from a import b` → `EXTRACTED` a `a.b`
- [ ] Llamada vía `import a.b as c` → `c.f()` da `EXTRACTED` a `a.b.f`
- [ ] `a.b.c()` con `a` importado → `EXTRACTED` con la cadena completa
- [ ] Nombre no resoluble → `AMBIGUOUS` con el literal
- [ ] `self.m()` → `AMBIGUOUS` (paso 4b lo promoverá)
- [ ] Con `from x import *`, un nombre desconocido → `AMBIGUOUS`, nunca resuelto
- [ ] `len(x)` → `AMBIGUOUS`, no se descarta

### Atribución y duplicados

- [ ] Llamada dentro de un método → `src` es el `node_id` del método
- [ ] Llamada a nivel de módulo → `src` es el `node_id` del módulo
- [ ] Llamada dentro de una función anidada → `src` es la función padre indexada
- [ ] `f(a) + f(b)` en una línea → **una sola** arista tras deduplicar
- [ ] Ninguna arista tiene `resolution == "INFERRED"` en este paso

### Evidencia

- [ ] Toda arista tiene `evidence_path` y `evidence_line` correctos
- [ ] Dos llamadas al mismo destino en líneas distintas → dos aristas

---

## Verificación

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Los 86 tests existentes deben seguir pasando.

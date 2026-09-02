# Prompt — Paso 3: extracción de nodos

> Especificación ejecutable para implementar `arquigraph/core/parser/python.py`.
> Corresponde al paso 3 de [SPEC-FASE-0 §7](../SPEC-FASE-0.md).
> **Alcance: solo nodos. Las aristas son el paso 4 y no se tocan aquí.**

---

## Contexto que hay que leer antes

| Archivo | Qué aporta |
|---|---|
| `arquigraph/core/identity/hashing.py` | `Signature`, `Parameter`, `node_id`, `signature_hash`, `body_hash`. **Se usan tal cual, no se reimplementan.** |
| `docs/SPEC-FASE-0.md` §1 y §2 | Esquema de la tabla `nodes` y reglas de identidad |
| `docs/adr/ADR-009-parser-python-ast.md` | Por qué se usa `ast` y no `tree-sitter` |

---

## Objetivo

Un módulo que convierte un archivo `.py` en una lista de nodos listos para insertar en la tabla `nodes`.

```python
# arquigraph/core/parser/python.py

@dataclass(frozen=True)
class ParsedNode:
    node_id: str
    kind: str              # module | class | function | method
    qualified_name: str
    path: str              # relativa al repo, separador "/"
    signature_hash: str
    body_hash: str
    start_line: int        # 1-based, inclusive
    end_line: int          # 1-based, inclusive


def parse_module(source: str, path: str) -> list[ParsedNode]:
    """Extrae los nodos de un archivo Python.

    Raises:
        SyntaxError: si el archivo no es Python valido para este interprete.
    """
```

---

## Reglas de `qualified_name`

### Del path al módulo

| Path | Módulo |
|---|---|
| `main.py` | `main` |
| `app/auth/service.py` | `app.auth.service` |
| `app/auth/__init__.py` | `app.auth` |
| `__init__.py` | `` (cadena vacía → usar el nombre del directorio raíz si existe; si no, `__init__`) |

Se quita el sufijo `.py` y se sustituye `/` por `.`.

### Dentro del módulo

| Construcción | `qualified_name` | `kind` |
|---|---|---|
| El archivo | `app.auth.service` | `module` |
| `class Token:` | `app.auth.service.Token` | `class` |
| `def login():` a nivel de módulo | `app.auth.service.login` | `function` |
| `def refresh(self):` dentro de `class Token` | `app.auth.service.Token.refresh` | `method` |
| `class Inner:` dentro de `class Outer` | `app.auth.service.Outer.Inner` | `class` |
| `def m(self):` dentro de `Outer.Inner` | `app.auth.service.Outer.Inner.m` | `method` |

**`async def` produce el mismo `kind` que `def`** (`function` o `method` según el padre).

### Funciones anidadas: NO se indexan

Un `def` cuyo ancestro inmediato es otro `def` **no genera nodo** en Fase 0.

Razón: no son alcanzables como destino de llamada desde fuera del padre, e inflarían el grafo sin aportar navegación. Su código forma parte del `body_hash` del padre, que es donde debe estar.

Una `class` dentro de un `def` tampoco genera nodo, ni sus métodos.

---

## Construcción de la `Signature`

Es la parte con más casos límite. El orden de los parámetros importa.

### Orden

```
posonlyargs, args, *vararg, kwonlyargs, **kwarg
```

- El `vararg` se nombra `*args` (con asterisco en `Parameter.name`).
- El `kwarg` se nombra `**kwargs` (con doble asterisco).
- Ambos: `has_default = False` siempre.

### Valores por defecto — el error clásico

- `node.args.defaults` se alinea con **el final** de `posonlyargs + args`. Si hay 4 parámetros posicionales y 2 defaults, los defaults corresponden a los dos últimos.
- `node.args.kw_defaults` se alinea **uno a uno** con `kwonlyargs`, y un `None` en esa lista significa *sin valor por defecto*.

### Anotaciones

- `Parameter.annotation = ast.unparse(arg.annotation)` si existe, `None` si no.
- `Signature.returns = ast.unparse(node.returns)` si existe, `None` si no.

### Por tipo de nodo

| Nodo | `Signature` |
|---|---|
| `module` | `Signature(kind="module", name=<módulo>, parameters=(), returns=None)` |
| `class` | `Signature(kind="class", name=<nombre>, parameters=(), returns=None)` |
| `function` / `method` | firma completa como arriba |

Los decoradores **no entran** en la firma (ADR-003, Fase 0).

---

## `body_hash` y líneas

- `body_hash`: aplicar `body_hash()` de `core.identity` sobre el fragmento fuente del nodo, obtenido con `ast.get_source_segment(source, node)`.
- Para el nodo `module`: `body_hash(source)` sobre el archivo completo.
- `start_line` / `end_line`: `node.lineno` y `node.end_lineno` (ya son 1-based).
- Para el nodo `module`: `1` y el número de líneas del archivo.

---

## Restricciones

1. **No implementar aristas.** Ni `CALLS`, ni `IMPORTS`, ni `INHERITS`, ni `DEFINES`. Eso es el paso 4.
2. **No tocar `core/identity/` ni `core/graph/`.** Se consumen, no se modifican.
3. **No añadir dependencias.** Solo librería estándar (ADR-009).
4. **No escribir en la base de datos.** `parse_module` es puro: entra texto, sale una lista.
5. **Sin `print`.** Los errores se propagan como excepciones.

---

## Criterios de aceptación

Tests en `tests/test_parser_nodes.py`. Deben cubrir:

### Estructura

- [ ] Un módulo vacío produce exactamente un nodo `module`
- [ ] `app/auth/service.py` → `qualified_name` del módulo es `app.auth.service`
- [ ] `app/auth/__init__.py` → `app.auth`
- [ ] Función a nivel de módulo → `kind="function"`
- [ ] Método dentro de clase → `kind="method"` y nombre cualificado completo
- [ ] Clase anidada → `Outer.Inner`, y su método → `Outer.Inner.m`
- [ ] `async def` a nivel de módulo → `kind="function"`
- [ ] **Función anidada dentro de otra función → NO aparece en la salida**
- [ ] Clase dentro de una función → NO aparece

### Firmas

- [ ] `def f(a, b=1)` → solo `b` tiene `has_default=True`
- [ ] `def f(a, /, b, *, c, d=2)` → orden y `has_default` correctos en los cuatro
- [ ] `def f(*args, **kwargs)` → parámetros nombrados `*args` y `**kwargs`
- [ ] `def f(a: int) -> str` → anotación y retorno capturados
- [ ] `def f(a: dict[str, int])` → la anotación se serializa sin espacios espurios

### Identidad

- [ ] Todos los `node_id` de un archivo son únicos
- [ ] Reformatear el archivo no cambia ningún `body_hash`
- [ ] Añadir un comentario no cambia ningún `body_hash`

### Errores

- [ ] Un archivo con sintaxis inválida lanza `SyntaxError`, no devuelve lista vacía

---

## Verificación

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Los 50 tests existentes deben seguir pasando.

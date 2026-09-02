"""Extraccion de aristas desde codigo Python (SPEC-FASE-0 seccion 7, paso 4).

Implementa ADR-008 sobre un solo archivo, y solo dos de sus tres niveles:

- ``EXTRACTED`` (1.0) cuando el destino se deduce del AST **sin
  suposiciones**: la tabla de simbolos del modulo lo resuelve.
- ``AMBIGUOUS`` (0.0) para todo lo demas, con el texto literal como
  destino. La arista se guarda igual: registrar "hay una llamada aqui que
  no pude resolver" es honesto; borrarla haria creer al agente que el
  mapa esta completo.

**Ninguna arista ``INFERRED`` sale de este paso.** ``self.metodo()``, los
parametros anotados y los atributos son el paso 4b, que promovera algunas
de estas ``AMBIGUOUS``.

``dst_name`` es un nombre cualificado, no un ``node_id``: el parser ve un
solo archivo y no puede conocer los identificadores de otros modulos. El
paso 5 traduce el nombre a ``node_id`` cuando exista un nodo con ese
``qualified_name``. ``src`` si es un ``node_id``, porque el nodo que
contiene la referencia esta en este mismo archivo.

``extract_edges`` es pura: entra texto, sale una lista. No escribe en la
base de datos ni consulta el disco.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field

from arquigraph.core.identity import normalize_path
from arquigraph.core.parser.python import ParsedNode

__all__ = ["ParsedEdge", "extract_edges"]

_EXTRACTED = "EXTRACTED"
_AMBIGUOUS = "AMBIGUOUS"

_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

_Definition = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


@dataclass(frozen=True)
class ParsedEdge:
    """Una fila lista para insertar en la tabla ``edges``.

    ``confidence`` mide certeza de resolucion, no verosimilitud: 1.0 si el
    AST lo afirma, 0.0 si no se resolvio (ADR-008).
    """

    src: str  # node_id del nodo que contiene la referencia
    dst_name: str  # nombre cualificado del destino, TAL COMO SE RESOLVIO
    kind: str  # DEFINES | IMPORTS | INHERITS | CALLS
    evidence_path: str
    evidence_line: int
    confidence: float  # 1.0 (EXTRACTED) | 0.0 (AMBIGUOUS)
    resolution: str  # EXTRACTED | AMBIGUOUS


def extract_edges(source: str, path: str, nodes: list[ParsedNode]) -> list[ParsedEdge]:
    """Extrae las aristas de un archivo Python ya parseado en nodos.

    ``nodes`` es la salida de ``parse_module`` para el mismo archivo: de
    ahi salen los ``node_id`` que van en ``src``.

    Raises:
        SyntaxError: si el archivo no es Python valido.
        ValueError: si ``nodes`` no trae el nodo ``module`` del archivo.
    """
    tree = ast.parse(source)
    canonical_path = normalize_path(path)

    index = {(node.qualified_name, node.kind): node for node in nodes}
    module = next((node for node in nodes if node.kind == "module"), None)
    if module is None:
        raise ValueError("`nodes` debe contener el nodo module del archivo")

    table = _symbol_table(tree, canonical_path, module.qualified_name)
    context = _Context(path=canonical_path, table=table, index=index)

    edges = _import_edges(tree, module, context)
    edges += _walk(tree.body, module.qualified_name, module, context, in_class=False)
    return _dedupe(edges)


def _dedupe(edges: list[ParsedEdge]) -> list[ParsedEdge]:
    """Una sola arista por clave primaria, conservando el orden de aparicion.

    La clave de la tabla ``edges`` es
    ``(src, dst, kind, evidence_path, evidence_line)``, y una sola linea
    puede producir la misma arista dos veces:

    ``resultado = calcular(a) + calcular(b)``

    Sin esto, la insercion del archivo entero fallaria.
    """
    return list({_key(edge): edge for edge in edges}.values())


def _key(edge: ParsedEdge) -> tuple[str, str, str, str, int]:
    return (edge.src, edge.dst_name, edge.kind, edge.evidence_path, edge.evidence_line)


# ---------------------------------------------------------------------------
# Tabla de simbolos del modulo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SymbolTable:
    """Que nombre del modulo apunta a que nombre cualificado.

    ``has_star`` registra que el modulo tiene un ``from x import *``. Con
    esa marca, un nombre ausente de la tabla podria venir de cualquier
    sitio: no se adivina.
    """

    names: dict[str, str] = field(default_factory=dict)
    has_star: bool = False

    def resolve(self, name: str) -> str | None:
        if self.has_star and name not in self.names:
            return None  # puede venir del `import *`; no se afirma
        return self.names.get(name)


def _package_of(path: str) -> str:
    """Paquete que contiene al archivo, en notacion de puntos.

    Vale igual para ``app/auth/service.py`` y para
    ``app/auth/__init__.py``: en ambos casos el paquete es ``app.auth``.
    """
    return ".".join(path.split("/")[:-1])


def _join(base: str, name: str) -> str:
    """Une dos tramos de nombre cualificado tolerando que falte cualquiera.

    ``from . import util`` no aporta modulo, y un archivo en la raiz del
    repo no aporta paquete.
    """
    if not base:
        return name
    if not name:
        return base
    return f"{base}.{name}"


def _import_from_base(stmt: ast.ImportFrom, path: str) -> str:
    """Modulo del que importa un ``from ... import ...``, ya resuelto.

    Cada punto adicional sube un paquete: en ``app/auth/service.py``,
    ``from . import x`` mira en ``app.auth`` y ``from ..core import x``
    en ``app.core``.
    """
    if not stmt.level:
        return stmt.module or ""

    parts = [part for part in _package_of(path).split(".") if part]
    subir = stmt.level - 1
    if subir:
        parts = parts[: max(len(parts) - subir, 0)]
    return _join(".".join(parts), stmt.module or "")


def _symbol_table(tree: ast.Module, path: str, module_name: str) -> _SymbolTable:
    """Nombres visibles a nivel de modulo, resueltos a nombre cualificado.

    Las definiciones locales se anaden **despues** de los imports porque
    tienen prioridad: es lo que hace Python, donde la ultima asignacion al
    nombre gana y una definicion local sombrea al import.
    """
    names: dict[str, str] = {}
    has_star = False

    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.asname:
                    names[alias.asname] = alias.name
                else:
                    # `import app.auth` enlaza `app`, no `app.auth`.
                    root = alias.name.split(".")[0]
                    names[root] = root
        elif isinstance(stmt, ast.ImportFrom):
            base = _import_from_base(stmt, path)
            for alias in stmt.names:
                if alias.name == "*":
                    has_star = True
                    continue
                names[alias.asname or alias.name] = _join(base, alias.name)

    for stmt in tree.body:
        if isinstance(stmt, _DEFINITION_NODES):
            names[stmt.name] = f"{module_name}.{stmt.name}"

    return _SymbolTable(names=names, has_star=has_star)


# ---------------------------------------------------------------------------
# Contexto del recorrido
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Context:
    path: str
    table: _SymbolTable
    index: dict[tuple[str, str], ParsedNode]

    def edge(
        self,
        src: ParsedNode,
        dst_name: str,
        kind: str,
        line: int,
        *,
        resolved: bool,
    ) -> ParsedEdge:
        return ParsedEdge(
            src=src.node_id,
            dst_name=dst_name,
            kind=kind,
            evidence_path=self.path,
            evidence_line=line,
            confidence=1.0 if resolved else 0.0,
            resolution=_EXTRACTED if resolved else _AMBIGUOUS,
        )


# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------


def _import_edges(tree: ast.Module, module: ParsedNode, context: _Context) -> list[ParsedEdge]:
    """Aristas ``IMPORTS``, siempre desde el nodo ``module``.

    Solo los imports de nivel de modulo, que son los que construyen la
    tabla de simbolos.
    """
    edges: list[ParsedEdge] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            edges += [
                context.edge(module, alias.name, "IMPORTS", stmt.lineno, resolved=True)
                for alias in stmt.names
            ]
        elif isinstance(stmt, ast.ImportFrom):
            base = _import_from_base(stmt, context.path)
            for alias in stmt.names:
                # De un `import *` sabemos de donde importa, no que.
                estrella = alias.name == "*"
                dst = base if estrella else _join(base, alias.name)
                edges.append(
                    context.edge(module, dst, "IMPORTS", stmt.lineno, resolved=not estrella)
                )
    return edges


# ---------------------------------------------------------------------------
# Recorrido: DEFINES, INHERITS y CALLS
# ---------------------------------------------------------------------------


def _walk(
    body: list[ast.stmt],
    prefix: str,
    owner: ParsedNode,
    context: _Context,
    *,
    in_class: bool,
) -> list[ParsedEdge]:
    """Recorre el cuerpo directo de un modulo o de una clase.

    ``owner`` es el nodo al que se atribuyen las llamadas que aparezcan
    aqui. Las definiciones anidadas dentro de un ``def`` no tienen nodo,
    asi que sus llamadas se atribuyen al ``def`` padre, que si lo tiene.
    """
    edges: list[ParsedEdge] = []
    for stmt in body:
        if not isinstance(stmt, _DEFINITION_NODES):
            edges += _calls_in(stmt, owner, context)
            continue

        qualified_name = f"{prefix}.{stmt.name}"
        kind = "class" if isinstance(stmt, ast.ClassDef) else ("method" if in_class else "function")
        child = context.index.get((qualified_name, kind))
        if child is None:
            # Sin nodo no hay arista que citar; el contenido cuenta como
            # del contenedor.
            edges += _calls_in(stmt, owner, context)
            continue

        edges.append(context.edge(owner, qualified_name, "DEFINES", stmt.lineno, resolved=True))
        # Decoradores, bases y valores por defecto se evaluan en el
        # contenedor, no dentro de la definicion.
        for expr in _outer_expressions(stmt):
            edges += _calls_in(expr, owner, context)

        if isinstance(stmt, ast.ClassDef):
            edges += _inherits_edges(stmt, child, context)
            edges += _walk(stmt.body, qualified_name, child, context, in_class=True)
        else:
            for inner in stmt.body:
                edges += _calls_in(inner, child, context)
    return edges


def _outer_expressions(stmt: _Definition) -> Iterator[ast.AST]:
    """Todo lo de una definicion que se evalua fuera de ella."""
    yield from stmt.decorator_list
    if isinstance(stmt, ast.ClassDef):
        yield from stmt.bases
        yield from stmt.keywords
    else:
        yield stmt.args  # anotaciones y valores por defecto
        if stmt.returns is not None:
            yield stmt.returns


def _inherits_edges(
    stmt: ast.ClassDef,
    child: ParsedNode,
    context: _Context,
) -> list[ParsedEdge]:
    """Una arista por base. Sin resolver la base, ``AMBIGUOUS`` literal."""
    edges = []
    for base in stmt.bases:
        dst_name, resolved = _resolve_reference(base, context.table)
        edges.append(context.edge(child, dst_name, "INHERITS", base.lineno, resolved=resolved))
    return edges


# ---------------------------------------------------------------------------
# CALLS
# ---------------------------------------------------------------------------


def _calls_in(node: ast.AST, owner: ParsedNode, context: _Context) -> list[ParsedEdge]:
    """Aristas ``CALLS`` de todas las llamadas del subarbol, para ``owner``."""
    edges = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        dst_name, resolved = _resolve_reference(inner.func, context.table)
        edges.append(context.edge(owner, dst_name, "CALLS", inner.lineno, resolved=resolved))
    return edges


def _dotted_parts(expr: ast.expr) -> list[str] | None:
    """``['a', 'b', 'c']`` para ``a.b.c``; ``None`` si la raiz no es un nombre.

    ``obj[0].m``, ``f()(...)`` y las lambdas caen aqui: no hay raiz que
    buscar en la tabla de simbolos.
    """
    parts: list[str] = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name):
        return None
    parts.append(expr.id)
    parts.reverse()
    return parts


def _resolve_reference(expr: ast.expr, table: _SymbolTable) -> tuple[str, bool]:
    """Resuelve una referencia contra la tabla de simbolos.

    Returns:
        ``(dst_name, resolved)``. Si no se resuelve, ``dst_name`` es el
        texto literal: ``self.m``, ``len``, ``items[0].m``. Los builtins
        no se tratan aparte — filtrarlos es decision del recuperador, no
        del parser, y aqui no se descarta informacion.
    """
    parts = _dotted_parts(expr)
    if parts is None:
        return ast.unparse(expr), False

    root = table.resolve(parts[0])
    if root is None:
        return ast.unparse(expr), False
    return ".".join([root, *parts[1:]]), True

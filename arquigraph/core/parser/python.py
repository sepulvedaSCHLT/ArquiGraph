"""Extraccion de nodos desde codigo Python (SPEC-FASE-0 seccion 7, paso 3).

Solo nodos. Las aristas son el paso 4 y no se tocan aqui.

El arbol lo entrega ``ast`` de la libreria estandar, no ``tree-sitter``
(ADR-009): es el mismo arbol del que ya se deriva ``body_hash``, asi que
no hay dos fuentes de verdad que puedan discrepar.

``parse_module`` es pura: entra texto, sale una lista. No escribe en la
base de datos ni consulta el disco.

Que NO se indexa, y por que:

- Una definicion cuyo ancestro inmediato es un ``def`` no genera nodo. No
  es alcanzable como destino de llamada desde fuera del padre, e inflaria
  el grafo sin aportar navegacion. Su codigo ya cuenta en el
  ``body_hash`` del padre, que es donde debe estar.
- Solo se recorre el cuerpo directo del modulo y de las clases. Una
  definicion escondida dentro de un ``if`` o un ``try`` queda fuera en
  Fase 0; cuando aparezca el caso, se decide con el caso delante.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from arquigraph.core.identity import (
    Parameter,
    Signature,
    body_hash,
    node_id,
    normalize_path,
    signature_hash,
)

__all__ = ["ParsedNode", "parse_module"]

# Definiciones con parametros. ``async def`` produce el mismo kind que ``def``.
_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

_Definition = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


@dataclass(frozen=True)
class ParsedNode:
    """Una fila lista para insertar en la tabla ``nodes``.

    ``start_line`` y ``end_line`` son 1-based e inclusivas, y son VOLATILES:
    sirven para navegar, nunca para identificar (SPEC-FASE-0 seccion 1).
    """

    node_id: str
    kind: str  # module | class | function | method
    qualified_name: str
    path: str  # relativa a la raiz del repo, separador "/"
    signature_hash: str
    body_hash: str
    start_line: int
    end_line: int


def parse_module(source: str, path: str) -> list[ParsedNode]:
    """Extrae los nodos de un archivo Python.

    Raises:
        SyntaxError: si el archivo no es Python valido para este interprete.
    """
    tree = ast.parse(source)
    canonical_path = normalize_path(path)
    module_name = _module_qualified_name(canonical_path)

    module_node = _make_node(
        kind="module",
        qualified_name=module_name,
        path=canonical_path,
        signature=Signature(kind="module", name=module_name),
        segment=source,
        start_line=1,
        end_line=max(len(source.splitlines()), 1),
    )
    collected = _collect(tree.body, module_name, canonical_path, source, in_class=False)
    return _dedupe([module_node, *collected])


def _dedupe(nodes: list[ParsedNode]) -> list[ParsedNode]:
    """Una sola fila por ``node_id``, conservando la ultima definicion.

    Un mismo nombre puede definirse varias veces en un archivo. El caso
    frecuente es ``@overload``: las firmas previas son declaraciones para
    el verificador de tipos y la implementacion real es la ultima, que es
    tambien la que Python enlaza.

    Sin esto, el ``PRIMARY KEY`` de la tabla ``nodes`` rechazaria la
    insercion del archivo entero.

    El diccionario conserva la posicion de la primera aparicion y el
    contenido de la ultima, que es exactamente lo que queremos.
    """
    return list({node.node_id: node for node in nodes}.values())


# ---------------------------------------------------------------------------
# Del path al modulo
# ---------------------------------------------------------------------------


def _module_qualified_name(path: str) -> str:
    """Nombre de modulo de una ruta ya canonizada.

    ``app/auth/service.py`` -> ``app.auth.service``
    ``app/auth/__init__.py`` -> ``app.auth``

    Un ``__init__.py`` en la raiz del repo no tiene directorio del que
    tomar el nombre, asi que se queda en ``__init__``.
    """
    parts = path.removesuffix(".py").split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or "__init__"


# ---------------------------------------------------------------------------
# Recorrido
# ---------------------------------------------------------------------------


def _collect(
    body: list[ast.stmt],
    prefix: str,
    path: str,
    source: str,
    *,
    in_class: bool,
) -> list[ParsedNode]:
    nodes: list[ParsedNode] = []
    for stmt in body:
        if isinstance(stmt, _FUNCTION_NODES):
            kind = "method" if in_class else "function"
            nodes.append(_definition_node(stmt, kind, prefix, path, source))
            # No se desciende: lo anidado en un def no genera nodo.
        elif isinstance(stmt, ast.ClassDef):
            qualified_name = f"{prefix}.{stmt.name}"
            nodes.append(_definition_node(stmt, "class", prefix, path, source))
            nodes.extend(_collect(stmt.body, qualified_name, path, source, in_class=True))
    return nodes


def _definition_node(
    stmt: _Definition,
    kind: str,
    prefix: str,
    path: str,
    source: str,
) -> ParsedNode:
    return _make_node(
        kind=kind,
        qualified_name=f"{prefix}.{stmt.name}",
        path=path,
        signature=_build_signature(stmt, kind),
        segment=ast.get_source_segment(source, stmt) or "",
        start_line=stmt.lineno,
        end_line=stmt.end_lineno or stmt.lineno,
    )


def _make_node(
    *,
    kind: str,
    qualified_name: str,
    path: str,
    signature: Signature,
    segment: str,
    start_line: int,
    end_line: int,
) -> ParsedNode:
    return ParsedNode(
        node_id=node_id(path, qualified_name, kind),
        kind=kind,
        qualified_name=qualified_name,
        path=path,
        signature_hash=signature_hash(signature),
        body_hash=body_hash(segment),
        start_line=start_line,
        end_line=end_line,
    )


# ---------------------------------------------------------------------------
# Firmas
# ---------------------------------------------------------------------------


def _annotation(node: ast.arg | ast.expr | None) -> str | None:
    if isinstance(node, ast.arg):
        node = node.annotation
    return ast.unparse(node) if node is not None else None


def _build_signature(stmt: _Definition, kind: str) -> Signature:
    """Firma normalizable de una definicion.

    ``name`` es el nombre simple, no el cualificado: mover una funcion a
    otro archivo no cambia su contrato (SPEC-FASE-0 seccion 2). Los
    decoradores no entran en Fase 0 (ADR-003).
    """
    if isinstance(stmt, ast.ClassDef):
        return Signature(kind=kind, name=stmt.name)

    args = stmt.args
    positional = [*args.posonlyargs, *args.args]
    # `defaults` se alinea con el FINAL de los posicionales, no con el principio.
    first_default = len(positional) - len(args.defaults)

    parameters = [
        Parameter(arg.arg, _annotation(arg), index >= first_default)
        for index, arg in enumerate(positional)
    ]
    if args.vararg is not None:
        parameters.append(Parameter(f"*{args.vararg.arg}", _annotation(args.vararg), False))
    # `kw_defaults` se alinea uno a uno con `kwonlyargs`; None = sin defecto.
    parameters.extend(
        Parameter(arg.arg, _annotation(arg), default is not None)
        for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
    )
    if args.kwarg is not None:
        parameters.append(Parameter(f"**{args.kwarg.arg}", _annotation(args.kwarg), False))

    return Signature(
        kind=kind,
        name=stmt.name,
        parameters=tuple(parameters),
        returns=_annotation(stmt.returns),
    )

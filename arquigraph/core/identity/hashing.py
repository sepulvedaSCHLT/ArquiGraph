"""Identidad de nodos y disparadores de invalidacion.

Implementa la seccion 2 de docs/SPEC-FASE-0.md y materializa ADR-003.

Tres valores, tres responsabilidades distintas:

- ``node_id``        identidad estable. No cambia al editar el codigo.
- ``signature_hash`` disparador FUERTE. Cambia si cambia el contrato.
- ``body_hash``      disparador SUAVE. Cambia si cambia la implementacion,
                     pero NO si solo cambia el formato o los comentarios.

Esa ultima propiedad es la que sostiene P3: si reformatear un archivo
invalidara la memoria anclada a el, el sistema seria inutil en la practica.

Nota sobre estabilidad: ``body_hash`` se deriva del volcado del AST de
CPython, que puede variar entre versiones mayores del interprete. Por eso
el grafo registra ``parser_version`` en ``graph_meta``: un cambio de
version obliga a reconstruir, no a invalidar la memoria.
"""

from __future__ import annotations

import ast
import hashlib
import textwrap
from dataclasses import dataclass, field

__all__ = [
    "NodeRef",
    "Parameter",
    "Signature",
    "body_hash",
    "detect_moves",
    "node_id",
    "normalize_body",
    "normalize_path",
    "normalize_signature",
    "signature_hash",
]

# 8 bytes -> 16 caracteres hexadecimales. Suficiente para un repositorio:
# la colision exigiria ~2^32 nodos con el mismo par (path, qualified_name).
_DIGEST_SIZE = 8

# Nodos del AST que representan una definicion con cuerpo propio.
_DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Parameter:
    """Un parametro de una firma.

    ``has_default`` registra si el parametro tiene valor por defecto, pero
    NO cual es: cambiar ``timeout=30`` por ``timeout=60`` altera el
    comportamiento, no el contrato.
    """

    name: str
    annotation: str | None = None
    has_default: bool = False


@dataclass(frozen=True)
class Signature:
    """Firma normalizable de una definicion."""

    kind: str
    name: str
    parameters: tuple[Parameter, ...] = field(default_factory=tuple)
    returns: str | None = None


@dataclass(frozen=True)
class NodeRef:
    """Referencia minima a un nodo, para detectar movimientos."""

    node_id: str
    body_hash: str


# ---------------------------------------------------------------------------
# Primitiva de hash
# ---------------------------------------------------------------------------


def _digest(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=_DIGEST_SIZE).hexdigest()


# ---------------------------------------------------------------------------
# Identidad
# ---------------------------------------------------------------------------


def normalize_path(path: str) -> str:
    """Normaliza una ruta a la forma canonica del grafo.

    Separador ``/`` en cualquier sistema operativo y sin prefijo ``./``,
    para que el mismo archivo produzca el mismo ``node_id`` en Linux,
    macOS y Windows.
    """
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def node_id(path: str, qualified_name: str, kind: str) -> str:
    """Identidad estable de un nodo.

    Deliberadamente NO intervienen: numero de linea, offset de bytes,
    contenido ni orden de aparicion. Anadir codigo encima de una funcion
    no cambia su identidad.
    """
    return _digest(f"{normalize_path(path)}::{qualified_name}::{kind}")


# ---------------------------------------------------------------------------
# Disparador fuerte: la firma
# ---------------------------------------------------------------------------


def _normalize_expression(text: str | None) -> str:
    """Normaliza una expresion de tipo a forma canonica.

    ``dict[str, int]`` y ``dict[str,  int]`` son el mismo tipo escrito de
    dos maneras; deben producir el mismo hash. Si el texto no es una
    expresion valida, se cae a colapsar espacios.
    """
    if not text or not text.strip():
        return ""
    try:
        return ast.dump(ast.parse(text.strip(), mode="eval").body)
    except SyntaxError:
        return " ".join(text.split())


def normalize_signature(signature: Signature) -> str:
    """Serializa una firma a su forma canonica.

    Formato: ``{kind}|{nombre}|{p1}:{anotacion1}{=},...|{retorno}``

    El orden de los parametros es significativo: reordenarlos rompe a
    quien llama por posicion, y eso es un cambio de contrato.
    """
    params = ",".join(
        f"{p.name}:{_normalize_expression(p.annotation)}{'=' if p.has_default else ''}"
        for p in signature.parameters
    )
    returns = _normalize_expression(signature.returns)
    return f"{signature.kind}|{signature.name}|{params}|{returns}"


def signature_hash(signature: Signature) -> str:
    """Disparador FUERTE: cambia cuando cambia el contrato publico."""
    return _digest(normalize_signature(signature))


# ---------------------------------------------------------------------------
# Disparador suave: el cuerpo
# ---------------------------------------------------------------------------


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if not body:
        return body
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return body[1:]
    return body


def normalize_body(source: str) -> str:
    """Normaliza el cuerpo de una definicion a forma canonica.

    Se apoya en el AST, que por construccion descarta comentarios,
    espaciado y saltos de linea. Los docstrings se eliminan de forma
    explicita: documentar mejor una funcion no cambia lo que hace.

    Acepta la definicion completa (``def f(x): ...``) o un bloque de
    sentencias. La indentacion sobrante se elimina antes de parsear.

    Raises:
        SyntaxError: si el codigo no es Python valido.
    """
    tree = ast.parse(textwrap.dedent(source))
    body = tree.body
    if len(body) == 1 and isinstance(body[0], _DEFINITION_NODES):
        body = body[0].body
    return "".join(ast.dump(stmt) for stmt in _strip_docstring(body))


def body_hash(source: str) -> str:
    """Disparador SUAVE: cambia con la implementacion, no con el formato."""
    return _digest(normalize_body(source))


# ---------------------------------------------------------------------------
# Migracion de anclas (mitigacion de R2)
# ---------------------------------------------------------------------------


def detect_moves(
    disappeared: list[NodeRef],
    appeared: list[NodeRef],
) -> dict[str, str]:
    """Empareja nodos desaparecidos con nodos nuevos de cuerpo identico.

    Un renombrado o un cambio de archivo produce un ``node_id`` distinto
    con el mismo ``body_hash``. Sin esta deteccion, un refactor rutinario
    borraria toda la memoria anclada del proyecto: es la mitigacion
    directa de R2.

    Regla de seguridad: solo se empareja cuando la correspondencia es
    **uno a uno**. Si varios nodos comparten ``body_hash`` (tipico en
    funciones triviales o autogeneradas), la migracion seria una
    adivinanza, y preferimos invalidar antes que anclar memoria al nodo
    equivocado.

    Returns:
        Mapa ``node_id`` antiguo -> ``node_id`` nuevo. Lo que no aparece
        aqui se invalida.
    """
    by_old: dict[str, list[str]] = {}
    for ref in disappeared:
        by_old.setdefault(ref.body_hash, []).append(ref.node_id)

    by_new: dict[str, list[str]] = {}
    for ref in appeared:
        by_new.setdefault(ref.body_hash, []).append(ref.node_id)

    return {
        old_ids[0]: by_new[digest][0]
        for digest, old_ids in by_old.items()
        if len(old_ids) == 1 and len(by_new.get(digest, [])) == 1
    }

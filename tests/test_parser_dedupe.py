"""Un archivo nunca produce dos nodos con el mismo ``node_id``.

Es requisito del ``PRIMARY KEY`` de la tabla ``nodes``: sin esta garantia,
insertar un archivo con ``@overload`` abortaria la construccion del grafo
entera con un ``IntegrityError``.

La regla es conservar la **ultima** definicion, que es la que Python
enlaza realmente.
"""

from arquigraph.core.parser.python import parse_module

OVERLOAD = '''
from typing import overload


@overload
def f(x: int) -> int: ...


@overload
def f(x: str) -> str: ...


def f(x):
    """Implementacion real: la que Python enlaza."""
    return x
'''

REDEFINICION = """
def f():
    return 1


def f():
    return 2
"""

METODO_REDEFINIDO = """
class Servicio:
    def guardar(self):
        return 1

    def guardar(self):
        return 2
"""


def _ids(source: str) -> list[str]:
    return [n.node_id for n in parse_module(source, "m.py")]


def test_overload_no_duplica_identidades() -> None:
    ids = _ids(OVERLOAD)
    assert len(ids) == len(set(ids))


def test_overload_deja_un_solo_nodo_para_la_funcion() -> None:
    """Un nodo `module` y un nodo `m.f`, no cuatro."""
    nodos = parse_module(OVERLOAD, "m.py")
    assert [n.qualified_name for n in nodos] == ["m", "m.f"]


def test_conserva_la_ultima_definicion() -> None:
    """La implementacion real es la ultima, no la declaracion de tipos."""
    ultima = parse_module(OVERLOAD, "m.py")[-1]
    solo_implementacion = parse_module("def f(x):\n    return x\n", "m.py")[-1]
    assert ultima.body_hash == solo_implementacion.body_hash


def test_redefinicion_simple_no_duplica() -> None:
    ids = _ids(REDEFINICION)
    assert len(ids) == len(set(ids))


def test_redefinicion_conserva_el_segundo_cuerpo() -> None:
    ultima = parse_module(REDEFINICION, "m.py")[-1]
    segunda = parse_module("def f():\n    return 2\n", "m.py")[-1]
    assert ultima.body_hash == segunda.body_hash


def test_metodo_redefinido_no_duplica() -> None:
    ids = _ids(METODO_REDEFINIDO)
    assert len(ids) == len(set(ids))


def test_archivo_vacio_tiene_una_linea_como_minimo() -> None:
    """end_line nunca debe quedar por debajo de start_line."""
    (modulo,) = parse_module("", "m.py")
    assert modulo.start_line == 1
    assert modulo.end_line >= modulo.start_line

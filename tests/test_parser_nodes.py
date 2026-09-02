"""Extraccion de nodos desde Python (SPEC-FASE-0 seccion 7, paso 3).

Lo que estos tests fijan:

- Que se indexa y que no. Las funciones anidadas dentro de otra funcion
  quedan fuera a proposito: no son alcanzables desde fuera del padre y su
  codigo ya cuenta en el ``body_hash`` del padre.
- Que el orden de los parametros y las marcas de valor por defecto son
  exactos, porque de ahi sale el disparador FUERTE.
- Que el ``body_hash`` sobrevive a un reformateo. Es la misma propiedad
  que sostiene P3 en ``test_identity.py``, verificada ahora extremo a
  extremo sobre un archivo real.
- Que ningun archivo produce dos nodos con el mismo ``node_id``. Es
  requisito del ``PRIMARY KEY`` de la tabla ``nodes``.

Aristas: paso 4. Aqui no se comprueban.
"""

import ast

import pytest

from arquigraph.core.identity import Parameter, Signature
from arquigraph.core.parser.python import ParsedNode, _build_signature, parse_module


def por_nombre(nodos: list[ParsedNode]) -> dict[str, ParsedNode]:
    return {n.qualified_name: n for n in nodos}


def firma_de(source: str) -> Signature:
    """Firma que el parser construye para la unica definicion de ``source``."""
    (definicion,) = ast.parse(source).body
    return _build_signature(definicion, "function")


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------


def test_modulo_vacio_produce_un_solo_nodo() -> None:
    nodos = parse_module("", "main.py")

    assert len(nodos) == 1
    assert nodos[0].kind == "module"
    assert nodos[0].qualified_name == "main"


@pytest.mark.parametrize(
    ("path", "esperado"),
    [
        ("main.py", "main"),
        ("app/auth/service.py", "app.auth.service"),
        ("app/auth/__init__.py", "app.auth"),
        ("__init__.py", "__init__"),
        ("./app/auth/service.py", "app.auth.service"),
        ("app\\auth\\service.py", "app.auth.service"),
    ],
)
def test_nombre_cualificado_del_modulo(path: str, esperado: str) -> None:
    (modulo,) = parse_module("", path)

    assert modulo.qualified_name == esperado


def test_funcion_a_nivel_de_modulo() -> None:
    nodos = por_nombre(parse_module("def login():\n    pass\n", "app/auth/service.py"))

    assert nodos["app.auth.service.login"].kind == "function"


def test_metodo_dentro_de_clase() -> None:
    source = "class Token:\n    def refresh(self):\n        pass\n"

    nodos = por_nombre(parse_module(source, "app/auth/service.py"))

    assert nodos["app.auth.service.Token"].kind == "class"
    assert nodos["app.auth.service.Token.refresh"].kind == "method"


def test_clase_anidada_y_su_metodo() -> None:
    source = "class Outer:\n    class Inner:\n        def m(self):\n            pass\n"

    nodos = por_nombre(parse_module(source, "svc.py"))

    assert nodos["svc.Outer.Inner"].kind == "class"
    assert nodos["svc.Outer.Inner.m"].kind == "method"


def test_async_def_a_nivel_de_modulo_es_funcion() -> None:
    nodos = por_nombre(parse_module("async def fetch():\n    pass\n", "svc.py"))

    assert nodos["svc.fetch"].kind == "function"


def test_async_def_dentro_de_clase_es_metodo() -> None:
    source = "class Client:\n    async def fetch(self):\n        pass\n"

    nodos = por_nombre(parse_module(source, "svc.py"))

    assert nodos["svc.Client.fetch"].kind == "method"


def test_funcion_anidada_no_se_indexa() -> None:
    source = "def outer():\n    def inner():\n        pass\n    return inner\n"

    nombres = por_nombre(parse_module(source, "svc.py"))

    assert "svc.outer" in nombres
    assert "svc.outer.inner" not in nombres
    assert len(nombres) == 2  # modulo + outer


def test_clase_dentro_de_funcion_no_se_indexa() -> None:
    source = (
        "def factory():\n"
        "    class Hidden:\n"
        "        def m(self):\n"
        "            pass\n"
        "    return Hidden\n"
    )

    nombres = por_nombre(parse_module(source, "svc.py"))

    assert set(nombres) == {"svc", "svc.factory"}


# ---------------------------------------------------------------------------
# Firmas
# ---------------------------------------------------------------------------


def test_default_se_alinea_con_el_final_de_los_posicionales() -> None:
    assert firma_de("def f(a, b=1): pass").parameters == (
        Parameter("a", None, False),
        Parameter("b", None, True),
    )


def test_posonly_kwonly_orden_y_defaults() -> None:
    assert firma_de("def f(a, /, b, *, c, d=2): pass").parameters == (
        Parameter("a", None, False),
        Parameter("b", None, False),
        Parameter("c", None, False),
        Parameter("d", None, True),
    )


def test_vararg_y_kwarg_llevan_asteriscos() -> None:
    assert firma_de("def f(*args, **kwargs): pass").parameters == (
        Parameter("*args", None, False),
        Parameter("**kwargs", None, False),
    )


def test_vararg_no_confunde_el_alineado_de_defaults() -> None:
    assert firma_de("def f(a, b=1, *args, c, d=2, **kwargs): pass").parameters == (
        Parameter("a", None, False),
        Parameter("b", None, True),
        Parameter("*args", None, False),
        Parameter("c", None, False),
        Parameter("d", None, True),
        Parameter("**kwargs", None, False),
    )


def test_anotaciones_y_retorno() -> None:
    firma = firma_de("def f(a: int) -> str: pass")

    assert firma.parameters == (Parameter("a", "int", False),)
    assert firma.returns == "str"


def test_anotacion_generica_sin_espacios_espurios() -> None:
    assert firma_de("def f(a: dict[str,   int]): pass").parameters == (
        Parameter("a", "dict[str, int]", False),
    )


def test_sin_anotacion_de_retorno_es_none() -> None:
    assert firma_de("def f(a): pass").returns is None


def test_la_firma_de_una_clase_no_lleva_parametros() -> None:
    firma = _build_signature(ast.parse("class Token:\n    pass").body[0], "class")

    assert firma == Signature(kind="class", name="Token", parameters=(), returns=None)


def test_decoradores_no_entran_en_la_firma() -> None:
    """ADR-003: en Fase 0 los decoradores no forman parte del contrato."""
    plano = parse_module("def f(a):\n    return a\n", "svc.py")
    decorada = parse_module("@cache\ndef f(a):\n    return a\n", "svc.py")

    assert por_nombre(plano)["svc.f"].signature_hash == por_nombre(decorada)["svc.f"].signature_hash


# ---------------------------------------------------------------------------
# Identidad
# ---------------------------------------------------------------------------


ARCHIVO = '''\
"""Docstring del modulo."""


class Token:
    """Un token."""

    def refresh(self, ttl=30):
        value = compute(ttl)
        return value

    class Inner:
        def m(self):
            return 1


def login(user, password=None):
    return Token()
'''


def test_todos_los_node_id_son_unicos() -> None:
    nodos = parse_module(ARCHIVO, "app/auth/service.py")

    ids = [n.node_id for n in nodos]
    assert len(set(ids)) == len(ids)
    assert len(ids) == 6  # modulo, Token, refresh, Inner, m, login


def test_reformatear_no_cambia_ningun_body_hash() -> None:
    reformateado = '''\
"""Docstring del modulo."""
class Token:
    """Un token."""
    def refresh( self , ttl = 30 ):

        value  =  compute( ttl )

        return  value
    class Inner:

        def m( self ):
            return  1
def login( user , password = None ):
    return  Token( )
'''

    original = por_nombre(parse_module(ARCHIVO, "app/auth/service.py"))
    nuevo = por_nombre(parse_module(reformateado, "app/auth/service.py"))

    assert set(original) == set(nuevo)
    for nombre, nodo in original.items():
        assert nodo.body_hash == nuevo[nombre].body_hash, nombre


def test_anadir_un_comentario_no_cambia_ningun_body_hash() -> None:
    comentado = ARCHIVO.replace(
        "    def refresh(self, ttl=30):",
        "    # el ttl por defecto viene de la configuracion\n    def refresh(self, ttl=30):",
    )

    original = por_nombre(parse_module(ARCHIVO, "app/auth/service.py"))
    nuevo = por_nombre(parse_module(comentado, "app/auth/service.py"))

    for nombre, nodo in original.items():
        assert nodo.body_hash == nuevo[nombre].body_hash, nombre


def test_lineas_del_nodo_son_1_based_e_inclusivas() -> None:
    nodos = por_nombre(parse_module(ARCHIVO, "app/auth/service.py"))

    assert nodos["app.auth.service"].start_line == 1
    assert nodos["app.auth.service"].end_line == len(ARCHIVO.splitlines())
    assert nodos["app.auth.service.Token.refresh"].start_line == 7
    assert nodos["app.auth.service.Token.refresh"].end_line == 9


def test_la_ruta_se_canoniza() -> None:
    (modulo,) = parse_module("", ".\\app\\auth\\service.py")

    assert modulo.path == "app/auth/service.py"


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


def test_sintaxis_invalida_lanza_syntax_error() -> None:
    with pytest.raises(SyntaxError):
        parse_module("def f(:\n", "roto.py")

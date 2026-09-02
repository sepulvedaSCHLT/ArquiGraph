"""Extraccion de aristas desde Python (SPEC-FASE-0 seccion 7, paso 4).

Lo que estos tests fijan es la politica de ADR-008 aplicada a un solo
archivo:

- ``EXTRACTED`` solo cuando el AST lo resuelve **sin suposiciones**.
- Todo lo demas es ``AMBIGUOUS``, y se guarda igual: que ``arqui trace``
  diga "hay una llamada aqui que no pude resolver" es honesto; borrarla
  haria creer que el mapa esta completo.
- Ninguna arista ``INFERRED`` sale de este paso. Las suposiciones
  (``self.metodo()``, parametros anotados) son el paso 4b.

``dst_name`` es un nombre cualificado, no un ``node_id``: el parser ve un
solo archivo y no puede conocer los identificadores de otros modulos. La
traduccion a ``node_id`` es el paso 5.
"""

import pytest

from arquigraph.core.parser.edges import ParsedEdge, extract_edges
from arquigraph.core.parser.python import ParsedNode, parse_module

RUTA = "app/auth/service.py"


def aristas(source: str, path: str = RUTA) -> list[ParsedEdge]:
    return extract_edges(source, path, parse_module(source, path))


def de_tipo(edges: list[ParsedEdge], kind: str) -> list[ParsedEdge]:
    return [e for e in edges if e.kind == kind]


def nodo(source: str, qualified_name: str, path: str = RUTA) -> ParsedNode:
    (encontrado,) = [n for n in parse_module(source, path) if n.qualified_name == qualified_name]
    return encontrado


def destinos(edges: list[ParsedEdge], kind: str) -> set[str]:
    return {e.dst_name for e in de_tipo(edges, kind)}


# ---------------------------------------------------------------------------
# DEFINES
# ---------------------------------------------------------------------------


def test_defines_del_modulo_a_sus_definiciones() -> None:
    source = "def login():\n    pass\n\n\nclass Token:\n    pass\n"

    edges = de_tipo(aristas(source), "DEFINES")
    modulo = nodo(source, "app.auth.service")

    assert {(e.src, e.dst_name) for e in edges} == {
        (modulo.node_id, "app.auth.service.login"),
        (modulo.node_id, "app.auth.service.Token"),
    }
    assert all(e.resolution == "EXTRACTED" and e.confidence == 1.0 for e in edges)


def test_defines_de_la_clase_a_sus_metodos() -> None:
    source = (
        "class Token:\n"
        "    def refresh(self):\n"
        "        pass\n"
        "\n"
        "    def revoke(self):\n"
        "        pass\n"
    )

    edges = de_tipo(aristas(source), "DEFINES")
    token = nodo(source, "app.auth.service.Token")

    desde_token = {e.dst_name for e in edges if e.src == token.node_id}
    assert desde_token == {"app.auth.service.Token.refresh", "app.auth.service.Token.revoke"}


def test_defines_de_la_clase_externa_a_la_interna() -> None:
    source = "class Outer:\n    class Inner:\n        pass\n"

    edges = de_tipo(aristas(source), "DEFINES")
    outer = nodo(source, "app.auth.service.Outer")

    assert (outer.node_id, "app.auth.service.Outer.Inner") in {(e.src, e.dst_name) for e in edges}


def test_defines_apunta_a_la_linea_de_la_definicion_contenida() -> None:
    source = "\n\ndef login():\n    pass\n"

    (arista,) = de_tipo(aristas(source), "DEFINES")

    assert arista.evidence_line == 3
    assert arista.evidence_path == RUTA


# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------


def test_import_con_punto() -> None:
    edges = aristas("import app.auth\n")

    assert destinos(edges, "IMPORTS") == {"app.auth"}
    assert de_tipo(edges, "IMPORTS")[0].resolution == "EXTRACTED"


def test_import_con_alias() -> None:
    assert destinos(aristas("import app.auth as a\n"), "IMPORTS") == {"app.auth"}


def test_from_import_resuelve_el_simbolo() -> None:
    assert destinos(aristas("from app.auth import verify\n"), "IMPORTS") == {"app.auth.verify"}


def test_import_relativo_de_un_punto() -> None:
    assert destinos(aristas("from . import util\n"), "IMPORTS") == {"app.auth.util"}


def test_import_relativo_con_modulo() -> None:
    assert destinos(aristas("from .service import f\n"), "IMPORTS") == {"app.auth.service.f"}


def test_import_relativo_de_dos_puntos() -> None:
    assert destinos(aristas("from ..core import g\n"), "IMPORTS") == {"app.core.g"}


def test_import_estrella_es_ambiguo_y_apunta_al_modulo() -> None:
    (arista,) = de_tipo(aristas("from x import *\n"), "IMPORTS")

    assert arista.dst_name == "x"
    assert arista.resolution == "AMBIGUOUS"
    assert arista.confidence == 0.0


def test_el_src_de_un_import_es_el_modulo() -> None:
    source = "import app.auth\n"

    (arista,) = de_tipo(aristas(source), "IMPORTS")

    assert arista.src == nodo(source, "app.auth.service").node_id


# ---------------------------------------------------------------------------
# INHERITS
# ---------------------------------------------------------------------------


def test_hereda_de_una_base_importada() -> None:
    source = "from app.models import Base\n\n\nclass A(Base):\n    pass\n"

    (arista,) = de_tipo(aristas(source), "INHERITS")

    assert arista.dst_name == "app.models.Base"
    assert arista.resolution == "EXTRACTED"
    assert arista.confidence == 1.0
    assert arista.src == nodo(source, "app.auth.service.A").node_id


def test_hereda_de_una_base_local() -> None:
    source = "class Base:\n    pass\n\n\nclass A(Base):\n    pass\n"

    (arista,) = de_tipo(aristas(source), "INHERITS")

    assert arista.dst_name == "app.auth.service.Base"
    assert arista.resolution == "EXTRACTED"


def test_hereda_de_una_base_no_resoluble() -> None:
    (arista,) = de_tipo(aristas("class A(desconocido.Base):\n    pass\n"), "INHERITS")

    assert arista.dst_name == "desconocido.Base"
    assert arista.resolution == "AMBIGUOUS"
    assert arista.confidence == 0.0


def test_dos_bases_dan_dos_aristas() -> None:
    source = "class B:\n    pass\n\n\nclass C:\n    pass\n\n\nclass A(B, C):\n    pass\n"

    edges = de_tipo(aristas(source), "INHERITS")

    assert {e.dst_name for e in edges} == {"app.auth.service.B", "app.auth.service.C"}


def test_base_con_atributo_sobre_import_resoluble() -> None:
    source = "import app.models\n\n\nclass A(app.models.Base):\n    pass\n"

    (arista,) = de_tipo(aristas(source), "INHERITS")

    assert arista.dst_name == "app.models.Base"
    assert arista.resolution == "EXTRACTED"


# ---------------------------------------------------------------------------
# CALLS
# ---------------------------------------------------------------------------


def test_llamada_a_funcion_del_mismo_modulo() -> None:
    source = "def helper():\n    pass\n\n\ndef login():\n    return helper()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert arista.dst_name == "app.auth.service.helper"
    assert arista.resolution == "EXTRACTED"
    assert arista.confidence == 1.0


def test_llamada_via_from_import() -> None:
    source = "from a import b\n\n\ndef f():\n    return b()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("a.b", "EXTRACTED")


def test_llamada_via_import_con_alias() -> None:
    source = "import a.b as c\n\n\ndef f():\n    return c.f()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("a.b.f", "EXTRACTED")


def test_cadena_de_atributos_completa() -> None:
    source = "import a\n\n\ndef f():\n    return a.b.c()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("a.b.c", "EXTRACTED")


def test_nombre_no_resoluble_conserva_el_literal() -> None:
    (arista,) = de_tipo(aristas("def f():\n    return desconocido()\n"), "CALLS")

    assert (arista.dst_name, arista.resolution, arista.confidence) == (
        "desconocido",
        "AMBIGUOUS",
        0.0,
    )


def test_atributo_sobre_nombre_no_resoluble() -> None:
    (arista,) = de_tipo(aristas("def f(x):\n    return x.metodo()\n"), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("x.metodo", "AMBIGUOUS")


def test_self_es_ambiguo_en_este_paso() -> None:
    """El paso 4b lo promovera a INFERRED; aqui no se supone nada."""
    source = "class A:\n    def f(self):\n        return self.m()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert (arista.dst_name, arista.resolution, arista.confidence) == ("self.m", "AMBIGUOUS", 0.0)


def test_llamada_sobre_expresion_no_dotada() -> None:
    source = "def f(items):\n    return items[0].m()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("items[0].m", "AMBIGUOUS")


def test_con_marca_de_estrella_un_nombre_desconocido_nunca_se_resuelve() -> None:
    source = "from x import *\n\n\ndef f():\n    return verify()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("verify", "AMBIGUOUS")


def test_la_marca_de_estrella_no_borra_lo_que_si_esta_en_la_tabla() -> None:
    source = "from x import *\nfrom a import b\n\n\ndef f():\n    return b()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("a.b", "EXTRACTED")


def test_los_builtins_no_se_descartan() -> None:
    (arista,) = de_tipo(aristas("def f(x):\n    return len(x)\n"), "CALLS")

    assert (arista.dst_name, arista.resolution) == ("len", "AMBIGUOUS")


def test_una_definicion_local_tiene_prioridad_sobre_el_import() -> None:
    source = (
        "from a import verify\n\n\ndef verify():\n    pass\n\n\ndef f():\n    return verify()\n"
    )

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert arista.dst_name == "app.auth.service.verify"


# ---------------------------------------------------------------------------
# Atribucion y duplicados
# ---------------------------------------------------------------------------


def test_llamada_dentro_de_un_metodo_se_atribuye_al_metodo() -> None:
    source = "class A:\n    def f(self):\n        return desconocido()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert arista.src == nodo(source, "app.auth.service.A.f").node_id


def test_llamada_a_nivel_de_modulo_se_atribuye_al_modulo() -> None:
    source = "resultado = desconocido()\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert arista.src == nodo(source, "app.auth.service").node_id


def test_llamada_en_funcion_anidada_se_atribuye_a_la_funcion_padre() -> None:
    source = "def outer():\n    def inner():\n        return desconocido()\n\n    return inner\n"

    (arista,) = de_tipo(aristas(source), "CALLS")

    assert arista.src == nodo(source, "app.auth.service.outer").node_id


def test_dos_llamadas_identicas_en_una_linea_dan_una_sola_arista() -> None:
    source = "def f(a, b):\n    return desconocido(a) + desconocido(b)\n"

    assert len(de_tipo(aristas(source), "CALLS")) == 1


def test_la_lista_completa_no_tiene_duplicados() -> None:
    source = "def f(items):\n    return [g(x) for x in items] + [g(y) for y in items]\n"

    edges = aristas(source)
    claves = [(e.src, e.dst_name, e.kind, e.evidence_path, e.evidence_line) for e in edges]

    assert len(claves) == len(set(claves))


def test_ninguna_arista_es_inferred() -> None:
    source = (
        "from a import b\n"
        "import c.d as e\n"
        "from x import *\n"
        "\n\n"
        "class A(b):\n"
        "    def m(self):\n"
        "        return self.otro() + e.f() + len(desconocido)\n"
        "\n\n"
        "def top():\n"
        "    return A().m()\n"
    )

    edges = aristas(source)

    assert edges
    assert {e.resolution for e in edges} <= {"EXTRACTED", "AMBIGUOUS"}
    assert {e.confidence for e in edges} <= {0.0, 1.0}


# ---------------------------------------------------------------------------
# Evidencia
# ---------------------------------------------------------------------------


def test_toda_arista_lleva_evidencia() -> None:
    source = "import a\n\n\nclass A(a.Base):\n    def m(self):\n        return a.f()\n"

    edges = aristas(source)
    lineas = len(source.splitlines())

    assert edges
    for arista in edges:
        assert arista.evidence_path == RUTA
        assert 1 <= arista.evidence_line <= lineas


def test_dos_llamadas_al_mismo_destino_en_lineas_distintas_dan_dos_aristas() -> None:
    source = "def f(a, b):\n    desconocido(a)\n    desconocido(b)\n"

    edges = de_tipo(aristas(source), "CALLS")

    assert sorted(e.evidence_line for e in edges) == [2, 3]


def test_la_ruta_de_la_evidencia_se_canoniza() -> None:
    source = "def f():\n    return desconocido()\n"

    edges = extract_edges(source, ".\\app\\auth\\service.py", parse_module(source, RUTA))

    assert all(e.evidence_path == RUTA for e in edges)


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


def test_sintaxis_invalida_lanza_syntax_error() -> None:
    with pytest.raises(SyntaxError):
        extract_edges("def f(:\n", "roto.py", [])

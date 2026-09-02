"""Contrato de identidad e invalidacion (ADR-003, SPEC-FASE-0 seccion 2).

La tabla que estos tests fijan:

| Cambio en el codigo        | node_id  | signature_hash | body_hash |
|----------------------------|----------|----------------|-----------|
| Reformatear / comentarios  | igual    | igual          | IGUAL     |
| Cambiar el cuerpo          | igual    | igual          | distinto  |
| Renombrar un parametro     | igual    | DISTINTO       | igual     |
| Anadir anotacion de tipo   | igual    | DISTINTO       | igual     |
| Renombrar la funcion       | DISTINTO | distinto       | igual     |
| Mover a otro archivo       | DISTINTO | igual          | igual     |

Las dos ultimas filas son las que habilitan la migracion de anclas: mismo
cuerpo con distinta identidad significa movimiento, no borrado.
"""

import pytest

from arquigraph.core.identity import (
    NodeRef,
    Parameter,
    Signature,
    body_hash,
    detect_moves,
    node_id,
    normalize_body,
    normalize_path,
    normalize_signature,
    signature_hash,
)

# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("app/auth/service.py", "app/auth/service.py"),
        ("app\\auth\\service.py", "app/auth/service.py"),
        ("./app/auth/service.py", "app/auth/service.py"),
        ("/app/auth/service.py", "app/auth/service.py"),
        ("  app/auth/service.py  ", "app/auth/service.py"),
    ],
)
def test_normalize_path_canoniza(entrada: str, esperado: str) -> None:
    assert normalize_path(entrada) == esperado


def test_misma_ruta_en_windows_y_linux_da_el_mismo_id() -> None:
    """Un repo clonado en Windows debe producir el mismo grafo."""
    assert node_id("app\\auth.py", "app.auth.login", "function") == node_id(
        "app/auth.py", "app.auth.login", "function"
    )


# ---------------------------------------------------------------------------
# node_id
# ---------------------------------------------------------------------------


def test_node_id_es_determinista_y_de_16_hex() -> None:
    resultado = node_id("app/auth.py", "app.auth.login", "function")
    assert resultado == node_id("app/auth.py", "app.auth.login", "function")
    assert len(resultado) == 16
    assert all(c in "0123456789abcdef" for c in resultado)


def test_node_id_cambia_al_renombrar_la_funcion() -> None:
    """Renombrar es un cambio de identidad: la memoria debe invalidarse."""
    assert node_id("app/auth.py", "app.auth.login", "function") != node_id(
        "app/auth.py", "app.auth.signin", "function"
    )


def test_node_id_cambia_al_mover_de_archivo() -> None:
    assert node_id("app/auth.py", "app.auth.login", "function") != node_id(
        "app/session.py", "app.auth.login", "function"
    )


def test_node_id_distingue_el_tipo_de_nodo() -> None:
    """Una clase y una funcion con el mismo nombre no son el mismo nodo."""
    assert node_id("app/a.py", "app.a.Token", "class") != node_id(
        "app/a.py", "app.a.Token", "function"
    )


# ---------------------------------------------------------------------------
# signature_hash — disparador FUERTE
# ---------------------------------------------------------------------------


def _firma(**cambios: object) -> Signature:
    base: dict[str, object] = {
        "kind": "function",
        "name": "refresh",
        "parameters": (
            Parameter("self"),
            Parameter("token", "str"),
            Parameter("timeout", "int", has_default=True),
        ),
        "returns": "bool",
    }
    base.update(cambios)
    return Signature(**base)  # type: ignore[arg-type]


def test_firma_identica_produce_el_mismo_hash() -> None:
    assert signature_hash(_firma()) == signature_hash(_firma())


def test_renombrar_un_parametro_cambia_la_firma() -> None:
    """Rompe a quien llama por nombre: es un cambio de contrato."""
    otra = _firma(
        parameters=(
            Parameter("self"),
            Parameter("jwt", "str"),
            Parameter("timeout", "int", has_default=True),
        )
    )
    assert signature_hash(_firma()) != signature_hash(otra)


def test_anadir_anotacion_de_tipo_cambia_la_firma() -> None:
    sin_anotacion = _firma(
        parameters=(
            Parameter("self"),
            Parameter("token"),
            Parameter("timeout", "int", has_default=True),
        )
    )
    assert signature_hash(_firma()) != signature_hash(sin_anotacion)


def test_reordenar_parametros_cambia_la_firma() -> None:
    """Rompe a quien llama por posicion."""
    invertida = _firma(
        parameters=(
            Parameter("self"),
            Parameter("timeout", "int", has_default=True),
            Parameter("token", "str"),
        )
    )
    assert signature_hash(_firma()) != signature_hash(invertida)


def test_cambiar_el_tipo_de_retorno_cambia_la_firma() -> None:
    assert signature_hash(_firma()) != signature_hash(_firma(returns="str"))


def test_quitar_el_valor_por_defecto_cambia_la_firma() -> None:
    """Deja de ser opcional: quien no lo pasaba, ahora falla."""
    obligatorio = _firma(
        parameters=(
            Parameter("self"),
            Parameter("token", "str"),
            Parameter("timeout", "int", has_default=False),
        )
    )
    assert signature_hash(_firma()) != signature_hash(obligatorio)


def test_el_espaciado_de_la_anotacion_no_cambia_la_firma() -> None:
    """dict[str, int] y dict[str,int] son el mismo tipo."""
    apretada = _firma(parameters=(Parameter("datos", "dict[str,int]"),))
    espaciada = _firma(parameters=(Parameter("datos", "dict[str,  int]"),))
    assert signature_hash(apretada) == signature_hash(espaciada)


def test_normalize_signature_es_legible_para_depurar() -> None:
    firma = Signature(kind="function", name="ping", parameters=(), returns=None)
    assert normalize_signature(firma) == "function|ping||"


# ---------------------------------------------------------------------------
# body_hash — disparador SUAVE
# ---------------------------------------------------------------------------

ORIGINAL = """
def refresh(self, token: str) -> bool:
    valor = self._decode(token)
    return valor is not None
"""

REFORMATEADA = """
def refresh(self, token: str) -> bool:

    valor  =  self._decode( token )

    return valor is not None
"""

CON_COMENTARIOS = """
def refresh(self, token: str) -> bool:
    # Decodifica el token recibido.
    valor = self._decode(token)
    # None significa que expiro.
    return valor is not None
"""

CON_DOCSTRING = """
def refresh(self, token: str) -> bool:
    \"\"\"Refresca el token si sigue siendo valido.\"\"\"
    valor = self._decode(token)
    return valor is not None
"""

CUERPO_DISTINTO = """
def refresh(self, token: str) -> bool:
    valor = self._decode(token)
    return valor is not None and not valor.expirado
"""


def test_reformatear_no_cambia_el_body_hash() -> None:
    """La propiedad que sostiene P3: `ruff format` no borra la memoria."""
    assert body_hash(ORIGINAL) == body_hash(REFORMATEADA)


def test_los_comentarios_no_cambian_el_body_hash() -> None:
    assert body_hash(ORIGINAL) == body_hash(CON_COMENTARIOS)


def test_el_docstring_no_cambia_el_body_hash() -> None:
    """Documentar mejor una funcion no cambia lo que hace."""
    assert body_hash(ORIGINAL) == body_hash(CON_DOCSTRING)


def test_cambiar_la_logica_si_cambia_el_body_hash() -> None:
    assert body_hash(ORIGINAL) != body_hash(CUERPO_DISTINTO)


def test_renombrar_la_funcion_no_cambia_el_body_hash() -> None:
    """Requisito de la migracion de anclas: el cuerpo es la huella."""
    renombrada = ORIGINAL.replace("def refresh(", "def renew(")
    assert body_hash(ORIGINAL) == body_hash(renombrada)


def test_body_hash_acepta_un_bloque_sin_definicion() -> None:
    assert body_hash("x = 1\ny = 2\n") == body_hash("x = 1\n\n# nota\ny = 2\n")


def test_body_hash_admite_codigo_indentado() -> None:
    assert normalize_body("    x = 1\n") == normalize_body("x = 1\n")


def test_body_hash_falla_con_codigo_invalido() -> None:
    """Preferimos fallar a producir un hash de basura."""
    with pytest.raises(SyntaxError):
        body_hash("def roto(:\n")


# ---------------------------------------------------------------------------
# detect_moves — mitigacion de R2
# ---------------------------------------------------------------------------


def test_detecta_un_renombrado_simple() -> None:
    """Mismo cuerpo, distinta identidad: se migra el ancla, no se invalida."""
    movimientos = detect_moves(
        disappeared=[NodeRef("aaa", "cuerpo1")],
        appeared=[NodeRef("bbb", "cuerpo1")],
    )
    assert movimientos == {"aaa": "bbb"}


def test_no_migra_cuando_el_cuerpo_cambio() -> None:
    movimientos = detect_moves(
        disappeared=[NodeRef("aaa", "cuerpo1")],
        appeared=[NodeRef("bbb", "cuerpo2")],
    )
    assert movimientos == {}


def test_no_migra_cuando_hay_ambiguedad() -> None:
    """Dos candidatos con el mismo cuerpo: migrar seria adivinar."""
    movimientos = detect_moves(
        disappeared=[NodeRef("aaa", "trivial")],
        appeared=[NodeRef("bbb", "trivial"), NodeRef("ccc", "trivial")],
    )
    assert movimientos == {}


def test_no_migra_cuando_desaparecen_varios_iguales() -> None:
    movimientos = detect_moves(
        disappeared=[NodeRef("aaa", "trivial"), NodeRef("bbb", "trivial")],
        appeared=[NodeRef("ccc", "trivial")],
    )
    assert movimientos == {}


def test_migra_solo_los_pares_no_ambiguos() -> None:
    movimientos = detect_moves(
        disappeared=[
            NodeRef("unico_viejo", "cuerpo_unico"),
            NodeRef("ambiguo_a", "cuerpo_repetido"),
            NodeRef("ambiguo_b", "cuerpo_repetido"),
        ],
        appeared=[
            NodeRef("unico_nuevo", "cuerpo_unico"),
            NodeRef("ambiguo_c", "cuerpo_repetido"),
            NodeRef("ambiguo_d", "cuerpo_repetido"),
        ],
    )
    assert movimientos == {"unico_viejo": "unico_nuevo"}


def test_detecta_un_movimiento_real_entre_archivos() -> None:
    """Caso de extremo a extremo: la funcion se muda de modulo."""
    viejo = NodeRef(node_id("app/auth.py", "app.auth.refresh", "function"), body_hash(ORIGINAL))
    nuevo = NodeRef(
        node_id("app/tokens.py", "app.tokens.refresh", "function"),
        body_hash(REFORMATEADA),
    )
    assert viejo.node_id != nuevo.node_id
    assert detect_moves([viejo], [nuevo]) == {viejo.node_id: nuevo.node_id}

"""Recursos de pedido."""

from __future__ import annotations

from tienda.api.recursos_pedidos import (
    cancelar_pedido,
    consultar_pedido,
    crear_pedido,
    listar_pedidos,
)


def cuerpo_valido(**cambios) -> dict:
    peticion = {
        "cliente": "CLI-001",
        "zona": "peninsula",
        "lineas": [{"referencia": "TAZ-010", "cantidad": 12}],
    }
    peticion.update(cambios)
    return peticion


def test_crear_pedido_devuelve_201(contexto):
    codigo, cuerpo = crear_pedido(contexto, cuerpo_valido())
    assert codigo == 201
    assert cuerpo["identificador"] == "PED-0001"
    assert cuerpo["estado"] == "creado"
    assert cuerpo["resumen"]["total"] == "123.42"
    assert cuerpo["resumen"]["descuentos"] == "18.00"


def test_dos_pedidos_seguidos_son_dos_pedidos(contexto):
    _, primero = crear_pedido(contexto, cuerpo_valido())
    _, segundo = crear_pedido(contexto, cuerpo_valido())
    assert primero["identificador"] != segundo["identificador"]
    codigo, cuerpo = listar_pedidos(contexto, "CLI-001")
    assert codigo == 200
    assert len(cuerpo["pedidos"]) == 2


def test_crear_pedido_con_cupon_caducado(contexto):
    # El cupon de verano caduco el 30 de junio y el reloj marca el 15
    # de julio: la peticion se rechaza y no se emite pedido.
    codigo, cuerpo = crear_pedido(contexto, cuerpo_valido(cupon="VERANO10"))
    assert codigo == 400
    assert cuerpo["codigo"] == "cupon_invalido"
    _, listado = listar_pedidos(contexto, "CLI-001")
    assert listado["pedidos"] == []


def test_crear_pedido_con_cupon_vigente(contexto):
    peticion = cuerpo_valido(lineas=[{"referencia": "MOL-002", "cantidad": 2}], cupon="OTONO15")
    codigo, cuerpo = crear_pedido(contexto, peticion)
    assert codigo == 201
    assert cuerpo["resumen"]["total"] == "47.13"


def test_crear_pedido_sin_stock(contexto):
    codigo, cuerpo = crear_pedido(
        contexto, cuerpo_valido(lineas=[{"referencia": "MOL-002", "cantidad": 11}])
    )
    assert codigo == 409
    assert cuerpo["codigo"] == "stock_insuficiente"


def test_crear_pedido_con_cuerpo_invalido(contexto):
    codigo, cuerpo = crear_pedido(contexto, {"cliente": "CLI-001", "zona": "peninsula"})
    assert codigo == 400
    assert cuerpo["codigo"] == "peticion_invalida"


def test_consultar_pedido(contexto):
    _, creado = crear_pedido(contexto, cuerpo_valido())
    codigo, cuerpo = consultar_pedido(contexto, creado["identificador"])
    assert codigo == 200
    assert cuerpo["lineas"] == [{"referencia": "TAZ-010", "cantidad": 12}]


def test_consultar_pedido_inexistente(contexto):
    codigo, cuerpo = consultar_pedido(contexto, "PED-9999")
    assert codigo == 404
    assert cuerpo["codigo"] == "pedido_no_encontrado"


def test_cancelar_pedido(contexto):
    _, creado = crear_pedido(contexto, cuerpo_valido())
    codigo, cuerpo = cancelar_pedido(contexto, creado["identificador"])
    assert codigo == 200
    assert cuerpo["estado"] == "cancelado"
    assert contexto.inventario.disponible("TAZ-010") == 100

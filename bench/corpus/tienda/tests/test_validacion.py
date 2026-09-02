"""Validacion de la peticion de pedido."""

from __future__ import annotations

import pytest
from tienda.api.validacion import validar_crear_pedido
from tienda.compartido.errores import ErrorDeValidacion


def peticion(**cambios) -> dict:
    datos = {
        "cliente": "CLI-001",
        "zona": "peninsula",
        "lineas": [{"referencia": "TAZ-010", "cantidad": 2}],
    }
    datos.update(cambios)
    return datos


def test_peticion_valida():
    validada = validar_crear_pedido(peticion())
    assert validada.cliente == "CLI-001"
    assert validada.como_pares() == (("TAZ-010", 2),)
    assert validada.cupon is None


def test_el_cupon_vacio_se_ignora():
    assert validar_crear_pedido(peticion(cupon="   ")).cupon is None
    assert validar_crear_pedido(peticion(cupon=" OTONO15 ")).cupon == "OTONO15"


def test_faltan_campos_obligatorios():
    with pytest.raises(ErrorDeValidacion):
        validar_crear_pedido({"zona": "peninsula", "lineas": []})
    with pytest.raises(ErrorDeValidacion):
        validar_crear_pedido(peticion(cliente="  "))


def test_pedido_sin_lineas():
    with pytest.raises(ErrorDeValidacion):
        validar_crear_pedido(peticion(lineas=[]))


def test_cantidad_no_entera():
    with pytest.raises(ErrorDeValidacion):
        validar_crear_pedido(peticion(lineas=[{"referencia": "TAZ-010", "cantidad": "2"}]))
    with pytest.raises(ErrorDeValidacion):
        validar_crear_pedido(peticion(lineas=[{"referencia": "TAZ-010", "cantidad": True}]))


def test_cantidad_no_positiva():
    with pytest.raises(ErrorDeValidacion):
        validar_crear_pedido(peticion(lineas=[{"referencia": "TAZ-010", "cantidad": 0}]))


def test_cuerpo_que_no_es_objeto():
    with pytest.raises(ErrorDeValidacion):
        validar_crear_pedido(["TAZ-010"])

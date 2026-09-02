"""Niveles y puntos."""

from __future__ import annotations

from tienda.compartido.dinero import CERO, Dinero
from tienda.dominio.fidelidad import (
    descuento_por_fidelidad,
    nivel_de,
    porcentaje_de,
    puntos_por_compra,
)
from tienda.dominio.modelos import Cliente


def test_nivel_por_puntos():
    assert nivel_de(0) == "bronce"
    assert nivel_de(99) == "bronce"
    assert nivel_de(100) == "plata"
    assert nivel_de(499) == "plata"
    assert nivel_de(500) == "oro"


def test_porcentaje_por_nivel():
    assert porcentaje_de(Cliente("CLI-001", "Ana", 0)) == 0
    assert porcentaje_de(Cliente("CLI-002", "Bruno", 150)) == 3
    assert porcentaje_de(Cliente("CLI-003", "Carla", 620)) == 5
    assert porcentaje_de(None) == 0


def test_descuento_por_fidelidad():
    base = Dinero.desde_texto("100.00")
    assert descuento_por_fidelidad(base, Cliente("CLI-003", "Carla", 620)) == Dinero(500)
    assert descuento_por_fidelidad(base, None) == CERO


def test_puntos_por_compra_solo_cuenta_euros_completos():
    assert puntos_por_compra(Dinero.desde_texto("123.42")) == 123
    assert puntos_por_compra(Dinero.desde_texto("0.99")) == 0

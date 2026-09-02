"""Existencias y reservas."""

from __future__ import annotations

import pytest
from tienda.compartido.errores import ErrorDeValidacion
from tienda.dominio.inventario import Inventario


@pytest.fixture
def inventario() -> Inventario:
    almacen = Inventario()
    almacen.registrar("MOL-002", 10)
    return almacen


def test_registrar_suma_existencias(inventario: Inventario):
    inventario.registrar("MOL-002", 5)
    assert inventario.existencias("MOL-002") == 15
    assert inventario.disponible("MOL-002") == 15


def test_reservar_reduce_lo_disponible_pero_no_las_existencias(inventario: Inventario):
    inventario.reservar("MOL-002", 4)
    assert inventario.existencias("MOL-002") == 10
    assert inventario.reservado("MOL-002") == 4
    assert inventario.disponible("MOL-002") == 6


def test_no_se_puede_reservar_mas_de_lo_disponible(inventario: Inventario):
    assert inventario.reservar("MOL-002", 11) is False
    assert inventario.disponible("MOL-002") == 10


def test_liberar_devuelve_lo_reservado(inventario: Inventario):
    inventario.reservar("MOL-002", 4)
    inventario.liberar("MOL-002", 4)
    assert inventario.disponible("MOL-002") == 10
    assert inventario.reservado("MOL-002") == 0


def test_confirmar_saca_del_almacen(inventario: Inventario):
    inventario.reservar("MOL-002", 4)
    inventario.confirmar("MOL-002", 4)
    assert inventario.existencias("MOL-002") == 6
    assert inventario.reservado("MOL-002") == 0
    assert inventario.disponible("MOL-002") == 6


def test_la_referencia_se_normaliza(inventario: Inventario):
    inventario.reservar("mol-002", 2)
    assert inventario.disponible("MOL-002") == 8


def test_referencia_sin_existencias():
    assert Inventario().disponible("NO-EXISTE") == 0


def test_cantidad_no_positiva(inventario: Inventario):
    with pytest.raises(ErrorDeValidacion):
        inventario.reservar("MOL-002", 0)
    with pytest.raises(ErrorDeValidacion):
        inventario.registrar("MOL-002", -1)

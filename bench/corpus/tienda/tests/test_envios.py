"""Portes."""

from __future__ import annotations

from datetime import date

import pytest
from tienda.compartido.dinero import CERO, Dinero
from tienda.compartido.errores import ZonaDesconocida
from tienda.dominio.envios import (
    buscar_zona,
    coste_envio,
    fecha_entrega,
    kilos_extra,
    peso_total,
)
from tienda.dominio.modelos import LineaPedido, Producto


def test_peso_total(taza: Producto, saco: Producto):
    lineas = (LineaPedido(taza, 3), LineaPedido(saco, 1))
    assert peso_total(lineas) == 6200


def test_kilos_extra_solo_cuenta_lo_que_pasa_del_peso_incluido():
    assert kilos_extra(1500) == 0
    assert kilos_extra(2000) == 0
    assert kilos_extra(2001) == 1
    assert kilos_extra(3000) == 1
    assert kilos_extra(5000) == 3


def test_envio_gratis_por_encima_del_umbral(taza: Producto):
    lineas = (LineaPedido(taza, 12),)
    assert coste_envio("peninsula", lineas, Dinero.desde_texto("102.00")) == CERO


def test_envio_peninsular_de_cinco_kilos(saco: Producto):
    # Tarifa base 4.95 mas 0.50 por cada kilo a partir del tercero.
    lineas = (LineaPedido(saco, 1),)
    assert coste_envio("peninsula", lineas, Dinero.desde_texto("8.00")) == Dinero.desde_texto(
        "6.45"
    )


def test_envio_ligero_paga_solo_la_base(taza: Producto):
    lineas = (LineaPedido(taza, 2),)
    assert coste_envio("peninsula", lineas, Dinero.desde_texto("20.00")) == Dinero.desde_texto(
        "4.95"
    )


def test_cada_zona_tiene_su_tarifa(taza: Producto):
    lineas = (LineaPedido(taza, 1),)
    base = Dinero.desde_texto("10.00")
    assert coste_envio("baleares", lineas, base) == Dinero.desde_texto("7.95")
    assert coste_envio("canarias", lineas, base) == Dinero.desde_texto("12.95")


def test_zona_desconocida():
    with pytest.raises(ZonaDesconocida):
        buscar_zona("laponia")


def test_fecha_de_entrega_por_zona():
    assert fecha_entrega("peninsula", date(2026, 7, 15)) == date(2026, 7, 18)
    assert fecha_entrega("canarias", date(2026, 7, 15)) == date(2026, 7, 22)

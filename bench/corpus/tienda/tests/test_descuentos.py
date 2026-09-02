"""Descuentos por volumen y por cupon."""

from __future__ import annotations

from datetime import date

import pytest
from tienda.compartido.dinero import CERO, Dinero
from tienda.compartido.errores import CuponInvalido
from tienda.dominio.descuentos import (
    buscar_cupon,
    cupon_vigente,
    descuento_por_cupon,
    descuento_por_volumen,
    porcentaje_por_volumen,
)


def test_sin_volumen_no_hay_descuento():
    assert porcentaje_por_volumen(1) == 0
    assert porcentaje_por_volumen(4) == 0
    assert descuento_por_volumen(Dinero.desde_texto("40.00"), 2) == CERO


def test_tramos_por_volumen():
    assert porcentaje_por_volumen(5) == 5
    assert porcentaje_por_volumen(9) == 5
    assert porcentaje_por_volumen(10) == 15
    assert porcentaje_por_volumen(19) == 15
    assert porcentaje_por_volumen(20) == 20


def test_el_tramo_se_alcanza_en_el_minimo_exacto():
    # Diez unidades ya son el tramo del 15%, no el del 5%.
    assert descuento_por_volumen(Dinero.desde_texto("100.00"), 10) == Dinero.desde_texto("15.00")
    assert descuento_por_volumen(Dinero.desde_texto("50.00"), 5) == Dinero.desde_texto("2.50")


def test_buscar_cupon_normaliza_el_codigo():
    assert buscar_cupon("otono15").porcentaje == 15
    assert buscar_cupon(" OTONO15 ").codigo == "OTONO15"


def test_cupon_desconocido():
    with pytest.raises(CuponInvalido):
        buscar_cupon("NO-EXISTE")


def test_cupon_vigente_dentro_de_su_ventana():
    cupon = buscar_cupon("VERANO10")
    assert cupon_vigente(cupon, date(2026, 6, 1))
    assert cupon_vigente(cupon, date(2026, 6, 30))


def test_cupon_caducado_no_esta_vigente():
    cupon = buscar_cupon("VERANO10")
    assert not cupon_vigente(cupon, date(2026, 7, 15))
    assert not cupon_vigente(cupon, date(2026, 5, 31))


def test_descuento_por_cupon_caducado_se_rechaza():
    cupon = buscar_cupon("VERANO10")
    with pytest.raises(CuponInvalido):
        descuento_por_cupon(Dinero.desde_texto("40.00"), cupon, date(2026, 7, 15))


def test_descuento_por_cupon_vigente():
    cupon = buscar_cupon("OTONO15")
    importe = descuento_por_cupon(Dinero.desde_texto("40.00"), cupon, date(2026, 7, 15))
    assert importe == Dinero.desde_texto("6.00")


def test_sin_cupon_no_hay_descuento():
    assert descuento_por_cupon(Dinero.desde_texto("40.00"), None, date(2026, 7, 15)) == CERO

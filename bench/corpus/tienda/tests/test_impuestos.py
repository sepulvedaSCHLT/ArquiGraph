"""Tipos de IVA y cuota."""

from __future__ import annotations

import pytest
from tienda.compartido.dinero import Dinero
from tienda.compartido.errores import ErrorDeValidacion
from tienda.dominio.impuestos import (
    TIPO_GENERAL,
    TIPO_REDUCIDO,
    TIPO_SUPERREDUCIDO,
    con_impuesto,
    cuota,
    validar_tipo,
)


def test_cuota_por_tipo():
    base = Dinero.desde_texto("100.00")
    assert cuota(base, TIPO_GENERAL) == Dinero.desde_texto("21.00")
    assert cuota(base, TIPO_REDUCIDO) == Dinero.desde_texto("10.00")
    assert cuota(base, TIPO_SUPERREDUCIDO) == Dinero.desde_texto("4.00")


def test_cuota_redondea_el_empate_al_alza():
    # 33.33 al tipo general son 6.9993 euros: se cobran 7.00.
    assert cuota(Dinero.desde_texto("33.33"), TIPO_GENERAL) == Dinero.desde_texto("7.00")
    # Los portes peninsulares: 4.95 al 21% son 1.0395 -> 1.04.
    assert cuota(Dinero.desde_texto("4.95"), TIPO_GENERAL) == Dinero.desde_texto("1.04")


def test_con_impuesto_suma_la_cuota():
    assert con_impuesto(Dinero.desde_texto("102.00"), TIPO_GENERAL) == Dinero.desde_texto("123.42")


def test_tipo_no_reconocido():
    with pytest.raises(ErrorDeValidacion):
        validar_tipo(7)
    with pytest.raises(ErrorDeValidacion):
        cuota(Dinero.desde_texto("10.00"), 7)

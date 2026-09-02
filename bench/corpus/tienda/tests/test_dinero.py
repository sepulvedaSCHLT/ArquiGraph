"""Aritmetica de importes."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from tienda.compartido.dinero import CERO, Dinero


def test_desde_texto_guarda_centimos():
    assert Dinero.desde_texto("12.34").centimos == 1234
    assert Dinero.desde_texto("0.05").centimos == 5
    assert Dinero.desde_euros(7).centimos == 700


def test_suma_y_resta():
    assert Dinero(1234) + Dinero(66) == Dinero(1300)
    assert Dinero(1300) - Dinero(1234) == Dinero(66)


def test_multiplicar_es_exacto():
    assert Dinero.desde_texto("10.00").multiplicar(12) == Dinero(12000)
    assert Dinero.desde_texto("2.03").multiplicar(5) == Dinero(1015)


def test_porcentaje_exacto():
    assert Dinero.desde_texto("120.00").porcentaje(15) == Dinero.desde_texto("18.00")
    assert Dinero.desde_texto("100.00").porcentaje(21) == Dinero.desde_texto("21.00")


def test_porcentaje_redondea_el_empate_al_alza():
    # 10.15 al 5% son 0.5075 euros: la factura cobra 0.51, no 0.50.
    assert Dinero.desde_texto("10.15").porcentaje(5) == Dinero(51)
    # 33.33 al 21% son 6.9993: redondea a 7.00.
    assert Dinero.desde_texto("33.33").porcentaje(21) == Dinero(700)


def test_porcentaje_cero_es_cero():
    assert Dinero.desde_texto("99.99").porcentaje(0) == CERO


def test_a_texto():
    assert Dinero(1234).a_texto() == "12.34"
    assert Dinero(5).a_texto() == "0.05"
    assert Dinero(-1234).a_texto() == "-12.34"
    assert str(Dinero(12000)) == "120.00"


def test_orden():
    assert Dinero(100) < Dinero(101)
    assert Dinero(5000) >= Dinero.desde_texto("50.00")
    assert CERO.es_cero()


def test_dinero_es_inmutable():
    with pytest.raises(FrozenInstanceError):
        Dinero(100).centimos = 200

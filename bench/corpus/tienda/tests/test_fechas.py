"""Calendario."""

from __future__ import annotations

from datetime import date

from tienda.compartido.fechas import a_texto, desde_texto, dias_entre, esta_vigente, sumar_dias


def test_sumar_dias():
    assert sumar_dias(date(2026, 7, 15), 3) == date(2026, 7, 18)
    assert sumar_dias(date(2026, 7, 30), 7) == date(2026, 8, 6)


def test_dias_entre():
    assert dias_entre(date(2026, 7, 1), date(2026, 7, 15)) == 14
    assert dias_entre(date(2026, 7, 15), date(2026, 7, 1)) == -14


def test_esta_vigente_incluye_los_extremos():
    desde, hasta = date(2026, 6, 1), date(2026, 6, 30)
    assert esta_vigente(date(2026, 6, 1), desde, hasta)
    assert esta_vigente(date(2026, 6, 30), desde, hasta)
    assert esta_vigente(date(2026, 6, 15), desde, hasta)


def test_esta_vigente_rechaza_fuera_de_rango():
    desde, hasta = date(2026, 6, 1), date(2026, 6, 30)
    assert not esta_vigente(date(2026, 5, 31), desde, hasta)
    assert not esta_vigente(date(2026, 7, 15), desde, hasta)


def test_texto_ida_y_vuelta():
    assert a_texto(date(2026, 7, 15)) == "2026-07-15"
    assert desde_texto("2026-07-15") == date(2026, 7, 15)

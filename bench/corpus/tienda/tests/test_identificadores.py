"""Secuencia de identificadores."""

from __future__ import annotations

from tienda.infraestructura.identificadores import GeneradorSecuencial


def test_empieza_en_uno():
    assert GeneradorSecuencial("PED").siguiente() == "PED-0001"


def test_no_repite_identificadores():
    generador = GeneradorSecuencial("PED")
    emitidos = [generador.siguiente() for _ in range(5)]
    assert emitidos == ["PED-0001", "PED-0002", "PED-0003", "PED-0004", "PED-0005"]
    assert len(set(emitidos)) == 5


def test_cuenta_los_emitidos():
    generador = GeneradorSecuencial("FAC", ancho=6)
    generador.siguiente()
    generador.siguiente()
    assert generador.emitidos() == 2
    assert generador.siguiente() == "FAC-000003"

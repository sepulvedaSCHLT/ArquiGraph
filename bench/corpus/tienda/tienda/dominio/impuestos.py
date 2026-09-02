"""Tipos de IVA y calculo de la cuota.

Tres tipos, como en la factura real. El tipo lo lleva cada producto,
no el pedido: un pedido con un libro y una taza tributa a dos tipos.
"""

from __future__ import annotations

from tienda.compartido.dinero import Dinero
from tienda.compartido.errores import ErrorDeValidacion

__all__ = [
    "TIPOS",
    "TIPO_GENERAL",
    "TIPO_REDUCIDO",
    "TIPO_SUPERREDUCIDO",
    "con_impuesto",
    "cuota",
    "validar_tipo",
]

TIPO_GENERAL = 21
TIPO_REDUCIDO = 10
TIPO_SUPERREDUCIDO = 4

TIPOS = (TIPO_GENERAL, TIPO_REDUCIDO, TIPO_SUPERREDUCIDO)


def validar_tipo(tipo: int) -> None:
    if tipo not in TIPOS:
        raise ErrorDeValidacion(f"tipo de IVA no reconocido: {tipo}")


def cuota(base: Dinero, tipo: int) -> Dinero:
    """IVA que corresponde a una base imponible."""
    validar_tipo(tipo)
    return base.porcentaje(tipo)


def con_impuesto(base: Dinero, tipo: int) -> Dinero:
    """Base mas su IVA."""
    return base + cuota(base, tipo)

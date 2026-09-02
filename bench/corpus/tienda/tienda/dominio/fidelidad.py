"""Niveles de fidelidad y puntos.

El nivel sale de los puntos acumulados y se traduce en un descuento
permanente que se acumula al del cupon.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tienda.compartido.dinero import Dinero

if TYPE_CHECKING:
    from tienda.dominio.modelos import Cliente

__all__ = [
    "DESCUENTO_POR_NIVEL",
    "NIVELES",
    "descuento_por_fidelidad",
    "nivel_de",
    "porcentaje_de",
    "puntos_por_compra",
]

# (nombre, puntos minimos). De mas alto a mas bajo.
NIVELES = (("oro", 500), ("plata", 100), ("bronce", 0))

DESCUENTO_POR_NIVEL = {"oro": 5, "plata": 3, "bronce": 0}


def nivel_de(puntos: int) -> str:
    """Nivel que corresponde a esos puntos acumulados."""
    for nombre, minimo in NIVELES:
        if puntos >= minimo:
            return nombre
    return "bronce"


def porcentaje_de(cliente: Cliente | None) -> int:
    """Descuento permanente del cliente, en porcentaje."""
    if cliente is None:
        return 0
    return DESCUENTO_POR_NIVEL[nivel_de(cliente.puntos)]


def descuento_por_fidelidad(base: Dinero, cliente: Cliente | None) -> Dinero:
    return base.porcentaje(porcentaje_de(cliente))


def puntos_por_compra(total: Dinero) -> int:
    """Un punto por cada euro completo gastado."""
    return total.centimos // 100

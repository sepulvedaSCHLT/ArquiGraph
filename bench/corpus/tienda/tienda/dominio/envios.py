"""Portes: tarifa por zona, peso y umbral de envio gratuito.

La tarifa es una base fija por zona mas un suplemento por cada kilo
--o fraccion-- que pase del peso incluido. Por encima del umbral de
compra el envio no se cobra.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from tienda.compartido.dinero import CERO, Dinero
from tienda.compartido.errores import ZonaDesconocida
from tienda.compartido.fechas import sumar_dias
from tienda.dominio.modelos import LineaPedido

__all__ = [
    "PESO_INCLUIDO_GRAMOS",
    "UMBRAL_ENVIO_GRATIS",
    "ZONAS",
    "Zona",
    "buscar_zona",
    "coste_envio",
    "fecha_entrega",
    "kilos_extra",
    "peso_total",
]

# Peso que ya cubre la tarifa base de cualquier zona.
PESO_INCLUIDO_GRAMOS = 2000

UMBRAL_ENVIO_GRATIS = Dinero.desde_texto("50.00")


@dataclass(frozen=True)
class Zona:
    """Tarifa de una zona de reparto."""

    nombre: str
    base: Dinero
    kilo_extra: Dinero
    dias_entrega: int


ZONAS = {
    "peninsula": Zona("peninsula", Dinero.desde_texto("4.95"), Dinero.desde_texto("0.50"), 3),
    "baleares": Zona("baleares", Dinero.desde_texto("7.95"), Dinero.desde_texto("0.75"), 5),
    "canarias": Zona("canarias", Dinero.desde_texto("12.95"), Dinero.desde_texto("1.20"), 7),
}


def buscar_zona(nombre: str) -> Zona:
    zona = ZONAS.get(nombre.strip().lower())
    if zona is None:
        raise ZonaDesconocida(f"zona de reparto desconocida: {nombre}")
    return zona


def peso_total(lineas: Iterable[LineaPedido]) -> int:
    """Peso del envio en gramos."""
    return sum(linea.producto.peso_gramos * linea.cantidad for linea in lineas)


def kilos_extra(peso_gramos: int) -> int:
    """Kilos que se cobran aparte: los que pasan del peso incluido."""
    exceso = peso_gramos - PESO_INCLUIDO_GRAMOS
    if exceso <= 0:
        return 0
    return math.ceil(exceso / 1000)


def coste_envio(zona: str, lineas: Iterable[LineaPedido], base_imponible: Dinero) -> Dinero:
    """Portes de un pedido. Gratis a partir del umbral de compra."""
    if base_imponible >= UMBRAL_ENVIO_GRATIS:
        return CERO
    tarifa = buscar_zona(zona)
    return tarifa.base + tarifa.kilo_extra.multiplicar(kilos_extra(peso_total(lineas)))


def fecha_entrega(zona: str, dia: date) -> date:
    """Dia estimado de entrega para un pedido hecho el ``dia``."""
    return sumar_dias(dia, buscar_zona(zona).dias_entrega)

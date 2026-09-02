"""Descuentos por volumen y por cupon.

Dos mecanismos independientes que se acumulan:

- El **volumen** se mira linea a linea. Doce unidades de la misma
  referencia descuentan; doce unidades repartidas entre tres
  referencias, no.
- El **cupon** se aplica sobre lo que queda de cada linea despues del
  descuento por volumen, y solo si esta vigente el dia del pedido.
"""

from __future__ import annotations

from datetime import date

from tienda.compartido.dinero import CERO, Dinero
from tienda.compartido.errores import CuponInvalido
from tienda.compartido.fechas import esta_vigente
from tienda.dominio.modelos import Cupon

__all__ = [
    "CUPONES",
    "TRAMOS_POR_VOLUMEN",
    "buscar_cupon",
    "cupon_vigente",
    "descuento_por_cupon",
    "descuento_por_volumen",
    "porcentaje_por_volumen",
]

# (unidades minimas, porcentaje). De mas exigente a menos: se devuelve
# el primero que la cantidad alcanza.
TRAMOS_POR_VOLUMEN = ((20, 20), (10, 15), (5, 5))

CUPONES = {
    "VERANO10": Cupon("VERANO10", 10, date(2026, 6, 1), date(2026, 6, 30)),
    "OTONO15": Cupon("OTONO15", 15, date(2026, 7, 1), date(2026, 9, 30)),
    "BIENVENIDA5": Cupon("BIENVENIDA5", 5, date(2026, 1, 1), date(2026, 12, 31)),
}


def porcentaje_por_volumen(cantidad: int) -> int:
    """Porcentaje que corresponde a llevar ``cantidad`` unidades."""
    for minimo, porcentaje in TRAMOS_POR_VOLUMEN:
        if cantidad >= minimo:
            return porcentaje
    return 0


def descuento_por_volumen(base: Dinero, cantidad: int) -> Dinero:
    """Importe que se descuenta de ``base`` por llevar ``cantidad``."""
    return base.porcentaje(porcentaje_por_volumen(cantidad))


def buscar_cupon(codigo: str) -> Cupon:
    """Cupon con ese codigo, o ``CuponInvalido`` si no existe."""
    cupon = CUPONES.get(codigo.strip().upper())
    if cupon is None:
        raise CuponInvalido(f"cupon desconocido: {codigo}")
    return cupon


def cupon_vigente(cupon: Cupon, dia: date) -> bool:
    """Cierto si el cupon se puede usar ese dia."""
    return esta_vigente(dia, cupon.desde, cupon.hasta)


def descuento_por_cupon(base: Dinero, cupon: Cupon | None, dia: date) -> Dinero:
    """Importe que descuenta el cupon. Rechaza el cupon caducado."""
    if cupon is None:
        return CERO
    if not cupon_vigente(cupon, dia):
        raise CuponInvalido(f"el cupon {cupon.codigo} no esta vigente el {dia.isoformat()}")
    return base.porcentaje(cupon.porcentaje)

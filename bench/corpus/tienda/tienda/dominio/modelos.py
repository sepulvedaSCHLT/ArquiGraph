"""Los datos que se mueven por el dominio.

Todo inmutable. Un pedido no cambia de estado: se sustituye por otro
pedido igual con el estado nuevo, y el repositorio guarda el nuevo. Es
mas facil de razonar y elimina una clase entera de bugs de aliasing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from tienda.compartido.dinero import Dinero

__all__ = [
    "ESTADOS",
    "ESTADO_CANCELADO",
    "ESTADO_CONFIRMADO",
    "ESTADO_CREADO",
    "Cliente",
    "Cupon",
    "LineaPedido",
    "Pedido",
    "Producto",
    "ResumenPrecio",
]

ESTADO_CREADO = "creado"
ESTADO_CONFIRMADO = "confirmado"
ESTADO_CANCELADO = "cancelado"

ESTADOS = (ESTADO_CREADO, ESTADO_CONFIRMADO, ESTADO_CANCELADO)


@dataclass(frozen=True)
class Producto:
    """Una referencia del catalogo."""

    referencia: str
    nombre: str
    categoria: str
    precio: Dinero
    tipo_iva: int
    peso_gramos: int


@dataclass(frozen=True)
class LineaPedido:
    """Un producto y cuantas unidades se llevan de el."""

    producto: Producto
    cantidad: int


@dataclass(frozen=True)
class Cliente:
    """Ficha del cliente. Los puntos deciden su nivel de fidelidad."""

    identificador: str
    nombre: str
    puntos: int = 0


@dataclass(frozen=True)
class Cupon:
    """Un descuento con fecha de caducidad."""

    codigo: str
    porcentaje: int
    desde: date
    hasta: date


@dataclass(frozen=True)
class ResumenPrecio:
    """Desglose economico de un pedido.

    ``base_imponible`` es la suma de las lineas ya descontadas y sin
    impuestos; no incluye los portes. ``impuestos`` si incluye el IVA
    de los portes, porque el transporte tambien tributa.
    """

    subtotal: Dinero
    descuentos: Dinero
    base_imponible: Dinero
    envio: Dinero
    impuestos: Dinero
    total: Dinero


@dataclass(frozen=True)
class Pedido:
    """Un pedido emitido, con su desglose congelado en el momento."""

    identificador: str
    cliente: str
    zona: str
    lineas: tuple[LineaPedido, ...]
    resumen: ResumenPrecio
    creado_el: date
    estado: str = ESTADO_CREADO
    cupon: str | None = field(default=None)

    def unidades(self) -> int:
        return sum(linea.cantidad for linea in self.lineas)

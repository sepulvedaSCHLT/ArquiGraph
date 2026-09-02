"""Calculo de precios: de una linea suelta al desglose del pedido.

El orden importa y es el de la factura:

1. Precio base de la linea (precio por unidades).
2. Descuento por volumen.
3. Descuento por cupon y por fidelidad, sobre lo que queda.
4. IVA, sobre la base ya descontada y al tipo de cada producto.
5. Portes, con su propio IVA al tipo general.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from tienda.compartido.dinero import CERO, Dinero
from tienda.dominio import descuentos, envios, fidelidad, impuestos
from tienda.dominio.modelos import Cliente, Cupon, LineaPedido, ResumenPrecio

__all__ = [
    "calcular_resumen",
    "descuento_de_linea",
    "impuesto_de_linea",
    "precio_base_linea",
    "precio_final_linea",
    "precio_neto_linea",
]


def precio_base_linea(linea: LineaPedido) -> Dinero:
    """Precio de catalogo por las unidades pedidas, sin tocar."""
    return linea.producto.precio.multiplicar(linea.cantidad)


def descuento_de_linea(linea: LineaPedido) -> Dinero:
    """Lo que se descuenta de la linea por llevar tantas unidades."""
    return descuentos.descuento_por_volumen(precio_base_linea(linea), linea.cantidad)


def precio_neto_linea(linea: LineaPedido) -> Dinero:
    """Precio de la linea ya descontado y todavia sin impuestos."""
    return precio_base_linea(linea) - descuento_de_linea(linea)


def impuesto_de_linea(linea: LineaPedido) -> Dinero:
    """IVA de la linea, al tipo del producto y sobre el precio neto."""
    return impuestos.cuota(precio_neto_linea(linea), linea.producto.tipo_iva)


def precio_final_linea(linea: LineaPedido) -> Dinero:
    """Lo que paga el cliente por esta linea, impuestos incluidos."""
    return precio_neto_linea(linea) + impuesto_de_linea(linea)


def calcular_resumen(
    lineas: Iterable[LineaPedido],
    *,
    zona: str,
    dia: date,
    cliente: Cliente | None = None,
    cupon: Cupon | None = None,
) -> ResumenPrecio:
    """Desglose completo del pedido.

    Los descuentos de cupon y fidelidad se reparten linea a linea en vez
    de aplicarse al total: cada linea tributa a su propio tipo de IVA y
    hacerlo de otra forma descuadraria la factura por unos centimos.
    """
    lineas = tuple(lineas)
    subtotal = CERO
    descuento_total = CERO
    base_imponible = CERO
    impuesto_total = CERO

    for linea in lineas:
        base = precio_base_linea(linea)
        neto = precio_neto_linea(linea)
        del_cupon = descuentos.descuento_por_cupon(neto, cupon, dia)
        del_nivel = fidelidad.descuento_por_fidelidad(neto, cliente)
        imponible = neto - del_cupon - del_nivel

        subtotal += base
        descuento_total += (base - neto) + del_cupon + del_nivel
        base_imponible += imponible
        impuesto_total += impuestos.cuota(imponible, linea.producto.tipo_iva)

    envio = envios.coste_envio(zona, lineas, base_imponible)
    impuesto_total += impuestos.cuota(envio, impuestos.TIPO_GENERAL)

    return ResumenPrecio(
        subtotal=subtotal,
        descuentos=descuento_total,
        base_imponible=base_imponible,
        envio=envio,
        impuestos=impuesto_total,
        total=base_imponible + envio + impuesto_total,
    )

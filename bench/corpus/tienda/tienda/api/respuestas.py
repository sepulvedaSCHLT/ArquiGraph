"""Traduccion del dominio a cuerpos de respuesta.

Los importes salen como texto con dos decimales. Devolver centimos
obligaria a cada consumidor a saber que lo son.
"""

from __future__ import annotations

from tienda.compartido.errores import ErrorDeTienda
from tienda.dominio.modelos import Pedido, Producto, ResumenPrecio

__all__ = ["error_a_dict", "pedido_a_dict", "producto_a_dict", "resumen_a_dict"]


def producto_a_dict(producto: Producto, disponibles: int | None = None) -> dict:
    cuerpo = {
        "referencia": producto.referencia,
        "nombre": producto.nombre,
        "categoria": producto.categoria,
        "precio": producto.precio.a_texto(),
        "tipo_iva": producto.tipo_iva,
        "peso_gramos": producto.peso_gramos,
    }
    if disponibles is not None:
        cuerpo["disponibles"] = disponibles
    return cuerpo


def resumen_a_dict(resumen: ResumenPrecio) -> dict:
    return {
        "subtotal": resumen.subtotal.a_texto(),
        "descuentos": resumen.descuentos.a_texto(),
        "base_imponible": resumen.base_imponible.a_texto(),
        "envio": resumen.envio.a_texto(),
        "impuestos": resumen.impuestos.a_texto(),
        "total": resumen.total.a_texto(),
    }


def pedido_a_dict(pedido: Pedido) -> dict:
    return {
        "identificador": pedido.identificador,
        "cliente": pedido.cliente,
        "zona": pedido.zona,
        "estado": pedido.estado,
        "creado_el": pedido.creado_el.isoformat(),
        "cupon": pedido.cupon,
        "lineas": [
            {"referencia": linea.producto.referencia, "cantidad": linea.cantidad}
            for linea in pedido.lineas
        ],
        "resumen": resumen_a_dict(pedido.resumen),
    }


def error_a_dict(error: ErrorDeTienda) -> dict:
    return {"codigo": error.codigo, "mensaje": str(error)}

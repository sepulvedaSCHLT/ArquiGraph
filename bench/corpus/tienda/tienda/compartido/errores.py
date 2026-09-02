"""Jerarquia de errores de la tienda.

Cada error lleva su ``codigo`` y su ``estado_http``. Es la capa ``api``
la que los traduce a respuesta, pero el dato viaja con el error para que
el dominio no tenga que conocer HTTP.
"""

from __future__ import annotations

__all__ = [
    "ClienteNoEncontrado",
    "CuponInvalido",
    "ErrorDeTienda",
    "ErrorDeValidacion",
    "EstadoInvalido",
    "PedidoNoEncontrado",
    "ProductoNoEncontrado",
    "StockInsuficiente",
    "ZonaDesconocida",
]


class ErrorDeTienda(Exception):  # noqa: N818 -- el paquete nombra en espanol
    """Raiz de todo lo que la tienda sabe rechazar."""

    codigo = "error_interno"
    estado_http = 500


class ErrorDeValidacion(ErrorDeTienda):
    codigo = "peticion_invalida"
    estado_http = 400


class ProductoNoEncontrado(ErrorDeTienda):
    codigo = "producto_no_encontrado"
    estado_http = 404


class PedidoNoEncontrado(ErrorDeTienda):
    codigo = "pedido_no_encontrado"
    estado_http = 404


class ClienteNoEncontrado(ErrorDeTienda):
    codigo = "cliente_no_encontrado"
    estado_http = 404


class StockInsuficiente(ErrorDeTienda):
    codigo = "stock_insuficiente"
    estado_http = 409


class CuponInvalido(ErrorDeTienda):
    codigo = "cupon_invalido"
    estado_http = 400


class ZonaDesconocida(ErrorDeTienda):
    codigo = "zona_desconocida"
    estado_http = 400


class EstadoInvalido(ErrorDeTienda):
    codigo = "estado_invalido"
    estado_http = 409

"""Recursos de pedido.

Cada funcion hace lo mismo: valida, delega en el servicio y traduce el
error de dominio en codigo HTTP. Ninguna decide nada de negocio.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tienda.api.respuestas import error_a_dict, pedido_a_dict
from tienda.api.validacion import validar_crear_pedido
from tienda.compartido.errores import ErrorDeTienda
from tienda.dominio.pedidos import ServicioPedidos

if TYPE_CHECKING:
    from tienda.infraestructura.contexto import Contexto

__all__ = ["cancelar_pedido", "consultar_pedido", "crear_pedido", "listar_pedidos"]


def crear_pedido(contexto: Contexto, cuerpo: Any) -> tuple[int, dict]:
    try:
        peticion = validar_crear_pedido(cuerpo)
        pedido = ServicioPedidos(contexto).crear(
            peticion.cliente,
            peticion.zona,
            peticion.como_pares(),
            cupon=peticion.cupon,
        )
    except ErrorDeTienda as error:
        return error.estado_http, error_a_dict(error)
    return 201, pedido_a_dict(pedido)


def consultar_pedido(contexto: Contexto, identificador: str) -> tuple[int, dict]:
    try:
        pedido = ServicioPedidos(contexto).obtener(identificador)
    except ErrorDeTienda as error:
        return error.estado_http, error_a_dict(error)
    return 200, pedido_a_dict(pedido)


def listar_pedidos(contexto: Contexto, cliente: str) -> tuple[int, dict]:
    pedidos = ServicioPedidos(contexto).listar_de_cliente(cliente)
    return 200, {"pedidos": [pedido_a_dict(p) for p in pedidos]}


def cancelar_pedido(contexto: Contexto, identificador: str) -> tuple[int, dict]:
    try:
        pedido = ServicioPedidos(contexto).cancelar(identificador)
    except ErrorDeTienda as error:
        return error.estado_http, error_a_dict(error)
    return 200, pedido_a_dict(pedido)

"""Recursos de catalogo."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tienda.api.respuestas import error_a_dict, producto_a_dict
from tienda.compartido.errores import ErrorDeTienda
from tienda.dominio import catalogo

if TYPE_CHECKING:
    from tienda.infraestructura.contexto import Contexto

__all__ = ["buscar_productos", "consultar_producto", "listar_productos"]


def listar_productos(contexto: Contexto) -> tuple[int, dict]:
    productos = catalogo.listar_productos(contexto)
    return 200, {"productos": [producto_a_dict(p) for p in productos]}


def consultar_producto(contexto: Contexto, referencia: str) -> tuple[int, dict]:
    try:
        producto = catalogo.obtener_producto(contexto, referencia)
        disponibles = catalogo.disponibilidad(contexto, referencia)
    except ErrorDeTienda as error:
        return error.estado_http, error_a_dict(error)
    return 200, producto_a_dict(producto, disponibles)


def buscar_productos(contexto: Contexto, texto: str = "", categoria: str = "") -> tuple[int, dict]:
    if categoria:
        productos = catalogo.buscar_por_categoria(contexto, categoria)
    elif texto:
        productos = catalogo.buscar_por_texto(contexto, texto)
    else:
        productos = catalogo.listar_productos(contexto)
    return 200, {"productos": [producto_a_dict(p) for p in productos]}

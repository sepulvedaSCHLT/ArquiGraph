"""Consultas de catalogo.

Es la puerta que usa la capa ``api`` para leer productos: nunca toca el
repositorio directamente, porque la disponibilidad no sale del
repositorio sino del inventario.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tienda.dominio.modelos import Producto

if TYPE_CHECKING:
    from tienda.infraestructura.contexto import Contexto

__all__ = [
    "buscar_por_categoria",
    "buscar_por_texto",
    "disponibilidad",
    "listar_productos",
    "obtener_producto",
]


def obtener_producto(contexto: Contexto, referencia: str) -> Producto:
    """Producto por referencia. Lanza si no esta en el catalogo."""
    return contexto.productos.obtener(referencia)


def listar_productos(contexto: Contexto) -> list[Producto]:
    return contexto.productos.listar()


def buscar_por_categoria(contexto: Contexto, categoria: str) -> list[Producto]:
    objetivo = categoria.strip().lower()
    return [p for p in listar_productos(contexto) if p.categoria.lower() == objetivo]


def buscar_por_texto(contexto: Contexto, texto: str) -> list[Producto]:
    objetivo = texto.strip().lower()
    if not objetivo:
        return []
    return [p for p in listar_productos(contexto) if objetivo in p.nombre.lower()]


def disponibilidad(contexto: Contexto, referencia: str) -> int:
    """Unidades que se pueden comprar ahora mismo de esa referencia."""
    producto = obtener_producto(contexto, referencia)
    return contexto.inventario.disponible(producto.referencia)

"""Acceso a productos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tienda.compartido.errores import ProductoNoEncontrado
from tienda.infraestructura.almacen import AlmacenEnMemoria

if TYPE_CHECKING:
    from tienda.dominio.modelos import Producto

__all__ = ["RepositorioProductos"]


class RepositorioProductos:
    """Los productos del catalogo, indexados por referencia."""

    def __init__(self) -> None:
        self._almacen: AlmacenEnMemoria[Producto] = AlmacenEnMemoria()

    def guardar(self, producto: Producto) -> None:
        self._almacen.guardar(producto.referencia, producto)

    def buscar(self, referencia: str) -> Producto | None:
        """Devuelve el producto o ``None``. No lanza."""
        return self._almacen.obtener(referencia)

    def obtener(self, referencia: str) -> Producto:
        """Devuelve el producto o lanza ``ProductoNoEncontrado``."""
        producto = self.buscar(referencia)
        if producto is None:
            raise ProductoNoEncontrado(f"no existe el producto {referencia}")
        return producto

    def listar(self) -> list[Producto]:
        return self._almacen.listar()

    def __len__(self) -> int:
        return len(self._almacen)

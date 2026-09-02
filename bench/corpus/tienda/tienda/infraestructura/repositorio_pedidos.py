"""Acceso a pedidos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tienda.compartido.errores import PedidoNoEncontrado
from tienda.infraestructura.almacen import AlmacenEnMemoria

if TYPE_CHECKING:
    from tienda.dominio.modelos import Pedido

__all__ = ["RepositorioPedidos"]


class RepositorioPedidos:
    """Los pedidos emitidos, indexados por identificador."""

    def __init__(self) -> None:
        self._almacen: AlmacenEnMemoria[Pedido] = AlmacenEnMemoria()

    def guardar(self, pedido: Pedido) -> None:
        self._almacen.guardar(pedido.identificador, pedido)

    def buscar(self, identificador: str) -> Pedido | None:
        return self._almacen.obtener(identificador)

    def obtener(self, identificador: str) -> Pedido:
        pedido = self.buscar(identificador)
        if pedido is None:
            raise PedidoNoEncontrado(f"no existe el pedido {identificador}")
        return pedido

    def listar(self) -> list[Pedido]:
        return self._almacen.listar()

    def de_cliente(self, cliente: str) -> list[Pedido]:
        clave = AlmacenEnMemoria.normalizar(cliente)
        return [p for p in self.listar() if AlmacenEnMemoria.normalizar(p.cliente) == clave]

    def __len__(self) -> int:
        return len(self._almacen)

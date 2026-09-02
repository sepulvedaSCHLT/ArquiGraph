"""Acceso a clientes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tienda.compartido.errores import ClienteNoEncontrado
from tienda.infraestructura.almacen import AlmacenEnMemoria

if TYPE_CHECKING:
    from tienda.dominio.modelos import Cliente

__all__ = ["RepositorioClientes"]


class RepositorioClientes:
    """La ficha de cada cliente, indexada por identificador."""

    def __init__(self) -> None:
        self._almacen: AlmacenEnMemoria[Cliente] = AlmacenEnMemoria()

    def guardar(self, cliente: Cliente) -> None:
        self._almacen.guardar(cliente.identificador, cliente)

    def buscar(self, identificador: str) -> Cliente | None:
        return self._almacen.obtener(identificador)

    def obtener(self, identificador: str) -> Cliente:
        cliente = self.buscar(identificador)
        if cliente is None:
            raise ClienteNoEncontrado(f"no existe el cliente {identificador}")
        return cliente

    def listar(self) -> list[Cliente]:
        return self._almacen.listar()

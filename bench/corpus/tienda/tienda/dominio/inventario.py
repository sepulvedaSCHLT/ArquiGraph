"""Existencias y reservas.

Un pedido reserva antes de cobrar y confirma al cerrarse. Lo disponible
es lo que hay menos lo que otros pedidos ya han apartado.
"""

from __future__ import annotations

from tienda.compartido.errores import ErrorDeValidacion
from tienda.infraestructura.almacen import AlmacenEnMemoria

__all__ = ["Inventario"]


class Inventario:
    """Existencias por referencia, con reservas en curso."""

    def __init__(self) -> None:
        self._existencias: dict[str, int] = {}
        self._reservado: dict[str, int] = {}

    @staticmethod
    def _clave(referencia: str) -> str:
        return AlmacenEnMemoria.normalizar(referencia)

    def registrar(self, referencia: str, unidades: int) -> None:
        """Da de alta o repone existencias."""
        if unidades < 0:
            raise ErrorDeValidacion("las unidades no pueden ser negativas")
        clave = self._clave(referencia)
        self._existencias[clave] = self._existencias.get(clave, 0) + unidades
        self._reservado.setdefault(clave, 0)

    def existencias(self, referencia: str) -> int:
        return self._existencias.get(self._clave(referencia), 0)

    def reservado(self, referencia: str) -> int:
        return self._reservado.get(self._clave(referencia), 0)

    def disponible(self, referencia: str) -> int:
        """Unidades que todavia se pueden comprometer."""
        return self.existencias(referencia) - self.reservado(referencia)

    def reservar(self, referencia: str, cantidad: int) -> bool:
        """Aparta unidades. Devuelve si la reserva se pudo hacer."""
        if cantidad <= 0:
            raise ErrorDeValidacion("la cantidad reservada debe ser positiva")
        if cantidad > self.disponible(referencia):
            return False
        clave = self._clave(referencia)
        self._reservado[clave] = self._reservado.get(clave, 0) + cantidad
        return True

    def liberar(self, referencia: str, cantidad: int) -> None:
        """Deshace una reserva que no llego a cobrarse."""
        clave = self._clave(referencia)
        self._reservado[clave] = max(0, self._reservado.get(clave, 0) - cantidad)

    def confirmar(self, referencia: str, cantidad: int) -> None:
        """Convierte una reserva en salida real de almacen."""
        clave = self._clave(referencia)
        self._reservado[clave] = max(0, self._reservado.get(clave, 0) - cantidad)
        self._existencias[clave] = max(0, self._existencias.get(clave, 0) - cantidad)

"""Almacen clave-valor en memoria.

Ocupa el lugar de la base de datos. Las claves --referencias de
producto, identificadores de pedido-- se normalizan al guardar y al
consultar: en una tienda real llegan del exterior con la caja cambiada
y con espacios alrededor, y ``CAF-001`` y ``caf-001`` son el mismo
producto.
"""

from __future__ import annotations

__all__ = ["AlmacenEnMemoria"]


class AlmacenEnMemoria[T]:
    """Diccionario con claves normalizadas y orden de insercion estable."""

    def __init__(self) -> None:
        self._datos: dict[str, T] = {}

    @staticmethod
    def normalizar(clave: str) -> str:
        """Forma canonica de una clave: sin espacios y en mayusculas."""
        return clave.strip().upper()

    def guardar(self, clave: str, valor: T) -> None:
        self._datos[self.normalizar(clave)] = valor

    def obtener(self, clave: str) -> T | None:
        return self._datos.get(self.normalizar(clave))

    def existe(self, clave: str) -> bool:
        return self.normalizar(clave) in self._datos

    def borrar(self, clave: str) -> None:
        self._datos.pop(self.normalizar(clave), None)

    def listar(self) -> list[T]:
        return list(self._datos.values())

    def claves(self) -> list[str]:
        return list(self._datos)

    def __len__(self) -> int:
        return len(self._datos)

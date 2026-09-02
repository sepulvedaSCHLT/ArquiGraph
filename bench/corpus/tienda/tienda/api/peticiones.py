"""Formas validadas de lo que entra por la api.

Que estas clases existan es lo que permite que ``validacion`` sea el
unico sitio donde se mira un diccionario crudo.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PeticionCrearPedido", "PeticionLinea"]


@dataclass(frozen=True)
class PeticionLinea:
    referencia: str
    cantidad: int


@dataclass(frozen=True)
class PeticionCrearPedido:
    cliente: str
    zona: str
    lineas: tuple[PeticionLinea, ...]
    cupon: str | None = None

    def como_pares(self) -> tuple[tuple[str, int], ...]:
        """Lo que el servicio de pedidos espera recibir."""
        return tuple((linea.referencia, linea.cantidad) for linea in self.lineas)

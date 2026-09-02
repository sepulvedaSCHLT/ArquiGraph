"""El reloj de la aplicacion.

Nadie llama a ``date.today()`` en este paquete. El dia entra por aqui y
se inyecta, que es lo que permite fijar el calendario en los tests y
que una tarea del banco produzca siempre el mismo resultado.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from tienda.compartido.fechas import sumar_dias

__all__ = ["Reloj", "RelojFijo"]


class Reloj(Protocol):
    """Lo unico que el dominio necesita saber del tiempo."""

    def hoy(self) -> date:
        """Dia actual segun la aplicacion."""
        ...


class RelojFijo:
    """Reloj que solo avanza cuando alguien se lo pide."""

    def __init__(self, dia: date) -> None:
        self._dia = dia

    def hoy(self) -> date:
        return self._dia

    def avanzar(self, dias: int) -> None:
        self._dia = sumar_dias(self._dia, dias)

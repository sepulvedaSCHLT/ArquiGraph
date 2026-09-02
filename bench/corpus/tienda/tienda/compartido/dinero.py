"""Aritmetica de dinero en centimos enteros.

Un ``float`` no representa 0.10 de forma exacta, y sumar mil lineas de
pedido con ``float`` acaba en un descuadre de centimos que nadie sabe
explicar. Aqui el importe es un entero de centimos y las operaciones que
no son exactas --los porcentajes-- pasan por ``Decimal`` con redondeo
al alza en el empate, que es el criterio de la factura.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

__all__ = ["CERO", "Dinero"]

_CIEN = Decimal(100)
_UNIDAD = Decimal(1)


def _redondear(valor: Decimal) -> int:
    """Convierte a centimos enteros redondeando el empate hacia arriba."""
    return int(valor.quantize(_UNIDAD, rounding=ROUND_HALF_UP))


@dataclass(frozen=True, order=True)
class Dinero:
    """Importe expresado en centimos. Inmutable y comparable."""

    centimos: int

    @classmethod
    def desde_texto(cls, texto: str) -> Dinero:
        """Construye desde ``"12.34"``. Nunca desde un ``float``."""
        return cls(_redondear(Decimal(texto) * _CIEN))

    @classmethod
    def desde_euros(cls, euros: int) -> Dinero:
        return cls(euros * 100)

    def __add__(self, otro: Dinero) -> Dinero:
        return Dinero(self.centimos + otro.centimos)

    def __sub__(self, otro: Dinero) -> Dinero:
        return Dinero(self.centimos - otro.centimos)

    def multiplicar(self, unidades: int) -> Dinero:
        """Repite el importe ``unidades`` veces. Exacto, sin redondeo."""
        return Dinero(self.centimos * unidades)

    def porcentaje(self, tipo: int) -> Dinero:
        """Parte de este importe que representa el ``tipo`` por ciento."""
        return Dinero(_redondear(Decimal(self.centimos) * Decimal(tipo) / _CIEN))

    def es_cero(self) -> bool:
        return self.centimos == 0

    def a_texto(self) -> str:
        """Representacion con dos decimales: ``"12.34"``."""
        signo = "-" if self.centimos < 0 else ""
        unidades, resto = divmod(abs(self.centimos), 100)
        return f"{signo}{unidades}.{resto:02d}"

    def __str__(self) -> str:
        return self.a_texto()


CERO = Dinero(0)

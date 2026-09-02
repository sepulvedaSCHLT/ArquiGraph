"""Generacion de identificadores.

Una secuencia, no un UUID: el banco necesita que dos ejecuciones del
mismo caso produzcan los mismos identificadores para poder compararlas.
"""

from __future__ import annotations

__all__ = ["GeneradorSecuencial"]


class GeneradorSecuencial:
    """Emite ``PREFIJO-0001``, ``PREFIJO-0002``, ... sin repetir."""

    def __init__(self, prefijo: str, ancho: int = 4) -> None:
        self.prefijo = prefijo
        self.ancho = ancho
        self._contador = 0

    def siguiente(self) -> str:
        self._contador += 1
        return f"{self.prefijo}-{self._contador:0{self.ancho}d}"

    def emitidos(self) -> int:
        return self._contador

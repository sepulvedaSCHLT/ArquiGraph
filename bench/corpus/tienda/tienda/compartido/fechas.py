"""Utilidades de calendario.

Ninguna funcion de aqui pregunta que dia es hoy. El dia entra siempre
como argumento y sale del reloj de ``infraestructura``: es lo que hace
que los tests del corpus sean deterministas.
"""

from __future__ import annotations

from datetime import date, timedelta

__all__ = ["a_texto", "desde_texto", "dias_entre", "esta_vigente", "sumar_dias"]


def sumar_dias(dia: date, dias: int) -> date:
    return dia + timedelta(days=dias)


def dias_entre(inicio: date, fin: date) -> int:
    """Dias naturales de ``inicio`` a ``fin``. Negativo si van al reves."""
    return (fin - inicio).days


def esta_vigente(dia: date, desde: date, hasta: date) -> bool:
    """Cierto si ``dia`` cae dentro del intervalo, extremos incluidos."""
    return desde <= dia <= hasta


def a_texto(dia: date) -> str:
    return dia.isoformat()


def desde_texto(texto: str) -> date:
    return date.fromisoformat(texto)

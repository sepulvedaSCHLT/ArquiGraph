"""Validacion de lo que llega por la api.

Solo forma: que los campos esten, que sean del tipo esperado y que los
numeros sean positivos. Si algo existe o no --un producto, un cupon--
lo decide el dominio, no esto.
"""

from __future__ import annotations

from typing import Any

from tienda.api.peticiones import PeticionCrearPedido, PeticionLinea
from tienda.compartido.errores import ErrorDeValidacion

__all__ = ["texto_obligatorio", "validar_crear_pedido", "validar_linea"]


def texto_obligatorio(datos: dict[str, Any], campo: str) -> str:
    valor = datos.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorDeValidacion(f"falta el campo obligatorio '{campo}'")
    return valor.strip()


def validar_linea(datos: Any) -> PeticionLinea:
    if not isinstance(datos, dict):
        raise ErrorDeValidacion("cada linea debe ser un objeto")
    referencia = texto_obligatorio(datos, "referencia")
    cantidad = datos.get("cantidad")
    if not isinstance(cantidad, int) or isinstance(cantidad, bool):
        raise ErrorDeValidacion("la cantidad debe ser un entero")
    if cantidad <= 0:
        raise ErrorDeValidacion("la cantidad debe ser mayor que cero")
    return PeticionLinea(referencia, cantidad)


def validar_crear_pedido(datos: Any) -> PeticionCrearPedido:
    if not isinstance(datos, dict):
        raise ErrorDeValidacion("el cuerpo debe ser un objeto")
    cliente = texto_obligatorio(datos, "cliente")
    zona = texto_obligatorio(datos, "zona")
    lineas = datos.get("lineas")
    if not isinstance(lineas, list) or not lineas:
        raise ErrorDeValidacion("el pedido necesita al menos una linea")
    cupon = datos.get("cupon")
    if cupon is not None and not isinstance(cupon, str):
        raise ErrorDeValidacion("el cupon debe ser una cadena")
    return PeticionCrearPedido(
        cliente=cliente,
        zona=zona,
        lineas=tuple(validar_linea(linea) for linea in lineas),
        cupon=cupon.strip() if isinstance(cupon, str) and cupon.strip() else None,
    )

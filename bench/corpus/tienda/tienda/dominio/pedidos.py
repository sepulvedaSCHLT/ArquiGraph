"""El servicio de pedidos: lo unico que orquesta.

Reserva inventario, pide el desglose a ``precios``, emite identificador
y guarda. Si algo falla despues de reservar --un cupon caducado, por
ejemplo-- suelta lo reservado antes de propagar el error: dejar stock
apartado por un pedido que no existe es peor que el propio fallo.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import TYPE_CHECKING

from tienda.compartido.errores import EstadoInvalido, StockInsuficiente
from tienda.dominio import descuentos, precios
from tienda.dominio.modelos import (
    ESTADO_CANCELADO,
    ESTADO_CONFIRMADO,
    ESTADO_CREADO,
    LineaPedido,
    Pedido,
)

if TYPE_CHECKING:
    from tienda.infraestructura.contexto import Contexto

__all__ = ["ServicioPedidos"]


class ServicioPedidos:
    """Casos de uso de pedido sobre un contexto ya montado."""

    def __init__(self, contexto: Contexto) -> None:
        self._contexto = contexto

    def crear(
        self,
        cliente: str,
        zona: str,
        unidades_por_referencia: Iterable[tuple[str, int]],
        cupon: str | None = None,
    ) -> Pedido:
        ficha = self._contexto.clientes.obtener(cliente)
        lineas = tuple(
            LineaPedido(self._contexto.productos.obtener(referencia), cantidad)
            for referencia, cantidad in unidades_por_referencia
        )
        reservadas: list[LineaPedido] = []
        try:
            for linea in lineas:
                if not self._contexto.inventario.reservar(
                    linea.producto.referencia, linea.cantidad
                ):
                    raise StockInsuficiente(
                        f"no hay {linea.cantidad} unidades de {linea.producto.referencia}"
                    )
                reservadas.append(linea)

            resumen = precios.calcular_resumen(
                lineas,
                zona=zona,
                dia=self._contexto.reloj.hoy(),
                cliente=ficha,
                cupon=descuentos.buscar_cupon(cupon) if cupon else None,
            )
        except Exception:
            self._soltar(reservadas)
            raise

        pedido = Pedido(
            identificador=self._contexto.identificadores.siguiente(),
            cliente=ficha.identificador,
            zona=zona,
            lineas=lineas,
            resumen=resumen,
            creado_el=self._contexto.reloj.hoy(),
            cupon=cupon,
        )
        self._contexto.pedidos.guardar(pedido)
        return pedido

    def obtener(self, identificador: str) -> Pedido:
        return self._contexto.pedidos.obtener(identificador)

    def listar_de_cliente(self, cliente: str) -> list[Pedido]:
        return self._contexto.pedidos.de_cliente(cliente)

    def confirmar(self, identificador: str) -> Pedido:
        """Cierra el pedido y saca del almacen lo que tenia reservado."""
        pedido = self.obtener(identificador)
        if pedido.estado != ESTADO_CREADO:
            raise EstadoInvalido(f"el pedido {identificador} ya esta {pedido.estado}")
        for linea in pedido.lineas:
            self._contexto.inventario.confirmar(linea.producto.referencia, linea.cantidad)
        return self._guardar(replace(pedido, estado=ESTADO_CONFIRMADO))

    def cancelar(self, identificador: str) -> Pedido:
        """Anula el pedido y devuelve al almacen lo reservado."""
        pedido = self.obtener(identificador)
        if pedido.estado == ESTADO_CANCELADO:
            raise EstadoInvalido(f"el pedido {identificador} ya esta cancelado")
        if pedido.estado == ESTADO_CREADO:
            self._soltar(pedido.lineas)
        return self._guardar(replace(pedido, estado=ESTADO_CANCELADO))

    def _soltar(self, lineas: Iterable[LineaPedido]) -> None:
        for linea in lineas:
            self._contexto.inventario.liberar(linea.producto.referencia, linea.cantidad)

    def _guardar(self, pedido: Pedido) -> Pedido:
        self._contexto.pedidos.guardar(pedido)
        return pedido

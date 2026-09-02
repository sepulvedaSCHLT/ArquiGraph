"""Servicio de pedidos."""

from __future__ import annotations

import pytest
from tienda.compartido.dinero import Dinero
from tienda.compartido.errores import (
    ClienteNoEncontrado,
    CuponInvalido,
    EstadoInvalido,
    PedidoNoEncontrado,
    ProductoNoEncontrado,
    StockInsuficiente,
)
from tienda.dominio.modelos import ESTADO_CANCELADO, ESTADO_CONFIRMADO, ESTADO_CREADO
from tienda.dominio.pedidos import ServicioPedidos


@pytest.fixture
def servicio(contexto) -> ServicioPedidos:
    return ServicioPedidos(contexto)


def test_crear_pedido(servicio: ServicioPedidos):
    pedido = servicio.crear("CLI-001", "peninsula", [("TAZ-010", 12)])
    assert pedido.identificador == "PED-0001"
    assert pedido.estado == ESTADO_CREADO
    assert pedido.resumen.total == Dinero.desde_texto("123.42")
    assert pedido.unidades() == 12


def test_cada_pedido_recibe_su_identificador(servicio: ServicioPedidos):
    primero = servicio.crear("CLI-001", "peninsula", [("TAZ-010", 1)])
    segundo = servicio.crear("CLI-001", "peninsula", [("TAZ-010", 1)])
    assert primero.identificador != segundo.identificador
    assert len(servicio.listar_de_cliente("CLI-001")) == 2


def test_crear_pedido_reserva_inventario(servicio: ServicioPedidos, contexto):
    servicio.crear("CLI-001", "peninsula", [("MOL-002", 4)])
    assert contexto.inventario.disponible("MOL-002") == 6
    assert contexto.inventario.existencias("MOL-002") == 10


def test_pedido_que_agota_las_existencias_se_acepta(servicio: ServicioPedidos, contexto):
    # Quedan 10 unidades y se piden exactamente 10: el pedido es valido
    # y deja el inventario a cero.
    pedido = servicio.crear("CLI-001", "peninsula", [("MOL-002", 10)])
    assert pedido.identificador == "PED-0001"
    assert contexto.inventario.disponible("MOL-002") == 0
    assert pedido.resumen.total == Dinero.desde_texto("205.70")


def test_pedido_por_encima_de_las_existencias_se_rechaza(servicio: ServicioPedidos, contexto):
    with pytest.raises(StockInsuficiente):
        servicio.crear("CLI-001", "peninsula", [("MOL-002", 11)])
    assert contexto.inventario.disponible("MOL-002") == 10


def test_un_fallo_no_deja_stock_reservado(servicio: ServicioPedidos, contexto):
    with pytest.raises(StockInsuficiente):
        servicio.crear("CLI-001", "peninsula", [("TAZ-010", 2), ("MOL-002", 11)])
    assert contexto.inventario.disponible("TAZ-010") == 100
    assert contexto.inventario.disponible("MOL-002") == 10


def test_cupon_caducado_no_deja_stock_reservado(servicio: ServicioPedidos, contexto):
    with pytest.raises(CuponInvalido):
        servicio.crear("CLI-001", "peninsula", [("TAZ-010", 2)], cupon="VERANO10")
    assert contexto.inventario.disponible("TAZ-010") == 100


def test_pedido_con_cupon_vigente(servicio: ServicioPedidos):
    pedido = servicio.crear("CLI-001", "peninsula", [("MOL-002", 2)], cupon="OTONO15")
    assert pedido.cupon == "OTONO15"
    assert pedido.resumen.total == Dinero.desde_texto("47.13")


def test_el_nivel_del_cliente_descuenta(servicio: ServicioPedidos):
    pedido = servicio.crear("CLI-003", "peninsula", [("TAZ-010", 12)])
    assert pedido.resumen.total == Dinero.desde_texto("117.25")


def test_cliente_desconocido(servicio: ServicioPedidos):
    with pytest.raises(ClienteNoEncontrado):
        servicio.crear("CLI-999", "peninsula", [("TAZ-010", 1)])


def test_producto_desconocido(servicio: ServicioPedidos):
    with pytest.raises(ProductoNoEncontrado):
        servicio.crear("CLI-001", "peninsula", [("NO-EXISTE", 1)])


def test_confirmar_saca_del_almacen(servicio: ServicioPedidos, contexto):
    pedido = servicio.crear("CLI-001", "peninsula", [("MOL-002", 4)])
    confirmado = servicio.confirmar(pedido.identificador)
    assert confirmado.estado == ESTADO_CONFIRMADO
    assert contexto.inventario.existencias("MOL-002") == 6
    assert contexto.inventario.disponible("MOL-002") == 6


def test_no_se_confirma_dos_veces(servicio: ServicioPedidos):
    pedido = servicio.crear("CLI-001", "peninsula", [("MOL-002", 1)])
    servicio.confirmar(pedido.identificador)
    with pytest.raises(EstadoInvalido):
        servicio.confirmar(pedido.identificador)


def test_cancelar_devuelve_el_stock(servicio: ServicioPedidos, contexto):
    pedido = servicio.crear("CLI-001", "peninsula", [("MOL-002", 4)])
    cancelado = servicio.cancelar(pedido.identificador)
    assert cancelado.estado == ESTADO_CANCELADO
    assert contexto.inventario.disponible("MOL-002") == 10


def test_pedido_desconocido(servicio: ServicioPedidos):
    with pytest.raises(PedidoNoEncontrado):
        servicio.obtener("PED-9999")

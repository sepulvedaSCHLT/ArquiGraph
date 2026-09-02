"""Precio de linea y desglose del pedido."""

from __future__ import annotations

from datetime import date

import pytest
from tienda.compartido.dinero import CERO, Dinero
from tienda.compartido.errores import CuponInvalido
from tienda.dominio.descuentos import buscar_cupon
from tienda.dominio.modelos import Cliente, LineaPedido, Producto
from tienda.dominio.precios import (
    calcular_resumen,
    descuento_de_linea,
    impuesto_de_linea,
    precio_base_linea,
    precio_final_linea,
    precio_neto_linea,
)


def test_precio_base_sin_descuento(taza: Producto):
    # Tres tazas de 10.00: el precio de catalogo por las unidades.
    assert precio_base_linea(LineaPedido(taza, 3)) == Dinero.desde_texto("30.00")
    assert descuento_de_linea(LineaPedido(taza, 3)) == CERO
    assert precio_neto_linea(LineaPedido(taza, 3)) == Dinero.desde_texto("30.00")


def test_precio_final_sin_descuento(taza: Producto):
    # 30.00 al 21% son 36.30.
    assert precio_final_linea(LineaPedido(taza, 3)) == Dinero.desde_texto("36.30")


def test_descuento_por_volumen_de_la_linea(taza: Producto):
    linea = LineaPedido(taza, 12)
    assert precio_base_linea(linea) == Dinero.desde_texto("120.00")
    assert descuento_de_linea(linea) == Dinero.desde_texto("18.00")
    assert precio_neto_linea(linea) == Dinero.desde_texto("102.00")


def test_iva_sobre_precio_con_descuento(taza: Producto):
    # Doce unidades de 10.00 con el 15% por volumen: la base imponible
    # son 102.00, no 120.00, y el IVA se calcula sobre ella.
    linea = LineaPedido(taza, 12)
    assert impuesto_de_linea(linea) == Dinero.desde_texto("21.42")
    assert precio_final_linea(linea) == Dinero.desde_texto("123.42")


def test_descuento_de_linea_redondea_al_alza(filtros: Producto):
    # Cinco filtros de 2.03 son 10.15; el 5% son 0.5075 -> 0.51.
    linea = LineaPedido(filtros, 5)
    assert precio_base_linea(linea) == Dinero.desde_texto("10.15")
    assert descuento_de_linea(linea) == Dinero.desde_texto("0.51")


def test_cada_producto_tributa_a_su_tipo(taza: Producto, saco: Producto):
    assert impuesto_de_linea(LineaPedido(taza, 1)) == Dinero.desde_texto("2.10")
    assert impuesto_de_linea(LineaPedido(saco, 1)) == Dinero.desde_texto("0.80")


def test_resumen_de_pedido_con_envio_gratis(taza: Producto, dia: date):
    resumen = calcular_resumen((LineaPedido(taza, 12),), zona="peninsula", dia=dia)
    assert resumen.subtotal == Dinero.desde_texto("120.00")
    assert resumen.descuentos == Dinero.desde_texto("18.00")
    assert resumen.base_imponible == Dinero.desde_texto("102.00")
    assert resumen.envio == CERO
    assert resumen.impuestos == Dinero.desde_texto("21.42")
    assert resumen.total == Dinero.desde_texto("123.42")


def test_resumen_en_el_minimo_del_tramo(taza: Producto, dia: date):
    # Diez unidades de 10.00: 15% de descuento, 85.00 de base, 102.85.
    resumen = calcular_resumen((LineaPedido(taza, 10),), zona="peninsula", dia=dia)
    assert resumen.descuentos == Dinero.desde_texto("15.00")
    assert resumen.base_imponible == Dinero.desde_texto("85.00")
    assert resumen.total == Dinero.desde_texto("102.85")


def test_resumen_con_portes_y_su_iva(saco: Producto, dia: date):
    # Un saco de 8.00 al 10% y 5 kg a peninsula: portes 6.45 mas su IVA.
    resumen = calcular_resumen((LineaPedido(saco, 1),), zona="peninsula", dia=dia)
    assert resumen.base_imponible == Dinero.desde_texto("8.00")
    assert resumen.envio == Dinero.desde_texto("6.45")
    assert resumen.impuestos == Dinero.desde_texto("2.15")
    assert resumen.total == Dinero.desde_texto("16.60")


def test_resumen_con_cupon_vigente(dia: date):
    molinillo = Producto("MOL-002", "Molinillo", "menaje", Dinero.desde_texto("20.00"), 21, 800)
    resumen = calcular_resumen(
        (LineaPedido(molinillo, 2),),
        zona="peninsula",
        dia=dia,
        cupon=buscar_cupon("OTONO15"),
    )
    assert resumen.descuentos == Dinero.desde_texto("6.00")
    assert resumen.base_imponible == Dinero.desde_texto("34.00")
    assert resumen.envio == Dinero.desde_texto("4.95")
    assert resumen.total == Dinero.desde_texto("47.13")


def test_resumen_con_cupon_caducado_se_rechaza(taza: Producto, dia: date):
    with pytest.raises(CuponInvalido):
        calcular_resumen(
            (LineaPedido(taza, 2),),
            zona="peninsula",
            dia=dia,
            cupon=buscar_cupon("VERANO10"),
        )


def test_resumen_con_descuento_de_fidelidad(taza: Producto, dia: date):
    oro = Cliente("CLI-003", "Carla", 620)
    resumen = calcular_resumen((LineaPedido(taza, 12),), zona="peninsula", dia=dia, cliente=oro)
    # 102.00 menos el 5% de fidelidad: 96.90 de base.
    assert resumen.base_imponible == Dinero.desde_texto("96.90")
    assert resumen.descuentos == Dinero.desde_texto("23.10")
    assert resumen.total == Dinero.desde_texto("117.25")


def test_resumen_de_varias_lineas(taza: Producto, saco: Producto, dia: date):
    lineas = (LineaPedido(taza, 2), LineaPedido(saco, 1))
    resumen = calcular_resumen(lineas, zona="peninsula", dia=dia)
    assert resumen.subtotal == Dinero.desde_texto("28.00")
    assert resumen.base_imponible == Dinero.desde_texto("28.00")
    # 5.8 kg: la base mas cuatro kilos de suplemento.
    assert resumen.envio == Dinero.desde_texto("6.95")
    # 20.00 al 21% son 4.20; 8.00 al 10% son 0.80; los portes, 1.46.
    assert resumen.impuestos == Dinero.desde_texto("6.46")
    assert resumen.total == Dinero.desde_texto("41.41")

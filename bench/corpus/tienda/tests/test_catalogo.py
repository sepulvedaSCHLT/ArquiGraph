"""Consultas de catalogo."""

from __future__ import annotations

import pytest
from tienda.compartido.errores import ProductoNoEncontrado
from tienda.dominio.catalogo import (
    buscar_por_categoria,
    buscar_por_texto,
    disponibilidad,
    listar_productos,
    obtener_producto,
)


def test_listar_devuelve_el_catalogo_completo(contexto):
    assert len(listar_productos(contexto)) == 6


def test_obtener_por_referencia(contexto):
    assert obtener_producto(contexto, "CAF-001").nombre == "Cafe de especialidad 1 kg"


def test_obtener_no_distingue_mayusculas(contexto):
    assert obtener_producto(contexto, "caf-001").referencia == "CAF-001"


def test_obtener_lo_que_no_existe(contexto):
    with pytest.raises(ProductoNoEncontrado):
        obtener_producto(contexto, "NO-EXISTE")


def test_buscar_por_categoria(contexto):
    assert len(buscar_por_categoria(contexto, "alimentacion")) == 2
    assert len(buscar_por_categoria(contexto, "menaje")) == 3
    assert buscar_por_categoria(contexto, "ropa") == []


def test_buscar_por_texto(contexto):
    encontrados = buscar_por_texto(contexto, "cafe")
    assert {p.referencia for p in encontrados} == {"CAF-001", "CAF-005"}
    assert buscar_por_texto(contexto, "") == []


def test_disponibilidad_sale_del_inventario(contexto):
    assert disponibilidad(contexto, "MOL-002") == 10
    contexto.inventario.reservar("MOL-002", 4)
    assert disponibilidad(contexto, "MOL-002") == 6

"""Recursos de catalogo."""

from __future__ import annotations

from tienda.api.recursos_catalogo import buscar_productos, consultar_producto, listar_productos


def test_listar_devuelve_los_seis_productos(contexto):
    codigo, cuerpo = listar_productos(contexto)
    assert codigo == 200
    assert len(cuerpo["productos"]) == 6


def test_consultar_producto(contexto):
    codigo, cuerpo = consultar_producto(contexto, "CAF-001")
    assert codigo == 200
    assert cuerpo["referencia"] == "CAF-001"
    assert cuerpo["precio"] == "12.50"
    assert cuerpo["disponibles"] == 40


def test_consultar_producto_en_minusculas(contexto):
    # La referencia llega del exterior con la caja cambiada y sigue
    # siendo el mismo producto.
    codigo, cuerpo = consultar_producto(contexto, "caf-001")
    assert codigo == 200
    assert cuerpo["referencia"] == "CAF-001"


def test_consultar_producto_inexistente(contexto):
    codigo, cuerpo = consultar_producto(contexto, "NO-EXISTE")
    assert codigo == 404
    assert cuerpo["codigo"] == "producto_no_encontrado"


def test_buscar_por_categoria(contexto):
    codigo, cuerpo = buscar_productos(contexto, categoria="libros")
    assert codigo == 200
    assert [p["referencia"] for p in cuerpo["productos"]] == ["LIB-003"]


def test_buscar_por_texto(contexto):
    _, cuerpo = buscar_productos(contexto, texto="taza")
    assert [p["referencia"] for p in cuerpo["productos"]] == ["TAZ-010"]


def test_buscar_sin_criterio_devuelve_todo(contexto):
    _, cuerpo = buscar_productos(contexto)
    assert len(cuerpo["productos"]) == 6

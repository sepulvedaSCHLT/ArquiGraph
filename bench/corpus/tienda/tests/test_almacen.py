"""Almacen clave-valor."""

from __future__ import annotations

from tienda.infraestructura.almacen import AlmacenEnMemoria


def test_guarda_y_obtiene():
    almacen: AlmacenEnMemoria[str] = AlmacenEnMemoria()
    almacen.guardar("CAF-001", "cafe")
    assert almacen.obtener("CAF-001") == "cafe"


def test_la_clave_se_normaliza_al_consultar():
    almacen: AlmacenEnMemoria[str] = AlmacenEnMemoria()
    almacen.guardar("CAF-001", "cafe")
    assert almacen.obtener("caf-001") == "cafe"
    assert almacen.obtener("  caf-001  ") == "cafe"
    assert almacen.existe("caf-001")


def test_la_clave_se_normaliza_al_guardar():
    almacen: AlmacenEnMemoria[str] = AlmacenEnMemoria()
    almacen.guardar(" caf-001 ", "cafe")
    assert almacen.obtener("CAF-001") == "cafe"
    assert almacen.claves() == ["CAF-001"]


def test_obtener_lo_que_no_esta_devuelve_none():
    almacen: AlmacenEnMemoria[str] = AlmacenEnMemoria()
    assert almacen.obtener("NO-EXISTE") is None
    assert not almacen.existe("NO-EXISTE")


def test_listar_conserva_el_orden_de_insercion():
    almacen: AlmacenEnMemoria[int] = AlmacenEnMemoria()
    for indice, clave in enumerate(["c", "a", "b"]):
        almacen.guardar(clave, indice)
    assert almacen.listar() == [0, 1, 2]
    assert len(almacen) == 3


def test_borrar():
    almacen: AlmacenEnMemoria[str] = AlmacenEnMemoria()
    almacen.guardar("X", "x")
    almacen.borrar("x")
    assert len(almacen) == 0

"""Montaje de la aplicacion.

Este es el unico sitio donde se construyen las piezas concretas. El
dominio recibe el ``Contexto`` ya hecho, y por eso un test puede
cambiar el reloj o vaciar el catalogo sin tocar una sola regla.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from tienda.compartido.dinero import Dinero
from tienda.dominio.inventario import Inventario
from tienda.dominio.modelos import Cliente, Producto
from tienda.infraestructura.identificadores import GeneradorSecuencial
from tienda.infraestructura.reloj import Reloj, RelojFijo
from tienda.infraestructura.repositorio_clientes import RepositorioClientes
from tienda.infraestructura.repositorio_pedidos import RepositorioPedidos
from tienda.infraestructura.repositorio_productos import RepositorioProductos

__all__ = [
    "CATALOGO_DEMO",
    "CLIENTES_DEMO",
    "DIA_DEMO",
    "EXISTENCIAS_DEMO",
    "Contexto",
    "crear_contexto",
    "poblar",
]

DIA_DEMO = date(2026, 7, 15)

# El catalogo de demostracion se declara como tabla y se convierte a
# productos: un precio escrito como texto se lee mejor que un Dinero.
_FILAS_CATALOGO = (
    ("CAF-001", "Cafe de especialidad 1 kg", "alimentacion", "12.50", 10, 1000),
    ("CAF-005", "Saco de cafe verde 5 kg", "alimentacion", "8.00", 10, 5000),
    ("TAZ-010", "Taza de ceramica", "menaje", "10.00", 21, 400),
    ("MOL-002", "Molinillo manual", "menaje", "20.00", 21, 800),
    ("LIB-003", "Manual del barista", "libros", "20.00", 4, 800),
    ("FIL-004", "Filtros de papel", "menaje", "2.03", 21, 60),
)

CATALOGO_DEMO = tuple(
    Producto(referencia, nombre, categoria, Dinero.desde_texto(precio), tipo_iva, peso)
    for referencia, nombre, categoria, precio, tipo_iva, peso in _FILAS_CATALOGO
)

EXISTENCIAS_DEMO = {
    "CAF-001": 40,
    "CAF-005": 12,
    "TAZ-010": 100,
    "MOL-002": 10,
    "LIB-003": 25,
    "FIL-004": 200,
}

CLIENTES_DEMO = (
    Cliente("CLI-001", "Ana Ferrer", 0),
    Cliente("CLI-002", "Bruno Salas", 150),
    Cliente("CLI-003", "Carla Ortiz", 620),
)


@dataclass(frozen=True)
class Contexto:
    """Las dependencias de la aplicacion, ya resueltas."""

    productos: RepositorioProductos
    pedidos: RepositorioPedidos
    clientes: RepositorioClientes
    inventario: Inventario
    reloj: Reloj
    identificadores: GeneradorSecuencial


def crear_contexto(reloj: Reloj | None = None) -> Contexto:
    """Contexto vacio. El reloj por defecto es fijo, nunca el del sistema."""
    return Contexto(
        productos=RepositorioProductos(),
        pedidos=RepositorioPedidos(),
        clientes=RepositorioClientes(),
        inventario=Inventario(),
        reloj=reloj if reloj is not None else RelojFijo(DIA_DEMO),
        identificadores=GeneradorSecuencial("PED"),
    )


def poblar(contexto: Contexto) -> Contexto:
    """Carga el catalogo, las existencias y los clientes de demostracion."""
    for producto in CATALOGO_DEMO:
        contexto.productos.guardar(producto)
        contexto.inventario.registrar(producto.referencia, EXISTENCIAS_DEMO[producto.referencia])
    for cliente in CLIENTES_DEMO:
        contexto.clientes.guardar(cliente)
    return contexto

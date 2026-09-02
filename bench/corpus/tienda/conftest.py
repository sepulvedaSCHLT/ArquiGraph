"""Fixtures compartidas del corpus.

Vive en la raiz para que ``tienda`` sea importable desde los tests y
para que el calendario y el catalogo de demostracion se monten en un
unico sitio.
"""

from __future__ import annotations

from datetime import date

import pytest
from tienda.compartido.dinero import Dinero
from tienda.dominio.modelos import Cliente, Producto
from tienda.infraestructura.contexto import crear_contexto, poblar
from tienda.infraestructura.reloj import RelojFijo


@pytest.fixture
def dia() -> date:
    """El dia en el que ocurre todo en los tests."""
    return date(2026, 7, 15)


@pytest.fixture
def reloj(dia: date) -> RelojFijo:
    return RelojFijo(dia)


@pytest.fixture
def contexto(reloj: RelojFijo):
    """Contexto con el catalogo, las existencias y los clientes cargados."""
    return poblar(crear_contexto(reloj))


@pytest.fixture
def taza() -> Producto:
    return Producto("TAZ-010", "Taza de ceramica", "menaje", Dinero.desde_texto("10.00"), 21, 400)


@pytest.fixture
def saco() -> Producto:
    return Producto(
        "CAF-005", "Saco de cafe verde 5 kg", "alimentacion", Dinero.desde_texto("8.00"), 10, 5000
    )


@pytest.fixture
def filtros() -> Producto:
    return Producto("FIL-004", "Filtros de papel", "menaje", Dinero.desde_texto("2.03"), 21, 60)


@pytest.fixture
def cliente_bronce() -> Cliente:
    return Cliente("CLI-001", "Ana Ferrer", 0)

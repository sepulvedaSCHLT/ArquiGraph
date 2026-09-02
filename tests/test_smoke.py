"""Prueba minima: el paquete importa y el CI tiene algo que ejecutar."""

import arquigraph


def test_paquete_importa() -> None:
    assert arquigraph.__version__ == "0.0.1"

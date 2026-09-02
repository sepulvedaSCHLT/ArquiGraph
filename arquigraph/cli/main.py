"""Punto de entrada de la CLI de ArquiGraph."""

from arquigraph import __version__


def main() -> None:
    """Muestra la version. Los subcomandos llegan en el paso 7 de SPEC-FASE-0."""
    print(f"arquigraph {__version__} - fase 0")


if __name__ == "__main__":
    main()

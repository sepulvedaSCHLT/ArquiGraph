"""Tienda: corpus sintetico del banco de medicion.

Un paquete deliberadamente ordinario --capas ``api`` / ``dominio`` /
``infraestructura`` / ``compartido``-- escrito para que localizar algo
exija navegar entre capas. No es codigo de produccion de ArquiGraph:
es el sujeto sobre el que se miden las tareas de ``bench/tasks/``.

Reglas que cumple todo el paquete (ADR-010):

- Solo libreria estandar. Ni una dependencia.
- Nada no determinista: el reloj se inyecta desde ``infraestructura``,
  los identificadores son una secuencia, y no hay E/S de red ni disco.
- El dinero son centimos enteros; ningun ``float`` toca un importe.
"""

__all__ = ["VERSION"]

VERSION = "1.0.0"

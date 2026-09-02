"""Lectura de las tareas del banco (SPEC-FASE-0 seccion 3).

Es la vista que el **runner** tiene de un archivo de ``bench/tasks/``:
lo justo para preparar el directorio de trabajo, invocar al agente y
evaluar el resultado.

Dos ausencias deliberadas:

- ``hint_files`` se lee y se guarda, pero **nunca** viaja al agente.
  Documenta donde vive el bug para quien escribe la tarea; darselo al
  agente eliminaria precisamente lo que el banco mide.
- ``test_command`` de la tarea no se usa. El runner corre los tests con
  ``config.interprete_tests`` porque el ``python`` del PATH no tiene
  ``pytest``; ver ``ejecutor.ejecutar_tarea``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Tarea", "cargar_tarea", "cargar_tareas"]


@dataclass(frozen=True)
class Tarea:
    """Una tarea del banco, ya resuelta a rutas de disco."""

    task_id: str
    corpus: str
    directorio_corpus: Path  # bench/corpus/<corpus>, de solo lectura
    parche: Path  # bench/tasks/<task_id>.bug.patch
    problem_statement: str  # el prompt del agente, tal cual
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    hint_files: tuple[str, ...] = ()  # documentacion, jamas para el agente


def cargar_tarea(ruta: Path, directorio_corpus: Path | None = None) -> Tarea:
    """Lee ``bench/tasks/<task_id>.json``.

    ``directorio_corpus`` es la raiz que contiene los corpus; por defecto
    la hermana ``corpus/`` del directorio de tareas.
    """
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    raiz = directorio_corpus if directorio_corpus is not None else ruta.parent.parent / "corpus"
    corpus = str(datos["corpus"])
    return Tarea(
        task_id=str(datos["task_id"]),
        corpus=corpus,
        directorio_corpus=raiz / corpus,
        parche=ruta.parent / datos["bug_patch"],
        problem_statement=str(datos["problem_statement"]),
        fail_to_pass=tuple(datos["fail_to_pass"]),
        pass_to_pass=tuple(datos["pass_to_pass"]),
        hint_files=tuple(datos.get("hint_files", ())),
    )


def cargar_tareas(
    directorio_tareas: Path,
    identificadores: list[str] | None = None,
    directorio_corpus: Path | None = None,
) -> list[Tarea]:
    """Todas las tareas del directorio, o solo las pedidas, en orden.

    Raises:
        FileNotFoundError: si se pide un identificador que no existe. Un
            banco que ejecuta en silencio menos tareas de las pedidas
            produce una media sobre otra cosa.
    """
    rutas = sorted(directorio_tareas.glob("*.json"))
    if identificadores is not None:
        pedidas = {i.removesuffix(".json") for i in identificadores}
        rutas = [r for r in rutas if r.stem in pedidas]
        faltan = pedidas - {r.stem for r in rutas}
        if faltan:
            raise FileNotFoundError(f"no hay tarea para: {', '.join(sorted(faltan))}")
    return [cargar_tarea(ruta, directorio_corpus) for ruta in rutas]

#!/usr/bin/env python3
"""Verifica que cada tarea del banco discrimina.

Una tarea que no discrimina no mide nada: si sus tests fallan tanto con
el bug puesto como sin el --o pasan en los dos casos-- la cifra que
salga del banco no dice nada sobre el agente. Esto se comprueba con un
script, nunca a ojo.

Para cada tarea de ``bench/tasks/``:

1. Copia el corpus a un directorio temporal.
2. Aplica ``bug_patch``.
3. Ejecuta los tests: ``fail_to_pass`` debe FALLAR y ``pass_to_pass``
   debe PASAR.
4. Revierte el parche.
5. Ejecuta los tests: ambos conjuntos deben PASAR.

Sale con codigo 0 solo si todas las tareas discriminan.

Uso::

    python bench/verificar_tareas.py [T003 T007 ...]

Sin dependencias externas: solo libreria estandar y el ``pytest`` que
ya vive en el entorno de desarrollo.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

BENCH = Path(__file__).resolve().parent
CORPUS = BENCH / "corpus"
TAREAS = BENCH / "tasks"

# Lo que no se copia al directorio de trabajo: es regenerable y solo
# ensucia la comparacion.
IGNORAR = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", ".coverage")

VERDE = "OK"
ROJO = "FALLA"


@dataclass(frozen=True)
class Tarea:
    """Una tarea del banco, tal y como esta en disco."""

    identificador: str
    corpus: str
    parche: Path
    orden_de_test: list[str]
    fail_to_pass: list[str]
    pass_to_pass: list[str]

    @classmethod
    def leer(cls, ruta: Path) -> Tarea:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return cls(
            identificador=datos["task_id"],
            corpus=datos["corpus"],
            parche=ruta.parent / datos["bug_patch"],
            orden_de_test=shlex.split(datos.get("test_command", "python -m pytest -q")),
            fail_to_pass=list(datos["fail_to_pass"]),
            pass_to_pass=list(datos["pass_to_pass"]),
        )


@dataclass
class Resultado:
    """Que se observo en una tarea."""

    identificador: str
    problemas: list[str]

    @property
    def discrimina(self) -> bool:
        return not self.problemas


def _ejecutar(orden: list[str], directorio: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(orden, cwd=directorio, capture_output=True, text=True, check=False)


def _orden_de_pytest(base: list[str], nodos: list[str]) -> list[str]:
    """La orden de tests de la tarea, restringida a unos nodos.

    ``python`` se sustituye por el interprete que ejecuta este script:
    es el que tiene ``pytest`` instalado, y asi la verificacion no
    depende de que haya en el PATH.
    """
    orden = list(base)
    if orden and orden[0] in {"python", "python3"}:
        orden[0] = sys.executable
    return orden + nodos


def _aplicar(parche: Path, directorio: Path, revertir: bool = False) -> None:
    """Aplica --o revierte-- el parche con git apply, y si no, con patch."""
    intentos = [
        ["git", "apply", "-p1"] + (["-R"] if revertir else []) + [str(parche)],
        ["patch", "-p1", "-s"] + (["-R"] if revertir else []) + ["-i", str(parche)],
    ]
    errores = []
    for orden in intentos:
        proceso = _ejecutar(orden, directorio)
        if proceso.returncode == 0:
            return
        errores.append(f"{orden[0]}: {(proceso.stderr or proceso.stdout).strip()}")
    verbo = "revertir" if revertir else "aplicar"
    raise RuntimeError(f"no se pudo {verbo} {parche.name}\n  " + "\n  ".join(errores))


def _nodos_que_fallan(tarea: Tarea, directorio: Path, nodos: list[str]) -> list[str]:
    """De esos nodos, cuales no pasan. Uno a uno para saber cual es."""
    fallan = []
    for nodo in nodos:
        proceso = _ejecutar(_orden_de_pytest(tarea.orden_de_test, [nodo]), directorio)
        if proceso.returncode != 0:
            fallan.append(nodo)
    return fallan


def verificar(tarea: Tarea) -> Resultado:
    """Aplica el parche, mide, lo revierte y vuelve a medir."""
    problemas: list[str] = []
    origen = CORPUS / tarea.corpus
    if not origen.is_dir():
        return Resultado(tarea.identificador, [f"no existe el corpus '{tarea.corpus}'"])
    if not tarea.parche.is_file():
        return Resultado(tarea.identificador, [f"no existe el parche {tarea.parche.name}"])

    with tempfile.TemporaryDirectory(prefix=f"bench-{tarea.identificador}-") as temporal:
        trabajo = Path(temporal) / tarea.corpus
        shutil.copytree(origen, trabajo, ignore=IGNORAR)

        try:
            _aplicar(tarea.parche, trabajo)
        except RuntimeError as error:
            return Resultado(tarea.identificador, [str(error)])

        # Con el bug puesto: lo que debe fallar, falla; lo demas, no.
        fallan = _nodos_que_fallan(tarea, trabajo, tarea.fail_to_pass)
        problemas += [
            f"con el bug deberia fallar y pasa: {nodo}"
            for nodo in tarea.fail_to_pass
            if nodo not in fallan
        ]
        problemas += [
            f"con el bug deberia pasar y falla: {nodo}"
            for nodo in _nodos_que_fallan(tarea, trabajo, tarea.pass_to_pass)
        ]

        try:
            _aplicar(tarea.parche, trabajo, revertir=True)
        except RuntimeError as error:
            problemas.append(str(error))
            return Resultado(tarea.identificador, problemas)

        # Sin el bug: todo verde. Si no, el parche no era la unica causa.
        problemas += [
            f"sin el bug deberia pasar y falla: {nodo}"
            for nodo in _nodos_que_fallan(tarea, trabajo, tarea.fail_to_pass + tarea.pass_to_pass)
        ]

    return Resultado(tarea.identificador, problemas)


def main(argv: list[str]) -> int:
    rutas = sorted(TAREAS.glob("*.json"))
    if argv:
        pedidas = {a.removesuffix(".json") for a in argv}
        rutas = [r for r in rutas if r.stem in pedidas]
        if not rutas:
            print(f"ninguna tarea coincide con {', '.join(sorted(pedidas))}", file=sys.stderr)
            return 2
    if not rutas:
        print(f"no hay tareas en {TAREAS}", file=sys.stderr)
        return 2

    resultados = []
    for ruta in rutas:
        resultado = verificar(Tarea.leer(ruta))
        resultados.append(resultado)
        estado = VERDE if resultado.discrimina else ROJO
        print(f"{resultado.identificador}  {estado}")
        for problema in resultado.problemas:
            print(f"    {problema}")

    discriminan = sum(1 for r in resultados if r.discrimina)
    print(f"\n{discriminan}/{len(resultados)} tareas discriminan")
    return 0 if discriminan == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Punto de entrada de la CLI de ArquiGraph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from arquigraph import __version__
from arquigraph.bench.runner.ejecutor import MODO_A, ConfiguracionBanco
from arquigraph.bench.runner.informe import construir_informe, formatear, leer_registros
from arquigraph.bench.runner.orquestador import ejecutar_banco
from arquigraph.bench.runner.tareas import cargar_tareas

RAIZ = Path(__file__).resolve().parents[2]
BENCH = RAIZ / "bench"

# El identificador completo, no el alias: el mismo valor se le pasa al
# agente y se compara con el `init` para verificar el aislamiento.
MODELO_POR_DEFECTO = "claude-sonnet-5"
# Tres, no cinco: `Glob` y `Grep` no existen con esos nombres en el
# conjunto integrado --al pedirlos, el `init` devolvia solo `Bash`, `Edit`
# y `Read`--, y el agente busca con `Bash`. La misma lista alimenta
# `--tools` y `--allowedTools` (FINDINGS-token-accounting 3.2).
HERRAMIENTAS_POR_DEFECTO = "Read,Edit,Bash"


def main(argv: list[str] | None = None) -> int:
    """Los subcomandos de grafo llegan en el paso 7 de SPEC-FASE-0."""
    analizador = _analizador()
    opciones = analizador.parse_args(argv)

    if opciones.comando is None:
        print(f"arquigraph {__version__} - fase 0")
        return 0
    if opciones.subcomando_bench == "run":
        return _bench_run(opciones)
    return _bench_report(opciones)


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(prog="arqui", description="ArquiGraph - fase 0")
    comandos = analizador.add_subparsers(dest="comando")

    bench = comandos.add_parser("bench", help="banco de medicion A/B")
    subcomandos = bench.add_subparsers(dest="subcomando_bench", required=True)

    ejecutar = subcomandos.add_parser("run", help="ejecuta la tanda y escribe los registros")
    ejecutar.add_argument("--mode", default=MODO_A, help="solo A en fase 0")
    ejecutar.add_argument("--repeticiones", type=int, default=1)
    ejecutar.add_argument("--tareas", help="lista separada por comas, p. ej. T001,T003")
    ejecutar.add_argument("--tope-usd", type=float, dest="tope_usd")
    ejecutar.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ejecutar.add_argument("--herramientas", default=HERRAMIENTAS_POR_DEFECTO)
    # Sin valor por defecto: `--settings` no desactiva plugins ni MCP, asi
    # que el banco no lo pasa salvo que se pida explicitamente.
    ejecutar.add_argument("--settings", type=Path, default=None)
    ejecutar.add_argument("--timeout", type=int, default=900)
    ejecutar.add_argument("--interprete-tests", dest="interprete_tests", default=sys.executable)
    ejecutar.add_argument("--tareas-dir", type=Path, dest="tareas_dir", default=BENCH / "tasks")
    ejecutar.add_argument("--runs", type=Path, default=BENCH / "runs")

    informe = subcomandos.add_parser("report", help="resume los registros de bench/runs/")
    informe.add_argument("--runs", type=Path, default=BENCH / "runs")

    return analizador


def _bench_run(opciones: argparse.Namespace) -> int:
    if opciones.mode != MODO_A:
        print(
            f"modo {opciones.mode!r} no disponible: el modo B llega en fase 1, "
            "cuando exista el servidor MCP",
            file=sys.stderr,
        )
        return 2

    try:
        tareas = cargar_tareas(
            opciones.tareas_dir,
            opciones.tareas.split(",") if opciones.tareas else None,
        )
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 2
    if not tareas:
        print(f"no hay tareas en {opciones.tareas_dir}", file=sys.stderr)
        return 2

    config = ConfiguracionBanco(
        modelo=opciones.modelo,
        herramientas=tuple(opciones.herramientas.split(",")),
        settings=opciones.settings,
        timeout_segundos=opciones.timeout,
        interprete_tests=opciones.interprete_tests,
    )
    resumen = ejecutar_banco(
        tareas,
        config,
        opciones.repeticiones,
        opciones.runs,
        tope_gasto_usd=opciones.tope_usd,
    )
    print(f"\n{len(resumen.resultados)} ejecuciones, ${resumen.gasto_usd:.4f} gastados")
    return 0


def _bench_report(opciones: argparse.Namespace) -> int:
    registros = leer_registros(opciones.runs)
    if not registros:
        print(f"no hay registros en {opciones.runs}", file=sys.stderr)
        return 2
    print(formatear(construir_informe(registros)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

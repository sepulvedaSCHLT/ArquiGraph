"""Informe de una tanda: ``arqui bench report``.

Lee ``bench/runs/*.json`` y resume por tarea y en total. Las ejecuciones
descartadas por aislamiento **no entran en ninguna media**: solo se
cuentan. Promediar una ejecucion que corrio con otro modelo, o con un
servidor MCP colado, seria publicar una cifra de otra cosa.

La dispersion es la desviacion tipica **poblacional** de las
repeticiones observadas: describe lo que se midio, no estima una
poblacion mayor, y esta definida tambien con una sola repeticion.

El encabezado declara el entorno **observado**: sale del ``init`` de los
registros, no de la configuracion que se pidio. Si un lector no puede
ver en que condiciones se midio, la cifra no vale (ADR-007). Cuando la
tanda mezcla entornos distintos se imprime una linea por cada uno: eso
tambien es informacion, y esconderla seria publicar una media de cosas
que no son la misma.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "Entorno",
    "Estadisticas",
    "Informe",
    "construir_informe",
    "formatear",
    "leer_registros",
]

TOTAL = "TOTAL"
SIN_ENTORNO = "no registrado: ninguna ejecucion dejo el evento init"


@dataclass(frozen=True)
class Estadisticas:
    """Resumen de un conjunto de ejecuciones."""

    task_id: str
    validas: int
    descartadas: int  # invalidas por aislamiento o por stream incompleto
    exitos: int
    tasa_exito: float
    con_coste: int  # validas con `result` en el stream; un timeout no lo trae
    coste_medio_usd: float
    desviacion_coste_usd: float
    turnos_medios: float


@dataclass(frozen=True)
class Entorno:
    """Las condiciones en las que se midio, leidas del ``init``.

    Los plugins se cuentan y no se ocultan: no hay forma de quitarlos sin
    romper la autenticacion (FINDINGS-token-accounting 3.2), asi que
    entran en la linea base y quien lea la cifra tiene que verlo.
    """

    modelo: str
    plugins: int
    servidores_mcp: int
    herramientas: int

    def __str__(self) -> str:
        return (
            f"{self.modelo} | {_plural(self.plugins, 'plugin')} | "
            f"{_plural(self.servidores_mcp, 'servidor MCP', 'servidores MCP')} | "
            f"{_plural(self.herramientas, 'herramienta')}"
        )


@dataclass(frozen=True)
class Informe:
    entornos: tuple[Entorno, ...]  # los observados, en orden de aparicion
    por_tarea: tuple[Estadisticas, ...]
    total: Estadisticas


def leer_registros(directorio: Path) -> list[dict[str, Any]]:
    """Los registros del directorio, ordenados por ``run_id``."""
    registros = [
        json.loads(ruta.read_text(encoding="utf-8")) for ruta in sorted(directorio.glob("*.json"))
    ]
    return sorted(registros, key=lambda r: str(r.get("run_id", "")))


def construir_informe(registros: list[dict[str, Any]]) -> Informe:
    por_tarea = {}
    for registro in registros:
        por_tarea.setdefault(str(registro.get("task_id", "")), []).append(registro)
    return Informe(
        entornos=_entornos(registros),
        por_tarea=tuple(
            _estadisticas(task_id, grupo) for task_id, grupo in sorted(por_tarea.items())
        ),
        total=_estadisticas(TOTAL, registros),
    )


def formatear(informe: Informe) -> str:
    """Entorno observado y tabla: una linea por tarea y una con el total."""
    cabecera = (
        f"{'tarea':<8} {'validas':>7} {'descart':>7} {'exito':>7} "
        f"{'$ medio':>9} {'$ desv':>8} {'turnos':>7}"
    )
    declarados = [f"entorno: {entorno}" for entorno in informe.entornos]
    lineas = declarados or [f"entorno: {SIN_ENTORNO}"]
    lineas += ["", cabecera, "-" * len(cabecera)]
    lineas += [_fila(e) for e in informe.por_tarea]
    lineas += ["-" * len(cabecera), _fila(informe.total)]
    return "\n".join(lineas)


def _fila(e: Estadisticas) -> str:
    return (
        f"{e.task_id:<8} {e.validas:>7} {e.descartadas:>7} {e.tasa_exito:>6.0%} "
        f"{e.coste_medio_usd:>9.4f} {e.desviacion_coste_usd:>8.4f} {e.turnos_medios:>7.1f}"
    )


def _estadisticas(task_id: str, registros: list[dict[str, Any]]) -> Estadisticas:
    validas = [r for r in registros if _es_valida(r)]
    costes = [c["total_cost_usd"] for c in map(_coste, validas) if c is not None]
    turnos = [c["num_turns"] for c in map(_coste, validas) if c is not None]
    exitos = sum(1 for r in validas if _exito(r))
    return Estadisticas(
        task_id=task_id,
        validas=len(validas),
        descartadas=len(registros) - len(validas),
        exitos=exitos,
        tasa_exito=exitos / len(validas) if validas else 0.0,
        con_coste=len(costes),
        coste_medio_usd=statistics.fmean(costes) if costes else 0.0,
        desviacion_coste_usd=statistics.pstdev(costes) if costes else 0.0,
        turnos_medios=statistics.fmean(turnos) if turnos else 0.0,
    )


def _es_valida(registro: dict[str, Any]) -> bool:
    aislamiento = registro.get("isolation")
    return bool(aislamiento.get("valid")) if isinstance(aislamiento, dict) else False


def _exito(registro: dict[str, Any]) -> bool:
    outcome = registro.get("outcome")
    return bool(outcome.get("success")) if isinstance(outcome, dict) else False


def _coste(registro: dict[str, Any]) -> dict[str, Any] | None:
    coste = registro.get("cost")
    return coste if isinstance(coste, dict) else None


def _entornos(registros: list[dict[str, Any]]) -> tuple[Entorno, ...]:
    """Los entornos distintos observados, sin repetir y en orden.

    Sale del bloque ``agent``, que el ledger rellena desde el ``init``:
    lo que la ejecucion hizo, no lo que se le pidio hacer. Un registro
    sin ``agent`` --agente que no arranco, stream vacio-- no aporta
    entorno y se salta.
    """
    entornos: list[Entorno] = []
    for registro in registros:
        agente = registro.get("agent")
        if not isinstance(agente, dict):
            continue
        entorno = Entorno(
            modelo=str(agente.get("model", "")),
            plugins=len(_lista(agente.get("plugins"))),
            servidores_mcp=len(_lista(agente.get("mcp_servers"))),
            herramientas=len(_lista(agente.get("tools"))),
        )
        if entorno not in entornos:
            entornos.append(entorno)
    return tuple(entornos)


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def _plural(cantidad: int, singular: str, plural: str = "") -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural or singular + 's'}"

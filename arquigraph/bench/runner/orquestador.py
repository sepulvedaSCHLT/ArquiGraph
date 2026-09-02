"""Orquestacion de una tanda del banco (SPEC-FASE-0 seccion 7, paso 9).

Secuencial, no paralelo: la maquina tiene cuatro nucleos y otros
proyectos encima.

El registro de cada ejecucion lo escribe ``ejecutar_tarea`` al terminar
esa ejecucion, no esta funcion al final de la tanda. Si la tanda se
corta --por el tope de gasto, por una tarea rota o por un Ctrl-C-- no se
pierde lo que ya se pago.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arquigraph.bench.runner.ejecutor import (
    ConfiguracionBanco,
    ResultadoEjecucion,
    ejecutar_tarea,
)
from arquigraph.bench.runner.tareas import Tarea

__all__ = ["ResumenBanco", "ejecutar_banco"]


@dataclass(frozen=True)
class ResumenBanco:
    """Lo que dio la tanda. ``gasto_usd`` incluye las ejecuciones invalidas.

    Una ejecucion descartada por aislamiento no entra en la media, pero
    se pago igual: el tope de gasto la cuenta.
    """

    resultados: tuple[ResultadoEjecucion, ...]
    gasto_usd: float
    detenido_por_tope: bool


def ejecutar_banco(
    tareas: list[Tarea],
    config: ConfiguracionBanco,
    repeticiones: int,
    directorio_salida: Path,
    tope_gasto_usd: float | None = None,
) -> ResumenBanco:
    """Ejecuta todas las tareas en secuencial."""
    resultados: list[ResultadoEjecucion] = []
    gasto = 0.0
    detenido = False

    for tarea in tareas:
        for repeticion in range(1, repeticiones + 1):
            resultado = ejecutar_tarea(tarea, config, repeticion, directorio_salida)
            resultados.append(resultado)
            gasto += resultado.run.cost.total_cost_usd if resultado.run else 0.0
            print(_linea(resultado))

            if tope_gasto_usd is not None and gasto >= tope_gasto_usd:
                # Red de seguridad contra una fuga de gasto por un bucle
                # del agente: se detiene y se devuelve lo hecho hasta aqui.
                print(f"tope de gasto alcanzado: ${gasto:.4f} de ${tope_gasto_usd:.4f}")
                detenido = True
                break
        if detenido:
            break

    return ResumenBanco(tuple(resultados), gasto, detenido)


def _linea(resultado: ResultadoEjecucion) -> str:
    """``T003 r1  exito=si  $0.4231  14 turnos  62s``."""
    cabecera = (
        f"{resultado.task_id} r{resultado.repeticion}  exito={'si' if resultado.exito else 'no'}"
    )
    if resultado.run is None:
        cuerpo = "sin stream"
    else:
        cost = resultado.run.cost
        cuerpo = (
            f"${cost.total_cost_usd:.4f}  {cost.num_turns} turnos  "
            f"{round(cost.duration_ms / 1000)}s"
        )
    if resultado.valido:
        return f"{cabecera}  {cuerpo}"
    return f"{cabecera}  {cuerpo}  INVALIDA: {'; '.join(resultado.desviaciones)}"

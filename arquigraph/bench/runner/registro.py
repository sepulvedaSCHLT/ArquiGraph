"""Serializacion del registro de una ejecucion (SPEC-FASE-0 seccion 4).

Un registro es lo unico que sobrevive a la ejecucion: el directorio de
trabajo se borra y el agente no vuelve. Por eso se escribe **al terminar
cada ejecucion**, no al final de la tanda.

Dos bloques no estan en la seccion 4 y se anaden aqui:

- ``isolation``: sin el, una ejecucion descartada seria indistinguible
  de una valida al releer el archivo, y el informe no podria contar
  cuantas se descartaron ni por que.
- ``outcome.timeout``: distingue "el agente se quedo sin tiempo" de "el
  agente termino y fallo". Se deriva, no se guarda aparte: el unico caso
  con ``valido`` y sin ``run`` es el timeout (los demas fallos del
  agente dejan el stream incompleto, que invalida la ejecucion).

En modo A el bloque ``arquigraph`` va a ``null``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - solo para los tipos
    from arquigraph.bench.runner.ejecutor import ResultadoEjecucion

__all__ = ["escribir_registro", "registro_de"]


def registro_de(resultado: ResultadoEjecucion) -> dict[str, Any]:
    """El registro de la ejecucion, listo para serializar."""
    run = resultado.run
    return {
        "run_id": resultado.run_id,
        "task_id": resultado.task_id,
        "mode": resultado.modo,
        "repetition": resultado.repeticion,
        "started_at": resultado.iniciado_en,
        "agent": _agente(resultado),
        "isolation": {
            "valid": resultado.valido,
            "deviations": list(resultado.desviaciones),
        },
        "outcome": {
            "success": resultado.exito,
            "fail_to_pass_ok": resultado.fail_to_pass_ok,
            "pass_to_pass_ok": resultado.pass_to_pass_ok,
            "is_error": run.is_error if run else None,
            "stop_reason": run.stop_reason if run else None,
            "timeout": resultado.valido and run is None,
        },
        "cost": _coste(resultado),
        "trajectory": [
            {"turn": llamada.turn, "tool": llamada.tool, "input": llamada.tool_input}
            for llamada in (run.trajectory if run else ())
        ],
        "arquigraph": None,
    }


def escribir_registro(resultado: ResultadoEjecucion, directorio_salida: Path) -> Path:
    """Escribe ``<directorio_salida>/<run_id>.json`` y devuelve su ruta."""
    directorio_salida.mkdir(parents=True, exist_ok=True)
    destino = directorio_salida / f"{resultado.run_id}.json"
    destino.write_text(
        json.dumps(registro_de(resultado), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destino


def _agente(resultado: ResultadoEjecucion) -> dict[str, Any] | None:
    """Las condiciones reales, leidas del ``init``. Sin stream, no hay."""
    if resultado.run is None:
        return None
    agent = resultado.run.agent
    return {
        "claude_code_version": agent.claude_code_version,
        "model": agent.model,
        "plugins": list(agent.plugins),
        "mcp_servers": list(agent.mcp_servers),
        "tools": list(agent.tools),
        "permission_mode": agent.permission_mode,
    }


def _coste(resultado: ResultadoEjecucion) -> dict[str, Any] | None:
    """Sin ``result`` en el stream no hay coste: se dice ``null``, no 0."""
    if resultado.run is None:
        return None
    cost = resultado.run.cost
    return {
        "total_cost_usd": cost.total_cost_usd,
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "cache_creation_input_tokens": cost.cache_creation_input_tokens,
        "cache_read_input_tokens": cost.cache_read_input_tokens,
        "num_turns": cost.num_turns,
        "duration_ms": cost.duration_ms,
    }

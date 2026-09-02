"""Parseo del stream de una ejecucion del agente (SPEC-FASE-0 seccion 7, paso 8).

**Solo parseo.** Nada de ``subprocess``, nada de red, ningun proceso
lanzado: invocar al agente es el paso 9.

Este modulo produce la cifra del criterio de kill de R1. Si mide mal,
todo el proyecto avanza sobre un numero falso, asi que las reglas son
conservadoras:

- Sin evento ``init`` no hay reproducibilidad — el ``agent`` se rellena
  desde lo que la ejecucion **hizo**, no desde lo que creiamos
  configurar (FINDINGS-agent-hooks seccion 5).
- Sin evento ``result``, o sin ``total_cost_usd`` en el, no hay coste que
  registrar. La ejecucion se cortó y no vale.
- Un contador ausente en ``usage`` es 0. No se inventa ninguna cifra.

La forma del stream esta observada en Claude Code ``2.1.257``. Las
llamadas a herramientas viven **dentro** de ``message.content`` como
bloques ``tool_use``, no en el ``type`` de nivel superior.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "AgentInfo",
    "Cost",
    "IncompleteStreamError",
    "ParsedRun",
    "ToolCall",
    "parse_stream",
]


class IncompleteStreamError(RuntimeError):
    """El stream no describe una ejecucion completa: no se puede registrar."""


@dataclass(frozen=True)
class AgentInfo:
    """Condiciones reales de la ejecucion, leidas del evento ``init``.

    Es lo que hace reproducible una cifra publicada: modelo, version,
    plugins y servidores MCP cambian el prompt de sistema y, con el, el
    coste.
    """

    claude_code_version: str
    model: str
    plugins: tuple[str, ...]  # "nombre@version"
    mcp_servers: tuple[str, ...]
    tools: tuple[str, ...]
    permission_mode: str
    cwd: str


@dataclass(frozen=True)
class Cost:
    """Coste de la ejecucion.

    ``total_cost_usd`` es la metrica primaria: con cache de por medio,
    "tokens totales" es ambiguo porque cada categoria tiene un precio
    distinto (FINDINGS-token-accounting seccion 4). El desglose queda
    para explicar **donde** se fue el coste.
    """

    total_cost_usd: float
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    num_turns: int
    duration_ms: int


@dataclass(frozen=True)
class ToolCall:
    turn: int
    tool: str
    tool_input: dict


@dataclass(frozen=True)
class ParsedRun:
    session_id: str
    agent: AgentInfo
    cost: Cost
    trajectory: tuple[ToolCall, ...]
    is_error: bool
    stop_reason: str | None
    malformed_lines: int  # lineas que no eran JSON, contadas y descartadas


def parse_stream(lines: Iterable[str]) -> ParsedRun:
    """Convierte la salida stream-json de una ejecucion en un registro.

    Raises:
        IncompleteStreamError: si falta el evento `init` o el `result`.
    """
    init: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    trajectory: list[ToolCall] = []
    malformed = 0
    turn = 0

    for line in lines:
        if not line.strip():
            continue  # las lineas vacias no son un fallo
        event = _load(line)
        if event is None:
            # El runner redirige 2>&1 y se cuela texto de stderr.
            malformed += 1
            continue

        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            init = event
        elif kind == "assistant":
            # Un mensaje de solo texto tambien gasta turno.
            turn += 1
            trajectory.extend(_tool_calls(event, turn))
        elif kind == "result":
            result = event
        # `user`, `hook_started`, `hook_response` y `rate_limit_event` se
        # ignoran en este paso.

    if init is None:
        raise IncompleteStreamError("el stream no trae el evento system/init")
    if result is None:
        raise IncompleteStreamError("el stream no trae el evento result: la ejecucion se corto")
    if "total_cost_usd" not in result:
        raise IncompleteStreamError("el evento result no trae total_cost_usd")

    return ParsedRun(
        session_id=str(init.get("session_id", "")),
        agent=_agent_info(init),
        cost=_cost(result),
        trajectory=tuple(trajectory),
        is_error=bool(result.get("is_error", False)),
        stop_reason=result.get("stop_reason"),
        malformed_lines=malformed,
    )


def _load(line: str) -> dict[str, Any] | None:
    """El evento de una linea, o ``None`` si no es un objeto JSON."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


# ---------------------------------------------------------------------------
# system/init
# ---------------------------------------------------------------------------


def _agent_info(init: dict[str, Any]) -> AgentInfo:
    return AgentInfo(
        claude_code_version=str(init.get("claude_code_version", "")),
        model=str(init.get("model", "")),
        plugins=tuple(_plugin_label(entry) for entry in _as_list(init.get("plugins"))),
        mcp_servers=tuple(_name_of(entry) for entry in _as_list(init.get("mcp_servers"))),
        tools=tuple(str(tool) for tool in _as_list(init.get("tools"))),
        # La clave del stream es camelCase.
        permission_mode=str(init.get("permissionMode", "")),
        cwd=str(init.get("cwd", "")),
    )


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _plugin_label(entry: Any) -> str:
    """``"nombre@version"``, o solo el nombre si no viene la version."""
    if not isinstance(entry, dict):
        return str(entry)
    name = str(entry.get("name", ""))
    version = entry.get("version")
    return f"{name}@{version}" if version else name


def _name_of(entry: Any) -> str:
    """Los servidores MCP llegan como objeto con ``name``, o como cadena."""
    return str(entry.get("name", "")) if isinstance(entry, dict) else str(entry)


# ---------------------------------------------------------------------------
# assistant
# ---------------------------------------------------------------------------


def _tool_calls(event: dict[str, Any], turn: int) -> list[ToolCall]:
    """Bloques ``tool_use`` del mensaje. Un mensaje puede traer varios."""
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [
        ToolCall(
            turn=turn,
            tool=str(block.get("name", "")),
            tool_input=dict(block.get("input") or {}),
        )
        for block in _as_list(content)
        if isinstance(block, dict) and block.get("type") == "tool_use"
    ]


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------


def _cost(result: dict[str, Any]) -> Cost:
    usage = result.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return Cost(
        total_cost_usd=float(result["total_cost_usd"]),
        input_tokens=_counter(usage, "input_tokens"),
        output_tokens=_counter(usage, "output_tokens"),
        cache_creation_input_tokens=_counter(usage, "cache_creation_input_tokens"),
        cache_read_input_tokens=_counter(usage, "cache_read_input_tokens"),
        num_turns=_counter(result, "num_turns"),
        duration_ms=_counter(result, "duration_ms"),
    )


def _counter(source: dict[str, Any], key: str) -> int:
    """Un contador ausente vale 0: no se inventa."""
    value = source.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0

"""Verificacion de aislamiento de una ejecucion del banco.

Correr el banco con la configuracion personal de quien lo lanza mediria
**sus plugins**, no ArquiGraph: en la instalacion observada, el hook
``SessionStart`` de un plugin inyectaba contexto en cada sesion
(FINDINGS-agent-hooks seccion 4). Y comparar el modo A con un modelo y el
B con otro invalida la medicion entera.

Esta funcion es la que hace creibles las cifras publicadas. Sin ella,
ADR-007 no se cumple: nadie podria reproducirlas.
"""

from __future__ import annotations

from dataclasses import dataclass

from arquigraph.bench.ledger.stream import AgentInfo

__all__ = ["ExpectedEnvironment", "check_isolation"]


@dataclass(frozen=True)
class ExpectedEnvironment:
    """Condiciones que el banco declara y exige. En modo A, sin MCP."""

    model: str
    allow_plugins: bool = False
    allowed_mcp_servers: tuple[str, ...] = ()


def check_isolation(agent: AgentInfo, expected: ExpectedEnvironment) -> list[str]:
    """Devuelve la lista de desviaciones. Vacia = ejecucion valida.

    Se comprueban todas: quien lea el informe quiere saber todo lo que
    pasa con la ejecucion, no solo el primer problema.
    """
    deviations: list[str] = []

    if agent.model != expected.model:
        deviations.append(
            f"modelo: se esperaba {expected.model!r} y la ejecucion uso {agent.model!r}"
        )

    if agent.plugins and not expected.allow_plugins:
        deviations.append(f"plugins activos, no permitidos: {', '.join(agent.plugins)}")

    deviations += [
        f"servidor MCP no permitido: {server!r}"
        for server in agent.mcp_servers
        if server not in expected.allowed_mcp_servers
    ]

    return deviations

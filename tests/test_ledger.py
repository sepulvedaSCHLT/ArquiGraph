"""Ledger del banco: parseo del stream y verificacion de aislamiento.

Este modulo produce la cifra del criterio de kill de R1. Si mide mal,
todo el proyecto avanza sobre un numero falso, asi que los tests fijan
tanto lo que se extrae como lo que se rechaza:

- Sin ``init`` no hay reproducibilidad; sin ``result`` no hay coste. En
  ambos casos la ejecucion no vale y se dice en voz alta.
- El texto de stderr que se cuela por el ``2>&1`` del runner se cuenta y
  se descarta, pero no rompe el parseo.
- Un ``usage`` incompleto vale 0. No se inventan cifras de coste.

Los fixtures estan escritos a mano en ``tests/fixtures/`` y versionados:
un fixture generado por el propio codigo que se prueba no prueba nada.
"""

import json
from pathlib import Path

import pytest

from arquigraph.bench.ledger.isolation import ExpectedEnvironment, check_isolation
from arquigraph.bench.ledger.stream import (
    AgentInfo,
    IncompleteStreamError,
    ParsedRun,
    parse_stream,
)

FIXTURES = Path(__file__).parent / "fixtures"

MODELO_DEL_BANCO = "claude-sonnet-5"


def fixture(nombre: str) -> list[str]:
    return (FIXTURES / f"{nombre}.jsonl").read_text().splitlines()


def parsear(nombre: str) -> ParsedRun:
    return parse_stream(fixture(nombre))


def agente(**cambios: object) -> AgentInfo:
    """Un ``AgentInfo`` limpio, con lo que haga falta sobrescrito."""
    base: dict[str, object] = {
        "claude_code_version": "2.1.257",
        "model": MODELO_DEL_BANCO,
        "plugins": (),
        "mcp_servers": (),
        "tools": ("Bash", "Read"),
        "permission_mode": "default",
        "cwd": "/tmp/bench",
    }
    return AgentInfo(**(base | cambios))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Parseo basico
# ---------------------------------------------------------------------------


def test_session_id_del_evento_init() -> None:
    run = parsear("stream_simple")

    assert run.session_id == "05504ffe-2c31-4c8f-9a77-6b1d0f3ea111"


def test_agent_se_rellena_desde_init() -> None:
    run = parsear("stream_simple")

    assert run.agent == AgentInfo(
        claude_code_version="2.1.257",
        model="claude-sonnet-5",
        plugins=(),
        mcp_servers=(),
        tools=("Task", "Bash", "Edit", "Read"),
        permission_mode="default",
        cwd="/tmp/r6test",
    )


def test_permission_mode_se_lee_de_la_clave_camel_case() -> None:
    """La clave del stream es `permissionMode`, no `permission_mode`."""
    run = parsear("stream_contaminado")

    assert run.agent.permission_mode == "acceptEdits"


def test_cost_recoge_los_cuatro_contadores_el_coste_y_los_turnos() -> None:
    cost = parsear("stream_simple").cost

    assert cost.total_cost_usd == 0.092123
    assert cost.input_tokens == 2
    assert cost.output_tokens == 4
    assert cost.cache_creation_input_tokens == 8695
    assert cost.cache_read_input_tokens == 10126
    assert cost.num_turns == 1
    assert cost.duration_ms == 1891


def test_el_resultado_registra_el_desenlace() -> None:
    run = parsear("stream_simple")

    assert run.is_error is False
    assert run.stop_reason == "end_turn"


def test_la_trayectoria_trae_la_llamada_con_su_input() -> None:
    (llamada,) = parsear("stream_simple").trajectory

    assert llamada.turn == 1
    assert llamada.tool == "Read"
    assert llamada.tool_input == {"file_path": "/tmp/r6test/prueba.txt"}


def test_los_plugins_se_serializan_como_nombre_arroba_version() -> None:
    run = parsear("stream_contaminado")

    assert run.agent.plugins == ("superpowers@6.3.0", "frontend-design@1.2.0")


def test_un_plugin_sin_version_deja_solo_el_nombre() -> None:
    init = json.loads(fixture("stream_simple")[0])
    init["plugins"] = [{"name": "sin-version"}]
    lines = [json.dumps(init), *fixture("stream_simple")[1:]]

    assert parse_stream(lines).agent.plugins == ("sin-version",)


# ---------------------------------------------------------------------------
# Trayectoria
# ---------------------------------------------------------------------------


def test_los_turnos_se_numeran_en_orden_desde_uno() -> None:
    run = parsear("stream_multiturno")

    assert [llamada.turn for llamada in run.trajectory] == [1, 1, 3]
    assert [llamada.tool for llamada in run.trajectory] == ["Read", "Read", "Bash"]


def test_varios_tool_use_en_un_mensaje_comparten_turno() -> None:
    primeras = [c for c in parsear("stream_multiturno").trajectory if c.turn == 1]

    assert [c.tool_input["file_path"] for c in primeras] == [
        "app/auth/service.py",
        "tests/test_auth.py",
    ]


def test_un_assistant_solo_de_texto_no_aporta_llamadas_pero_gasta_turno() -> None:
    """El turno 2 es texto: no aparece en la trayectoria, pero el 3 sigue siendo el 3."""
    turnos = {llamada.turn for llamada in parsear("stream_multiturno").trajectory}

    assert 2 not in turnos
    assert 3 in turnos


def test_los_eventos_de_usuario_hooks_y_rate_limit_se_ignoran() -> None:
    run = parsear("stream_multiturno")

    assert len(run.trajectory) == 3
    assert run.cost.num_turns == 3


# ---------------------------------------------------------------------------
# Robustez
# ---------------------------------------------------------------------------


def test_el_texto_de_stderr_se_cuenta_y_se_descarta() -> None:
    run = parsear("stream_sucio")

    assert run.malformed_lines == 2
    assert run.session_id == "05504ffe-2c31-4c8f-9a77-6b1d0f3ea111"
    assert run.cost.total_cost_usd == 0.092123
    assert len(run.trajectory) == 1


def test_las_lineas_vacias_no_cuentan_como_malformadas() -> None:
    lines = fixture("stream_simple")

    assert parse_stream(["", *lines, "   ", ""]).malformed_lines == 0


def test_un_stream_sin_result_no_vale() -> None:
    with pytest.raises(IncompleteStreamError):
        parsear("stream_sin_result")


def test_un_stream_sin_init_no_vale() -> None:
    sin_init = fixture("stream_simple")[1:]

    with pytest.raises(IncompleteStreamError):
        parse_stream(sin_init)


def test_un_result_sin_coste_no_vale() -> None:
    """No se inventa el coste: sin `total_cost_usd` la ejecucion no se registra."""
    lines = fixture("stream_simple")
    result = json.loads(lines[-1])
    del result["total_cost_usd"]

    with pytest.raises(IncompleteStreamError):
        parse_stream([*lines[:-1], json.dumps(result)])


def test_un_contador_ausente_en_usage_vale_cero() -> None:
    lines = fixture("stream_simple")
    result = json.loads(lines[-1])
    del result["usage"]["cache_read_input_tokens"]

    cost = parse_stream([*lines[:-1], json.dumps(result)]).cost

    assert cost.cache_read_input_tokens == 0
    assert cost.cache_creation_input_tokens == 8695


def test_un_result_sin_usage_deja_los_contadores_a_cero() -> None:
    lines = fixture("stream_simple")
    result = json.loads(lines[-1])
    del result["usage"]

    cost = parse_stream([*lines[:-1], json.dumps(result)]).cost

    assert (cost.input_tokens, cost.output_tokens) == (0, 0)
    assert cost.total_cost_usd == 0.092123


# ---------------------------------------------------------------------------
# Aislamiento
# ---------------------------------------------------------------------------


def test_un_entorno_correcto_no_tiene_desviaciones() -> None:
    run = parsear("stream_simple")

    assert check_isolation(run.agent, ExpectedEnvironment(model=MODELO_DEL_BANCO)) == []


def test_un_modelo_distinto_es_una_desviacion_que_nombra_ambos() -> None:
    run = parsear("stream_contaminado")

    esperado = ExpectedEnvironment(model=MODELO_DEL_BANCO, allow_plugins=True)

    (desviacion,) = check_isolation(run.agent, esperado)

    assert MODELO_DEL_BANCO in desviacion
    assert "claude-opus-5[1m]" in desviacion


def test_los_plugins_son_una_desviacion_que_los_nombra() -> None:
    agent = agente(plugins=("superpowers@6.3.0", "frontend-design@1.2.0"))

    (desviacion,) = check_isolation(agent, ExpectedEnvironment(model=MODELO_DEL_BANCO))

    assert "superpowers@6.3.0" in desviacion
    assert "frontend-design@1.2.0" in desviacion


def test_los_plugins_permitidos_no_son_desviacion() -> None:
    agent = agente(plugins=("superpowers@6.3.0",))

    esperado = ExpectedEnvironment(model=MODELO_DEL_BANCO, allow_plugins=True)

    assert check_isolation(agent, esperado) == []


def test_un_servidor_mcp_no_permitido_es_una_desviacion() -> None:
    agent = agente(mcp_servers=("arquigraph",))

    (desviacion,) = check_isolation(agent, ExpectedEnvironment(model=MODELO_DEL_BANCO))

    assert "arquigraph" in desviacion


def test_un_servidor_mcp_permitido_no_es_desviacion() -> None:
    agent = agente(mcp_servers=("arquigraph",))
    esperado = ExpectedEnvironment(model=MODELO_DEL_BANCO, allowed_mcp_servers=("arquigraph",))

    assert check_isolation(agent, esperado) == []


def test_se_devuelven_todas_las_desviaciones_no_solo_la_primera() -> None:
    agent = agente(
        model="claude-opus-5[1m]",
        plugins=("superpowers@6.3.0",),
        mcp_servers=("arquigraph",),
    )

    desviaciones = check_isolation(agent, ExpectedEnvironment(model=MODELO_DEL_BANCO))

    assert len(desviaciones) == 3


def test_el_stream_contaminado_se_detecta_entero() -> None:
    """El caso real de FINDINGS-agent-hooks: modelo del autor y sus plugins."""
    run = parsear("stream_contaminado")

    desviaciones = check_isolation(run.agent, ExpectedEnvironment(model=MODELO_DEL_BANCO))

    assert len(desviaciones) == 2

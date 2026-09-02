"""Runner del banco en modo A: preparacion, veredicto y orquestacion.

Ningun test de aqui invoca al agente real. Se usa un ejecutable falso
que emite un stream fijo y, si toca, escribe en el directorio de
trabajo: un test que gaste dinero no es un test.

El corpus de estos tests es minimo a proposito --dos funciones y dos
tests-- porque lo que se prueba es el runner, no el corpus del banco.

Lo que fijan estos tests, en orden de importancia:

- El veredicto sale de ejecutar los tests, nunca de lo que el agente
  diga haber hecho.
- El comando lleva las banderas que si aislan: `--strict-mcp-config` y
  la misma lista en `--tools` y `--allowedTools`.
- Una ejecucion sin aislamiento --otro modelo, un servidor MCP colado--
  se marca invalida y no entra en la media.
- El corpus original no se toca y el temporal se borra siempre.
- Un fallo del agente --timeout, stream cortado, salida vacia-- es un
  dato que se registra, no una excepcion que tumba la tanda.
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from arquigraph.bench.runner.ejecutor import (
    VARIABLE_EJECUTABLE,
    ConfiguracionBanco,
    ResultadoEjecucion,
    TareaRotaError,
    ejecutar_tarea,
)
from arquigraph.bench.runner.informe import SIN_ENTORNO, construir_informe, formatear
from arquigraph.bench.runner.orquestador import ejecutar_banco
from arquigraph.bench.runner.registro import registro_de
from arquigraph.bench.runner.tareas import Tarea, cargar_tarea, cargar_tareas

MODELO = "claude-sonnet-5"

SUMA_CORRECTA = "def suma(a, b):\n    return a + b\n\n\ndef doble(n):\n    return n * 2\n"
SUMA_ROMPE_EL_OTRO = "def suma(a, b):\n    return a + b\n\n\ndef doble(n):\n    return n * 3\n"

TESTS_DEL_CORPUS = (
    "from calc.suma import doble, suma\n"
    "\n"
    "\n"
    "def test_suma():\n"
    "    assert suma(2, 3) == 5\n"
    "\n"
    "\n"
    "def test_doble():\n"
    "    assert doble(4) == 8\n"
)

# Cambia `a + b` por `a - b`: test_suma falla, test_doble sigue pasando.
PARCHE_DEL_BUG = (
    "\n".join(
        [
            "--- a/calc/suma.py",
            "+++ b/calc/suma.py",
            "@@ -1,5 +1,5 @@",
            " def suma(a, b):",
            "-    return a + b",
            "+    return a - b",
            " ",
            " ",
            " def doble(n):",
        ]
    )
    + "\n"
)

FAIL_TO_PASS = ("tests/test_calc.py::test_suma",)
PASS_TO_PASS = ("tests/test_calc.py::test_doble",)


# ---------------------------------------------------------------------------
# Corpus, tarea y configuracion
# ---------------------------------------------------------------------------


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Un corpus de juguete con un bug inyectable y dos tests."""
    raiz = tmp_path / "corpus" / "mini"
    (raiz / "calc").mkdir(parents=True)
    (raiz / "tests").mkdir()
    # Ancla la raiz: sin esto pytest subiria hasta el pyproject.toml de
    # ArquiGraph y recogeria los tests del proyecto.
    (raiz / "pytest.ini").write_text("[pytest]\ntestpaths = tests\npythonpath = .\n")
    (raiz / "calc" / "__init__.py").write_text("")
    (raiz / "calc" / "suma.py").write_text(SUMA_CORRECTA)
    (raiz / "tests" / "test_calc.py").write_text(TESTS_DEL_CORPUS)
    return raiz


@pytest.fixture
def tarea(tmp_path: Path, corpus: Path) -> Tarea:
    parche = tmp_path / "T900.bug.patch"
    parche.write_text(PARCHE_DEL_BUG)
    return Tarea(
        task_id="T900",
        corpus="mini",
        directorio_corpus=corpus,
        parche=parche,
        problem_statement="Sumar 2 y 3 da -1 en vez de 5.",
        fail_to_pass=FAIL_TO_PASS,
        pass_to_pass=PASS_TO_PASS,
        hint_files=("calc/suma.py",),
    )


@pytest.fixture
def config() -> ConfiguracionBanco:
    return ConfiguracionBanco(
        modelo=MODELO,
        herramientas=("Read", "Edit", "Bash"),
        timeout_segundos=30,
        interprete_tests=sys.executable,
    )


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    return tmp_path / "runs"


# ---------------------------------------------------------------------------
# El agente falso
# ---------------------------------------------------------------------------


def stream(
    modelo: str = MODELO,
    plugins: tuple[str, ...] = (),
    servidores_mcp: tuple[str, ...] = (),
    coste: float = 0.25,
    turnos: int = 3,
    con_result: bool = True,
    texto: str = "hecho",
) -> str:
    """Un stream stream-json como el que emite el agente."""
    eventos: list[dict[str, object]] = [
        {
            "type": "system",
            "subtype": "init",
            "session_id": "5e1f0000-0000-4000-8000-000000000001",
            "claude_code_version": "2.1.257",
            "model": modelo,
            "cwd": "/tmp/bench/mini",
            "permissionMode": "default",
            "mcp_servers": [{"name": nombre} for nombre in servidores_mcp],
            "tools": ["Read", "Edit", "Bash"],
            "plugins": [{"name": nombre, "version": "1.0.0"} for nombre in plugins],
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "calc/suma.py"}}
                ]
            },
        },
    ]
    if con_result:
        eventos.append(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "stop_reason": "end_turn",
                "result": texto,
                "num_turns": turnos,
                "duration_ms": 61_000,
                "total_cost_usd": coste,
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 340,
                    "cache_creation_input_tokens": 8_000,
                    "cache_read_input_tokens": 20_000,
                },
            }
        )
    return "".join(json.dumps(evento) + "\n" for evento in eventos)


def escribe(ruta: str, contenido: str) -> str:
    """Guion para el agente falso: dejar un archivo con este contenido."""
    return f"pathlib.Path({ruta!r}).write_text({contenido!r})\n"


@pytest.fixture
def agente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Instala un ejecutable falso en lugar de `claude`."""

    def instalar(salida: str = "", guion: str = "") -> Path:
        ruta = tmp_path / "agente_falso.py"
        ruta.write_text(
            f"#!{sys.executable}\nimport pathlib, sys, time\n{guion}sys.stdout.write({salida!r})\n"
        )
        ruta.chmod(0o755)
        monkeypatch.setenv(VARIABLE_EJECUTABLE, str(ruta))
        return ruta

    return instalar


def guarda_el_comando(destino: Path) -> str:
    """Guion para el agente falso: dejar su propio argv en un archivo."""
    return f"pathlib.Path({str(destino)!r}).write_text(repr(sys.argv))\n"


def comando_ejecutado(destino: Path) -> list[str]:
    """El argv que recibio el agente, sin el ejecutable."""
    return ast.literal_eval(destino.read_text())[1:]


def valor_de(comando: list[str], bandera: str) -> str:
    """El argumento que sigue a `bandera`. Falla si la bandera no esta."""
    return comando[comando.index(bandera) + 1]


def ejecutar(tarea: Tarea, config: ConfiguracionBanco, runs: Path) -> ResultadoEjecucion:
    return ejecutar_tarea(tarea, config, repeticion=1, directorio_salida=runs)


def registro_en_disco(runs: Path) -> dict:
    (archivo,) = sorted(runs.glob("*.json"))
    return json.loads(archivo.read_text())


# ---------------------------------------------------------------------------
# El comando: lo unico que aisla de verdad
# ---------------------------------------------------------------------------
#
# Cinco pre-vuelos contra el CLI real dejaron una sola bandera util
# (FINDINGS-token-accounting 3.2): `--settings` con `enabledPlugins: {}`
# no desactiva nada, `--plugin-dir` anade en vez de reemplazar, `--tools`
# no filtra las herramientas de MCP y `--bare` aisla pero rompe la
# autenticacion OAuth. Queda `--strict-mcp-config`.


@pytest.fixture
def comando(tmp_path: Path, tarea, config, runs, agente):
    """Ejecuta una tarea y devuelve el argv que recibio el agente."""

    def invocar(configuracion: ConfiguracionBanco | None = None) -> list[str]:
        destino = tmp_path / "argv.txt"
        agente(stream(), guarda_el_comando(destino))
        ejecutar(tarea, configuracion or config, runs)
        return comando_ejecutado(destino)

    return invocar


def test_el_comando_de_modo_a_elimina_los_servidores_mcp(comando) -> None:
    orden = comando()

    assert "--strict-mcp-config" in orden
    assert "--mcp-config" not in orden


def test_el_comando_nunca_usa_bare(comando) -> None:
    """Aisla, pero solo admite ANTHROPIC_API_KEY: rompe la sesion OAuth."""
    assert "--bare" not in comando()


def test_las_dos_banderas_de_herramientas_reciben_la_misma_lista(comando) -> None:
    """`--allowedTools` a secas deja el conjunto integrado entero dentro."""
    orden = comando()

    assert valor_de(orden, "--tools") == "Read,Edit,Bash"
    assert valor_de(orden, "--allowedTools") == "Read,Edit,Bash"


def test_el_modelo_y_el_enunciado_van_tal_cual(comando, tarea, config) -> None:
    orden = comando()

    assert valor_de(orden, "-p") == tarea.problem_statement
    assert valor_de(orden, "--model") == config.modelo


def test_sin_settings_la_bandera_se_omite(comando) -> None:
    """No aisla nada; pasarla por costumbre solo sugiere que si."""
    assert "--settings" not in comando()


def test_con_settings_la_bandera_se_pasa(comando, config, tmp_path) -> None:
    propios = tmp_path / "settings.bench.json"

    orden = comando(replace(config, settings=propios))

    assert valor_de(orden, "--settings") == str(propios)


def test_con_mcp_config_se_pasa_junto_a_strict(comando, config, tmp_path) -> None:
    """Modo B: `--strict-mcp-config` deja entonces solo ArquiGraph."""
    servidores = tmp_path / "mcp.arquigraph.json"

    orden = comando(replace(config, mcp_config=servidores))

    assert valor_de(orden, "--mcp-config") == str(servidores)
    assert "--strict-mcp-config" in orden


# ---------------------------------------------------------------------------
# Preparacion del entorno
# ---------------------------------------------------------------------------


def test_el_corpus_original_no_se_toca(tarea, config, runs, agente, corpus) -> None:
    antes = {
        ruta.relative_to(corpus): ruta.read_bytes() for ruta in corpus.rglob("*") if ruta.is_file()
    }
    agente(stream(), escribe("calc/suma.py", "def suma(a, b):\n    return 0\n"))

    ejecutar(tarea, config, runs)

    despues = {
        ruta.relative_to(corpus): ruta.read_bytes() for ruta in corpus.rglob("*") if ruta.is_file()
    }
    assert despues == antes


def test_el_agente_trabaja_sobre_el_corpus_ya_parcheado(
    tarea, config, runs, agente, tmp_path
) -> None:
    testigo = tmp_path / "lo_que_vio.txt"
    agente(
        stream(),
        f"pathlib.Path({str(testigo)!r}).write_text(pathlib.Path('calc/suma.py').read_text())\n",
    )

    ejecutar(tarea, config, runs)

    assert "return a - b" in testigo.read_text()


def test_el_temporal_se_borra_al_terminar(tarea, config, runs, agente, monkeypatch, tmp_path):
    base = tmp_path / "temporales"
    base.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(base))
    agente(stream())

    ejecutar(tarea, config, runs)

    assert list(base.iterdir()) == []


def test_el_temporal_se_borra_aunque_haya_excepcion(
    tarea, config, runs, agente, monkeypatch, tmp_path
):
    base = tmp_path / "temporales"
    base.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(base))
    agente(stream())
    rota = dataclass_con(tarea, fail_to_pass=PASS_TO_PASS)

    with pytest.raises(TareaRotaError):
        ejecutar(rota, config, runs)

    assert list(base.iterdir()) == []


def test_la_comprobacion_previa_aborta_si_la_tarea_no_discrimina(
    tarea, config, runs, agente
) -> None:
    """`test_doble` pasa con el bug puesto: esa tarea no mediria nada."""
    ejecutable = agente(stream(), escribe("agente_estuvo_aqui.txt", "si"))
    rota = dataclass_con(tarea, fail_to_pass=PASS_TO_PASS)

    with pytest.raises(TareaRotaError, match="T900"):
        ejecutar(rota, config, runs)

    # Y se aborta antes de gastar dinero.
    assert not (ejecutable.parent / "agente_estuvo_aqui.txt").exists()
    assert not runs.exists()


def dataclass_con(tarea: Tarea, **cambios) -> Tarea:
    from dataclasses import replace

    return replace(tarea, **cambios)


# ---------------------------------------------------------------------------
# Evaluacion: el veredicto lo dan los tests
# ---------------------------------------------------------------------------


def test_un_agente_que_arregla_el_bug_tiene_exito(tarea, config, runs, agente) -> None:
    agente(stream(), escribe("calc/suma.py", SUMA_CORRECTA))

    resultado = ejecutar(tarea, config, runs)

    assert resultado.exito
    assert resultado.fail_to_pass_ok
    assert resultado.pass_to_pass_ok


def test_un_agente_que_no_toca_nada_fracasa(tarea, config, runs, agente) -> None:
    agente(stream())

    resultado = ejecutar(tarea, config, runs)

    assert not resultado.exito
    assert not resultado.fail_to_pass_ok
    assert resultado.pass_to_pass_ok


def test_un_agente_que_rompe_otro_test_fracasa(tarea, config, runs, agente) -> None:
    agente(stream(), escribe("calc/suma.py", SUMA_ROMPE_EL_OTRO))

    resultado = ejecutar(tarea, config, runs)

    assert resultado.fail_to_pass_ok
    assert not resultado.pass_to_pass_ok
    assert not resultado.exito


def test_el_veredicto_sale_de_los_tests_no_de_lo_que_diga_el_agente(
    tarea, config, runs, agente
) -> None:
    """El agente afirma haberlo arreglado y no ha tocado el bug."""
    agente(stream(texto="Arreglado: la suma ya devuelve 5."))

    resultado = ejecutar(tarea, config, runs)

    assert not resultado.exito
    assert registro_en_disco(runs)["outcome"]["success"] is False


# ---------------------------------------------------------------------------
# Aislamiento
# ---------------------------------------------------------------------------


def test_un_stream_con_plugins_sigue_siendo_valido(tarea, config, runs, agente) -> None:
    """`--bare` los quitaria y rompe la autenticacion: se admiten y constan.

    Se cargan igual en A y en B, asi que no alteran la diferencia que
    mide R1; inflan la linea base y por eso el informe los declara.
    """
    agente(stream(plugins=("superpowers",)), escribe("calc/suma.py", SUMA_CORRECTA))

    resultado = ejecutar(tarea, config, runs)

    assert resultado.valido
    assert resultado.desviaciones == ()
    assert registro_en_disco(runs)["agent"]["plugins"] == ["superpowers@1.0.0"]


def test_un_servidor_mcp_invalida_la_ejecucion(tarea, config, runs, agente) -> None:
    """En modo A no debe quedar ninguno: ahi `--strict-mcp-config` si cumple."""
    agente(stream(servidores_mcp=("gmail",)), escribe("calc/suma.py", SUMA_CORRECTA))

    resultado = ejecutar(tarea, config, runs)

    assert not resultado.valido
    assert any("gmail" in d for d in resultado.desviaciones)
    registro = registro_en_disco(runs)
    assert registro["isolation"]["valid"] is False
    assert registro["isolation"]["deviations"] == list(resultado.desviaciones)


def test_un_stream_con_otro_modelo_invalida_la_ejecucion(tarea, config, runs, agente) -> None:
    agente(stream(modelo="claude-opus-5[1m]"))

    resultado = ejecutar(tarea, config, runs)

    assert not resultado.valido
    assert any("modelo" in d for d in resultado.desviaciones)


def test_el_modelo_esperado_y_sin_mcp_es_valido(tarea, config, runs, agente) -> None:
    agente(stream(), escribe("calc/suma.py", SUMA_CORRECTA))

    resultado = ejecutar(tarea, config, runs)

    assert resultado.valido
    assert resultado.desviaciones == ()


# ---------------------------------------------------------------------------
# Fallos del agente: son un dato, no un error del banco
# ---------------------------------------------------------------------------


def test_un_timeout_se_registra_y_no_propaga(tarea, config, runs, agente) -> None:
    agente(stream(), "time.sleep(30)\n")
    impaciente = replace(config, timeout_segundos=1)

    resultado = ejecutar(tarea, impaciente, runs)

    assert resultado.valido
    assert not resultado.exito
    assert resultado.run is None
    registro = registro_en_disco(runs)
    assert registro["outcome"]["timeout"] is True
    assert registro["cost"] is None


def test_un_stream_sin_result_invalida_la_ejecucion(tarea, config, runs, agente) -> None:
    agente(stream(con_result=False), escribe("calc/suma.py", SUMA_CORRECTA))

    resultado = ejecutar(tarea, config, runs)

    assert not resultado.valido
    assert resultado.run is None
    assert any("stream incompleto" in d for d in resultado.desviaciones)


def test_una_salida_vacia_no_tumba_la_ejecucion(tarea, config, runs, agente) -> None:
    agente("")

    resultado = ejecutar(tarea, config, runs)

    assert not resultado.valido
    assert resultado.run is None
    assert registro_en_disco(runs)["agent"] is None


def test_el_registro_de_modo_a_no_afirma_nada_de_arquigraph(tarea, config, runs, agente) -> None:
    agente(stream())

    resultado = ejecutar(tarea, config, runs)

    registro = registro_de(resultado)
    assert registro["mode"] == "A"
    assert registro["arquigraph"] is None
    assert registro["agent"]["model"] == MODELO
    assert registro["cost"]["total_cost_usd"] == 0.25
    assert registro["trajectory"] == [
        {"turn": 1, "tool": "Edit", "input": {"file_path": "calc/suma.py"}}
    ]


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------


def test_cada_registro_se_escribe_al_terminar_su_ejecucion(tarea, config, runs, agente) -> None:
    """La segunda tarea aborta; el registro de la primera ya esta en disco."""
    agente(stream())
    rota = dataclass_con(tarea, task_id="T901", fail_to_pass=PASS_TO_PASS)

    with pytest.raises(TareaRotaError):
        ejecutar_banco([tarea, rota], config, repeticiones=1, directorio_salida=runs)

    archivos = sorted(p.name for p in runs.glob("*.json"))
    assert len(archivos) == 1
    assert "_T900_A_r1" in archivos[0]


def test_el_tope_de_gasto_detiene_la_tanda(tarea, config, runs, agente, capsys) -> None:
    agente(stream(coste=0.25))
    otra = dataclass_con(tarea, task_id="T901")

    resumen = ejecutar_banco(
        [tarea, otra], config, repeticiones=1, directorio_salida=runs, tope_gasto_usd=0.20
    )

    assert resumen.detenido_por_tope
    assert len(resumen.resultados) == 1
    assert resumen.gasto_usd == pytest.approx(0.25)
    assert len(list(runs.glob("*.json"))) == 1


def test_imprime_una_linea_por_ejecucion(tarea, config, runs, agente, capsys) -> None:
    agente(stream(coste=0.4231, turnos=14), escribe("calc/suma.py", SUMA_CORRECTA))

    ejecutar_banco([tarea], config, repeticiones=2, directorio_salida=runs)

    lineas = [linea for linea in capsys.readouterr().out.splitlines() if linea.startswith("T900")]
    assert lineas == [
        "T900 r1  exito=si  $0.4231  14 turnos  61s",
        "T900 r2  exito=si  $0.4231  14 turnos  61s",
    ]


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------


AGENTE_DEL_BANCO = {
    "model": MODELO,
    "plugins": ["superpowers@1.0.0", "ralph-loop@1.0.0", "superdesign@1.0.0", "graphify@1.0.0"],
    "mcp_servers": [],
    "tools": ["Read", "Edit", "Bash"],
}


def registro_falso(
    task_id: str,
    valida: bool,
    exito: bool,
    coste: float,
    turnos: int,
    agent: dict | None = AGENTE_DEL_BANCO,
) -> dict:
    return {
        "run_id": f"2026-09-02T10-00-0{turnos}_{task_id}_A_r1",
        "task_id": task_id,
        "mode": "A",
        "agent": agent,
        "isolation": {"valid": valida, "deviations": [] if valida else ["servidor MCP"]},
        "outcome": {"success": exito},
        "cost": {"total_cost_usd": coste, "num_turns": turnos},
    }


def test_el_informe_ignora_las_ejecuciones_invalidas() -> None:
    informe = construir_informe(
        [
            registro_falso("T001", valida=True, exito=True, coste=0.10, turnos=8),
            registro_falso("T001", valida=True, exito=False, coste=0.30, turnos=12),
            registro_falso("T001", valida=False, exito=True, coste=9.00, turnos=90),
        ]
    )

    (t001,) = informe.por_tarea
    assert t001.validas == 2
    assert t001.descartadas == 1
    assert t001.tasa_exito == pytest.approx(0.5)
    assert t001.coste_medio_usd == pytest.approx(0.20)
    assert t001.desviacion_coste_usd == pytest.approx(0.10)
    assert t001.turnos_medios == pytest.approx(10.0)


def test_el_informe_agrega_el_total_sobre_todas_las_tareas() -> None:
    informe = construir_informe(
        [
            registro_falso("T001", valida=True, exito=True, coste=0.10, turnos=8),
            registro_falso("T003", valida=True, exito=False, coste=0.30, turnos=12),
        ]
    )

    assert [e.task_id for e in informe.por_tarea] == ["T001", "T003"]
    assert informe.total.validas == 2
    assert informe.total.tasa_exito == pytest.approx(0.5)
    assert informe.total.coste_medio_usd == pytest.approx(0.20)


def test_un_timeout_cuenta_como_intento_pero_no_como_coste() -> None:
    sin_coste = registro_falso("T001", valida=True, exito=False, coste=0.0, turnos=0)
    sin_coste["cost"] = None

    (t001,) = construir_informe(
        [registro_falso("T001", valida=True, exito=True, coste=0.10, turnos=8), sin_coste]
    ).por_tarea

    assert t001.validas == 2
    assert t001.con_coste == 1
    assert t001.tasa_exito == pytest.approx(0.5)
    assert t001.coste_medio_usd == pytest.approx(0.10)


def test_el_informe_declara_el_entorno_observado() -> None:
    """Sale del `init`, no de la configuracion: es lo que de verdad corrio."""
    informe = construir_informe(
        [registro_falso("T001", valida=True, exito=True, coste=0.10, turnos=8)]
    )

    assert formatear(informe).splitlines()[0] == (
        "entorno: claude-sonnet-5 | 4 plugins | 0 servidores MCP | 3 herramientas"
    )


def test_una_tanda_con_dos_entornos_los_declara_los_dos() -> None:
    """Esconder la mezcla seria promediar cosas que no son la misma."""
    otro = {**AGENTE_DEL_BANCO, "mcp_servers": [{"name": "arquigraph"}], "plugins": []}

    informe = construir_informe(
        [
            registro_falso("T001", valida=True, exito=True, coste=0.10, turnos=8),
            registro_falso("T003", valida=True, exito=True, coste=0.20, turnos=9, agent=otro),
        ]
    )

    assert formatear(informe).splitlines()[:2] == [
        "entorno: claude-sonnet-5 | 4 plugins | 0 servidores MCP | 3 herramientas",
        "entorno: claude-sonnet-5 | 0 plugins | 1 servidor MCP | 3 herramientas",
    ]


def test_sin_init_el_entorno_no_se_inventa() -> None:
    informe = construir_informe(
        [registro_falso("T001", valida=False, exito=False, coste=0.0, turnos=0, agent=None)]
    )

    assert informe.entornos == ()
    assert formatear(informe).splitlines()[0] == f"entorno: {SIN_ENTORNO}"


# ---------------------------------------------------------------------------
# Lectura de tareas
# ---------------------------------------------------------------------------


def test_una_tarea_se_lee_del_json_del_banco(tmp_path: Path) -> None:
    tareas = tmp_path / "tasks"
    tareas.mkdir()
    (tareas / "T001.json").write_text(
        json.dumps(
            {
                "task_id": "T001",
                "corpus": "tienda",
                "bug_patch": "T001.bug.patch",
                "problem_statement": "El IVA se cobra sin descontar.",
                "fail_to_pass": ["tests/test_precios.py::test_iva"],
                "pass_to_pass": ["tests/test_precios.py::test_base"],
                "hint_files": ["tienda/dominio/precios.py"],
            }
        )
    )

    tarea = cargar_tarea(tareas / "T001.json")

    assert tarea.task_id == "T001"
    assert tarea.directorio_corpus == tmp_path / "corpus" / "tienda"
    assert tarea.parche == tareas / "T001.bug.patch"
    assert tarea.hint_files == ("tienda/dominio/precios.py",)


def test_pedir_una_tarea_que_no_existe_es_un_error(tmp_path: Path) -> None:
    tareas = tmp_path / "tasks"
    tareas.mkdir()

    with pytest.raises(FileNotFoundError, match="T404"):
        cargar_tareas(tareas, ["T404"])


def test_las_tareas_reales_del_banco_se_leen() -> None:
    banco = Path(__file__).resolve().parents[1] / "bench" / "tasks"

    tareas = cargar_tareas(banco, ["T001", "T003"])

    assert [t.task_id for t in tareas] == ["T001", "T003"]
    assert all(t.parche.is_file() and t.directorio_corpus.is_dir() for t in tareas)

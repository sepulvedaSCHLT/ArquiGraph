"""Ejecucion de una tarea del banco en modo A (SPEC-FASE-0 seccion 7, paso 9).

Este modulo produce el baseline contra el que se compara todo. Si mide
mal, el criterio de kill de R1 se evalua sobre un numero falso. De ahi
tres reglas que no son negociables:

1. **El runner evalua, el agente no.** Cuando el agente suelta el
   control, el runner corre ``fail_to_pass`` y ``pass_to_pass`` con su
   propio interprete. Que el agente diga "ya esta" no cuenta: puede no
   haberlo comprobado, o haber roto otra cosa.
2. **Aislamiento verificado en cada ejecucion.** El comando se
   construye para aislar --``--strict-mcp-config``, herramientas
   fijadas-- y despues se comprueba contra el ``init`` de lo que la
   ejecucion **hizo**. Una desviacion la marca invalida y la deja fuera
   de la media. Los plugins del autor son la excepcion declarada: no hay
   forma de quitarlos sin romper la autenticacion, asi que se admiten
   como offset constante en A y en B.
3. **Nada se escribe en el corpus original.** Cada ejecucion trabaja
   sobre una copia en un temporal; ``bench/corpus/`` es de solo lectura.

Modo A unicamente: sin MCP y sin ArquiGraph. El modo B llega en Fase 1.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from arquigraph.bench.ledger.isolation import ExpectedEnvironment, check_isolation
from arquigraph.bench.ledger.stream import IncompleteStreamError, ParsedRun, parse_stream
from arquigraph.bench.runner.registro import escribir_registro
from arquigraph.bench.runner.tareas import Tarea

__all__ = [
    "MODO_A",
    "VARIABLE_EJECUTABLE",
    "ConfiguracionBanco",
    "ResultadoEjecucion",
    "TareaRotaError",
    "ejecutar_tarea",
]

MODO_A = "A"

# Regenerable y solo ensucia la copia.
IGNORAR = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", ".coverage")

# El runner no deja bytecode en la copia: ver `_tirar_el_bytecode`.
SIN_BYTECODE = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

# El binario del agente. Existe como variable de entorno para que los
# tests puedan apuntar a un ejecutable falso: un test que invoque al
# agente real cuesta dinero, y eso no es un test.
VARIABLE_EJECUTABLE = "ARQUIGRAPH_BENCH_AGENTE"


class TareaRotaError(RuntimeError):
    """La tarea ya no discrimina: con el bug puesto, ``fail_to_pass`` pasa."""


@dataclass(frozen=True)
class ConfiguracionBanco:
    """Como se invoca al agente y como se evalua lo que deja.

    ``modelo`` se usa para dos cosas: se le pasa al agente en
    ``--model`` y se compara con el modelo que el evento ``init``
    declara. Por eso debe ser el identificador completo que el ``init``
    devuelve; un alias haria fallar el aislamiento en cada ejecucion.

    ``herramientas`` alimenta **las dos** banderas: ``--tools`` decide
    que herramientas existen y ``--allowedTools`` cuales se
    auto-aprueban. Pasar solo la segunda deja el conjunto integrado
    entero en el prompt de sistema.

    ``settings`` es opcional y no aisla nada: probado contra el CLI real,
    un ``settings.json`` con ``enabledPlugins: {}`` deja los plugins y
    los servidores MCP cargados (FINDINGS-token-accounting 3.2). Si se
    pasa se usa; si no, la bandera se omite.

    ``strict_mcp`` es lo que si aisla, y va en los dos modos: en A, sin
    ``mcp_config``, deja cero servidores; en B, con el, deja solo
    ArquiGraph. Esa simetria es lo que hace limpia la comparacion.

    ``interprete_tests`` existe porque el ``python`` del sistema no tiene
    ``pytest``: el runner recibe la ruta correcta, tipicamente la del
    ``.venv`` del proyecto.
    """

    modelo: str
    herramientas: tuple[str, ...]  # --tools y --allowedTools: la misma lista
    settings: Path | None = None  # opcional: no aisla nada
    timeout_segundos: int = 900
    interprete_tests: str = "python"  # el que usa el RUNNER para evaluar
    mcp_config: Path | None = None  # solo modo B; en A va None
    strict_mcp: bool = True  # SIEMPRE True en el banco


@dataclass(frozen=True)
class ResultadoEjecucion:
    """Lo observado en una ejecucion, ya verificado por el runner."""

    run_id: str
    task_id: str
    modo: str  # "A"
    repeticion: int
    iniciado_en: str  # ISO 8601 UTC
    valido: bool  # False si el aislamiento fallo
    desviaciones: tuple[str, ...]
    exito: bool
    fail_to_pass_ok: bool
    pass_to_pass_ok: bool
    run: ParsedRun | None  # None si el agente ni siquiera arranco


def ejecutar_tarea(
    tarea: Tarea,
    config: ConfiguracionBanco,
    repeticion: int,
    directorio_salida: Path,
) -> ResultadoEjecucion:
    """Ejecuta una tarea en modo A y devuelve su resultado verificado.

    Raises:
        TareaRotaError: si la comprobacion previa detecta que la tarea ya
            no discrimina.
        RuntimeError: si el parche no se puede aplicar.
    """
    iniciado = datetime.now(UTC)

    with tempfile.TemporaryDirectory(prefix=f"bench-{tarea.task_id}-") as temporal:
        trabajo = Path(temporal) / tarea.corpus
        shutil.copytree(tarea.directorio_corpus, trabajo, ignore=IGNORAR)
        _aplicar_parche(tarea.parche, trabajo)
        _comprobacion_previa(tarea, config, trabajo)

        salida, hubo_timeout = _invocar_agente(tarea, config, trabajo)

        run: ParsedRun | None = None
        desviaciones: list[str] = []
        valido = True
        fail_to_pass_ok = False
        pass_to_pass_ok = False

        if hubo_timeout:
            # El agente se quedo sin tiempo: no es un intento terminado y
            # no se le evalua. Es un dato, no un error del banco.
            pass
        else:
            try:
                run = parse_stream(salida.splitlines())
            except IncompleteStreamError as error:
                # Sin `result` no hay coste fiable que registrar.
                valido = False
                desviaciones.append(f"stream incompleto: {error}")
            else:
                desviaciones += check_isolation(run.agent, _entorno_esperado(config))
                valido = not desviaciones

            # Regla 1: el veredicto sale de aqui, no de lo que diga el agente.
            fail_to_pass_ok = _tests_pasan(config, trabajo, tarea.fail_to_pass)
            pass_to_pass_ok = _tests_pasan(config, trabajo, tarea.pass_to_pass)

        resultado = ResultadoEjecucion(
            run_id=_run_id(tarea, repeticion, iniciado),
            task_id=tarea.task_id,
            modo=MODO_A,
            repeticion=repeticion,
            iniciado_en=iniciado.strftime("%Y-%m-%dT%H:%M:%SZ"),
            valido=valido,
            desviaciones=tuple(desviaciones),
            exito=fail_to_pass_ok and pass_to_pass_ok,
            fail_to_pass_ok=fail_to_pass_ok,
            pass_to_pass_ok=pass_to_pass_ok,
            run=run,
        )
        escribir_registro(resultado, directorio_salida)

    return resultado


# ---------------------------------------------------------------------------
# Preparacion del directorio de trabajo
# ---------------------------------------------------------------------------


def _aplicar_parche(parche: Path, trabajo: Path) -> None:
    """Aplica el parche del bug con ``git apply``, y si no, con ``patch``."""
    errores = []
    for orden in (
        ["git", "apply", "-p1", str(parche)],
        ["patch", "-p1", "-s", "-i", str(parche)],
    ):
        proceso = _ejecutar(orden, trabajo)
        if proceso.returncode == 0:
            return
        errores.append(f"{orden[0]}: {(proceso.stderr or proceso.stdout).strip()}")
    raise RuntimeError(f"no se pudo aplicar {parche.name}\n  " + "\n  ".join(errores))


def _comprobacion_previa(tarea: Tarea, config: ConfiguracionBanco, trabajo: Path) -> None:
    """Con el bug puesto, ``fail_to_pass`` DEBE fallar.

    No es paranoia: si el parche no se aplico donde debia, o el corpus
    cambio, la tarea deja de discriminar y el resultado de la ejecucion
    no significaria nada.
    """
    if _tests_pasan(config, trabajo, tarea.fail_to_pass):
        raise TareaRotaError(
            f"{tarea.task_id}: con el bug aplicado, fail_to_pass pasa. "
            "La tarea no discrimina y su resultado no mediria nada."
        )


# ---------------------------------------------------------------------------
# El agente
# ---------------------------------------------------------------------------


def _invocar_agente(tarea: Tarea, config: ConfiguracionBanco, trabajo: Path) -> tuple[str, bool]:
    """Lanza al agente sobre el directorio de trabajo.

    El ``problem_statement`` va tal cual, sin anadir nada: ni el nombre
    de los tests, ni una pista de donde mirar. Cualquier texto adicional
    contamina el modo A y arruina la comparacion con B.

    Devuelve la salida (``stdout`` y ``stderr`` juntos; el ledger ya
    cuenta las lineas que no son JSON) y si expiro el tiempo.
    """
    try:
        proceso = subprocess.run(
            _orden_del_agente(tarea, config),
            cwd=trabajo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=config.timeout_segundos,
            check=False,
        )
    except subprocess.TimeoutExpired as expirado:
        return _texto(expirado.stdout), True
    return proceso.stdout or "", False


def _orden_del_agente(tarea: Tarea, config: ConfiguracionBanco) -> list[str]:
    """El comando exacto con el que se invoca al agente.

    Las banderas y su orden salen de cinco pre-vuelos contra el CLI real
    (FINDINGS-token-accounting 3.2). Lo que se aprendio ahi:

    - ``--tools`` y ``--allowedTools`` reciben la misma lista. La primera
      controla que herramientas existen; la segunda, cuales no piden
      permiso. Solo la segunda deja el conjunto integrado entero dentro.
    - ``--strict-mcp-config`` es la unica bandera que quita los
      servidores MCP sin tocar la autenticacion. Decir "ok" costo $0.2340
      con 72 herramientas y $0.0251 con 3: el manifiesto MCP es contexto
      precargado, y se paga se use o no.
    - ``--bare`` aislaria mas, pero solo admite ``ANTHROPIC_API_KEY`` y
      rompe la sesion OAuth. No se usa en ninguna ruta de codigo.
    - ``--settings`` no desactiva nada, asi que se omite si no se pasa.
    """
    herramientas = ",".join(config.herramientas)
    orden = [
        _ejecutable_agente(),
        "-p",
        tarea.problem_statement,
        "--model",
        config.modelo,
        "--tools",
        herramientas,
        "--allowedTools",
        herramientas,
    ]
    if config.strict_mcp:
        orden.append("--strict-mcp-config")
    if config.mcp_config is not None:
        orden += ["--mcp-config", str(config.mcp_config)]
    if config.settings is not None:
        orden += ["--settings", str(config.settings)]
    orden += ["--output-format", "stream-json", "--include-hook-events", "--verbose"]
    return orden


def _ejecutable_agente() -> str:
    return os.environ.get(VARIABLE_EJECUTABLE, "claude")


def _texto(salida: str | bytes | None) -> str:
    """``TimeoutExpired`` devuelve bytes aunque el proceso fuera de texto."""
    if salida is None:
        return ""
    return salida if isinstance(salida, str) else salida.decode("utf-8", "replace")


def _entorno_esperado(config: ConfiguracionBanco) -> ExpectedEnvironment:
    """Modo A: el modelo declarado y sin servidores MCP.

    Los servidores MCP siguen sin permitirse: ahi ``--strict-mcp-config``
    si funciona, y una desviacion significa que algo fallo de verdad.
    """
    return ExpectedEnvironment(
        model=config.modelo,
        # --bare los eliminaria pero rompe la autenticacion OAuth (FINDINGS
        # token-accounting 3.2). Son un offset constante en A y en B: no alteran
        # la diferencia que mide R1, aunque inflan la linea base.
        allow_plugins=True,
    )


# ---------------------------------------------------------------------------
# Los tests, corridos por el runner
# ---------------------------------------------------------------------------


def _tests_pasan(config: ConfiguracionBanco, trabajo: Path, nodos: tuple[str, ...]) -> bool:
    """``<interprete> -m pytest -q <nodos>`` en el directorio de trabajo.

    Los dos conjuntos se corren por separado para poder decir cual de los
    dos fallo.
    """
    if not nodos:
        # Sin nodos no hay nada que comprobar. Nunca `pytest` a secas:
        # recogeria todo el corpus y mediria otra cosa.
        return True
    _tirar_el_bytecode(trabajo)
    orden = [config.interprete_tests, "-m", "pytest", "-q", *nodos]
    return _ejecutar(orden, trabajo, SIN_BYTECODE).returncode == 0


def _tirar_el_bytecode(trabajo: Path) -> None:
    """Borra el bytecode de la copia antes de evaluar.

    Python valida el ``.pyc`` por ``(mtime, tamano)`` con precision de
    segundo: una edicion del mismo tamano hecha en el mismo segundo que
    la compilacion anterior reutiliza el bytecode viejo. El veredicto
    saldria entonces del codigo que el agente ya habia cambiado, que es
    justo lo que la regla 1 prohibe.
    """
    for cache in trabajo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _ejecutar(
    orden: list[str], directorio: Path, entorno: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        orden, cwd=directorio, capture_output=True, text=True, check=False, env=entorno
    )


def _run_id(tarea: Tarea, repeticion: int, iniciado: datetime) -> str:
    marca = iniciado.strftime("%Y-%m-%dT%H-%M-%S")
    return f"{marca}_{tarea.task_id}_{MODO_A}_r{repeticion}"

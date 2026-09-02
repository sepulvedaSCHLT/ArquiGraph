"""Ejecucion de una tarea del banco en modo A (SPEC-FASE-0 seccion 7, paso 9).

Este modulo produce el baseline contra el que se compara todo. Si mide
mal, el criterio de kill de R1 se evalua sobre un numero falso. De ahi
tres reglas que no son negociables:

1. **El runner evalua, el agente no.** Cuando el agente suelta el
   control, el runner corre ``fail_to_pass`` y ``pass_to_pass`` con su
   propio interprete. Que el agente diga "ya esta" no cuenta: puede no
   haberlo comprobado, o haber roto otra cosa.
2. **Aislamiento verificado en cada ejecucion.** Una ejecucion con los
   plugins de quien la lanza mide esos plugins, no el baseline; se marca
   invalida y no entra en la media.
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

    ``interprete_tests`` existe porque el ``python`` del sistema no tiene
    ``pytest``: el runner recibe la ruta correcta, tipicamente la del
    ``.venv`` del proyecto.
    """

    modelo: str
    herramientas: tuple[str, ...]  # --allowedTools
    settings: Path  # bench/config/settings.bench.json
    timeout_segundos: int = 900
    interprete_tests: str = "python"  # el que usa el RUNNER para evaluar


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
    orden = [
        _ejecutable_agente(),
        "-p",
        tarea.problem_statement,
        "--settings",
        str(config.settings),
        "--model",
        config.modelo,
        "--allowedTools",
        ",".join(config.herramientas),
        "--output-format",
        "stream-json",
        "--include-hook-events",
        "--verbose",
    ]
    try:
        proceso = subprocess.run(
            orden,
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


def _ejecutable_agente() -> str:
    return os.environ.get(VARIABLE_EJECUTABLE, "claude")


def _texto(salida: str | bytes | None) -> str:
    """``TimeoutExpired`` devuelve bytes aunque el proceso fuera de texto."""
    if salida is None:
        return ""
    return salida if isinstance(salida, str) else salida.decode("utf-8", "replace")


def _entorno_esperado(config: ConfiguracionBanco) -> ExpectedEnvironment:
    """Modo A: el modelo declarado, sin plugins y sin servidores MCP."""
    return ExpectedEnvironment(model=config.modelo)


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

# Prompt — Paso 9: el runner del banco

> Especificación ejecutable para `arquigraph/bench/runner/`.
> Paso 9 de [SPEC-FASE-0 §7](../SPEC-FASE-0.md), formato de registro en [§4](../SPEC-FASE-0.md).
> Corpus y tareas: [ADR-010](../adr/ADR-010-corpus-sintetico.md).
>
> **Alcance: modo A únicamente** (sin ArquiGraph). El modo B llega en Fase 1,
> cuando exista el servidor MCP. **No implementar nada del modo B aquí.**

---

## Por qué este módulo decide el proyecto

Produce el baseline contra el que se compara todo. Si mide mal, el criterio de kill de R1 se evalúa sobre un número falso y el proyecto entero avanza a ciegas.

De ahí las tres reglas que siguen. No son sugerencias.

---

## Regla 1 — El runner evalúa, el agente no

> Cuando el agente termina, **el runner ejecuta los tests por su cuenta** y decide si la tarea se resolvió.

Nunca se cree que el agente diga "ya está". Un agente puede declarar éxito sin haberlo comprobado, o haber roto otra cosa. El veredicto sale de ejecutar `fail_to_pass` y `pass_to_pass` con el intérprete del runner, después de que el agente haya soltado el control.

## Regla 2 — Aislamiento verificado en cada ejecución

> Tras parsear el stream, se llama a `check_isolation`. Si devuelve desviaciones, **la ejecución se marca inválida y no entra en la media**.

Ya existe en `arquigraph/bench/ledger/isolation.py`. Una ejecución con los plugins del autor cargados mide los plugins del autor, no el baseline.

## Regla 3 — Nada se escribe en el corpus original

> Cada ejecución trabaja sobre una **copia** en un directorio temporal. `bench/corpus/tienda/` es de solo lectura para el runner.

---

## Objetivo

```python
# arquigraph/bench/runner/ejecutor.py

@dataclass(frozen=True)
class ConfiguracionBanco:
    modelo: str
    herramientas: tuple[str, ...]        # --allowedTools
    settings: Path                        # bench/config/settings.bench.json
    timeout_segundos: int = 900
    interprete_tests: str = "python"      # el que usa el RUNNER para evaluar


@dataclass(frozen=True)
class ResultadoEjecucion:
    run_id: str
    task_id: str
    modo: str                 # "A"
    repeticion: int
    iniciado_en: str          # ISO 8601 UTC
    valido: bool              # False si el aislamiento fallo
    desviaciones: tuple[str, ...]
    exito: bool
    fail_to_pass_ok: bool
    pass_to_pass_ok: bool
    run: ParsedRun | None     # None si el agente ni siquiera arranco


def ejecutar_tarea(
    tarea: Tarea,
    config: ConfiguracionBanco,
    repeticion: int,
    directorio_salida: Path,
) -> ResultadoEjecucion:
    """Ejecuta una tarea en modo A y devuelve su resultado verificado."""
```

### Secuencia de una ejecución

```
1. Copiar bench/corpus/<corpus>/ a un directorio temporal
2. Aplicar <task_id>.bug.patch
3. Comprobacion previa: correr fail_to_pass -> DEBE fallar
     si pasa, la tarea esta rota: abortar con error claro
4. Invocar al agente sobre el directorio temporal
5. Parsear el stream con el ledger
6. check_isolation -> si hay desviaciones, valido = False
7. EL RUNNER corre fail_to_pass y pass_to_pass
8. exito = fail_to_pass_ok and pass_to_pass_ok
9. Escribir el registro en bench/runs/<run_id>.json
10. Borrar el directorio temporal
```

El paso 3 no es paranoia: si el parche no se aplicó bien, o el corpus cambió, la tarea deja de discriminar y el resultado no significaría nada.

---

## Invocación del agente

```bash
claude -p "<problem_statement>" \
  --settings <config.settings> \
  --model <config.modelo> \
  --allowedTools "<config.herramientas>" \
  --output-format stream-json \
  --include-hook-events \
  --verbose
```

Ejecutado con `cwd` en el directorio temporal, `subprocess.run` con `timeout`, capturando `stdout` y `stderr` juntos (el ledger ya cuenta las líneas que no son JSON).

**El `problem_statement` va tal cual, sin añadir nada.** Ni instrucciones extra, ni el nombre de los tests, ni una pista de dónde mirar. Cualquier texto adicional contamina el modo A y arruina la comparación con B.

**`hint_files` no se le pasa nunca al agente.** Existe para documentar dónde vive el bug, no para dárselo.

### Si el agente falla

| Situación | Resultado |
|---|---|
| Timeout | `valido=True`, `exito=False`, `run=None`, registrado como timeout |
| Código de salida distinto de 0 | Se intenta parsear igualmente; si no hay `result`, `run=None` |
| `IncompleteStreamError` | `valido=False` — no hay coste fiable que registrar |

Un fallo del agente **es un dato**, no un error del banco. Se registra y cuenta como intento sin éxito.

---

## Ejecución de los tests por el runner

```bash
<config.interprete_tests> -m pytest -q <test_id_1> <test_id_2> ...
```

Con `cwd` en el directorio temporal. Se ejecutan **por separado** los `fail_to_pass` y los `pass_to_pass`, para poder decir cuál de los dos falló.

`interprete_tests` existe porque el `python3` del sistema no tiene `pytest`; el runner recibe la ruta correcta (típicamente el del `.venv` del proyecto).

---

## Orquestación y piloto

```python
# arquigraph/bench/runner/orquestador.py

def ejecutar_banco(
    tareas: list[Tarea],
    config: ConfiguracionBanco,
    repeticiones: int,
    directorio_salida: Path,
    tope_gasto_usd: float | None = None,
) -> ResumenBanco:
    """Ejecuta todas las tareas en secuencial."""
```

- **Secuencial**, no paralelo. La máquina tiene 4 núcleos y otros proyectos encima.
- **`tope_gasto_usd`**: si el acumulado lo supera, se detiene y devuelve lo hecho hasta ahí. Es la red de seguridad contra una fuga de gasto por un bucle del agente.
- Tras cada ejecución, imprimir una línea: `T003 r1  exito=si  $0.4231  14 turnos  62s`
- Ir escribiendo cada registro a disco **al terminar cada ejecución**, no al final. Si se corta, no se pierde lo pagado.

### CLI

```
arqui bench run --mode A --repeticiones N [--tareas T001,T003] [--tope-usd 5.0]
arqui bench report
```

`arqui bench report` lee `bench/runs/*.json` y produce por tarea y en total: tasa de éxito, coste medio y desviación, turnos medios, y cuántas ejecuciones se descartaron por aislamiento.

---

## Restricciones

1. **Solo modo A.** Nada de MCP, nada de ArquiGraph inyectado. El bloque `arquigraph` del registro va a `null`.
2. **No modificar** `bench/corpus/`, `bench/tasks/`, `arquigraph/bench/ledger/` ni nada de `core/`.
3. **Sin dependencias nuevas.** Librería estándar (ADR-009).
4. **Sin telemetría.** Todo queda en `bench/runs/` (ADR: ARCHITECTURE §16.4).
5. **Los tests unitarios de este módulo no invocan al agente.** Se prueba con un ejecutable falso que emite un stream fijo. Un test que gaste dinero no es un test.

---

## Criterios de aceptación

Tests en `tests/test_runner.py`, **todos sin llamar al agente real**.

### Preparación del entorno

- [ ] Copia el corpus a un temporal y no toca el original
- [ ] Aplica el parche correctamente
- [ ] Borra el temporal al terminar, también si hubo excepción
- [ ] La comprobación previa detecta una tarea que ya no discrimina y aborta

### Evaluación

- [ ] Con un agente falso que arregla el bug → `exito=True`
- [ ] Con un agente falso que no toca nada → `exito=False`, `fail_to_pass_ok=False`
- [ ] Con un agente falso que rompe otro test → `pass_to_pass_ok=False`, `exito=False`
- [ ] **El veredicto sale de los tests, no de lo que diga el agente**

### Aislamiento

- [ ] Stream con plugins cargados → `valido=False` y las desviaciones en el registro
- [ ] Stream con el modelo esperado y sin plugins → `valido=True`

### Fallos del agente

- [ ] Timeout → registro con `exito=False`, sin excepción propagada
- [ ] Stream sin `result` → `valido=False`
- [ ] Salida vacía → `valido=False`, sin caída

### Orquestación

- [ ] Cada registro se escribe al terminar su ejecución, no al final
- [ ] `tope_gasto_usd` detiene la tanda al superarse
- [ ] `report` calcula media y dispersión sobre las ejecuciones válidas, ignorando las inválidas

---

## Verificación

```bash
uv run pytest -q          # 152 + los nuevos
uv run ruff check .
uv run ruff format --check .
```

**No ejecutar el banco real en este paso.** El piloto de coste se lanza después, a mano, con `--tareas T001,T007 --repeticiones 2 --tope-usd 5.0`.

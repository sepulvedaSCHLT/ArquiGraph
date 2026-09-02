# Prompt — Paso 9b: aislar la invocación del agente

> Corrección al paso 9, derivada de cinco pruebas reales contra Claude Code.
> Hallazgos completos en [FINDINGS-token-accounting.md §3.2](../FINDINGS-token-accounting.md).
>
> **Alcance: solo la construcción del comando y su configuración.** No se
> cambia la lógica de evaluación ni el ledger.

---

## Qué se descubrió

Cinco pre-vuelos contra el CLI real:

| Intento | Resultado |
|---|---|
| `--settings` con `enabledPlugins: {}` | **No desactiva nada.** Plugins y MCP siguen cargados. |
| `--bare` | Aísla bien, pero **rompe la autenticación**: solo admite `ANTHROPIC_API_KEY`, no OAuth. Inservible. |
| `--plugin-dir <vacío>` | **Añade** un plugin, no reemplaza. Herramienta equivocada. |
| `--tools` | Filtra solo las herramientas **integradas**, no las de MCP. |
| **`--strict-mcp-config`** | ✅ **Elimina los servidores MCP sin tocar la autenticación.** |

Coste de decir "ok", mismo modelo y mismo turno: **$0.2340 con 72 herramientas, $0.0251 con 3**.

---

## Cambio 1 — Nuevos campos en `ConfiguracionBanco`

```python
@dataclass(frozen=True)
class ConfiguracionBanco:
    modelo: str
    herramientas: tuple[str, ...]
    settings: Path | None = None          # ahora opcional: no aisla nada
    timeout_segundos: int = 900
    interprete_tests: str = "python"
    mcp_config: Path | None = None        # solo modo B; en A va None
    strict_mcp: bool = True               # SIEMPRE True en el banco
```

`settings` pasa a opcional porque no cumple la función que le atribuimos. Si se pasa, se usa; si no, se omite del comando.

## Cambio 2 — Construcción del comando

```
claude -p <problem_statement>
  --model <modelo>
  --tools "<herramientas>"
  --allowedTools "<herramientas>"
  --strict-mcp-config              # si strict_mcp
  --mcp-config <ruta>              # solo si mcp_config no es None
  --settings <ruta>                # solo si settings no es None
  --output-format stream-json
  --include-hook-events
  --verbose
```

Puntos que importan:

1. **`--tools` y `--allowedTools` reciben la misma lista.** El primero controla qué herramientas **existen**; el segundo, cuáles se auto-aprueban. Pasar solo el segundo deja 95 herramientas en el prompt de sistema.
2. **`--strict-mcp-config` siempre**, en A y en B. En A sin `--mcp-config` deja cero servidores; en B con él, deja **solo ArquiGraph**. La simetría es lo que hace limpia la comparación.
3. **Nada de `--bare`.** Rompe la autenticación OAuth.

## Cambio 3 — Herramientas por defecto

```python
HERRAMIENTAS_POR_DEFECTO = "Read,Edit,Bash"
```

`Glob` y `Grep` **no existen** en el conjunto integrado bajo esos nombres: al pedirlos, el `init` devolvía solo `Bash`, `Edit` y `Read`. El agente usa `Bash` para buscar. Documentar el porqué en un comentario, no dejarlo como accidente.

## Cambio 4 — El aislamiento admite los plugins como constante

`--bare` es la única forma de quitar los plugins y no se puede usar. Los cuatro plugins del autor se cargan en A y en B por igual.

```python
@dataclass(frozen=True)
class ExpectedEnvironment:
    model: str
    allow_plugins: bool = False
    allowed_mcp_servers: tuple[str, ...] = ()
```

El banco construye su `ExpectedEnvironment` con **`allow_plugins=True`**, y el motivo va en un comentario junto a la llamada:

```python
# --bare los eliminaria pero rompe la autenticacion OAuth (FINDINGS
# token-accounting 3.2). Son un offset constante en A y en B: no alteran
# la diferencia que mide R1, aunque inflan la linea base.
```

Los servidores MCP **siguen sin permitirse** en modo A: ahí `--strict-mcp-config` sí funciona, y una desviación significa que algo falló de verdad.

## Cambio 5 — El informe lo declara

`arqui bench report` añade al encabezado una línea con el entorno realmente observado:

```
entorno: claude-sonnet-5 | 4 plugins | 0 servidores MCP | 3 herramientas
```

Sale del `init` de los registros, no de la configuración. Si un lector no puede ver en qué condiciones se midió, la cifra no vale ([ADR-007](../adr/ADR-007-licencia.md)).

---

## Restricciones

1. **No tocar** la secuencia de evaluación, el ledger ni `bench/corpus/`.
2. **No usar `--bare`** en ninguna ruta de código.
3. Sin dependencias nuevas.
4. Los tests siguen sin invocar al agente real.

## Criterios de aceptación

- [ ] El comando construido incluye `--strict-mcp-config` en modo A
- [ ] `--tools` y `--allowedTools` reciben la misma lista
- [ ] `--settings` se omite del comando cuando es `None`
- [ ] `--mcp-config` se omite cuando es `None`
- [ ] `--bare` no aparece en ninguna parte del código
- [ ] Un stream con plugins y `allow_plugins=True` → **válido**
- [ ] Un stream con un servidor MCP en modo A → **inválido**
- [ ] `report` imprime la línea de entorno derivada del `init`
- [ ] `uv run pytest -q` sigue verde

## Verificación

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

# Fase 0 — Procedimiento de arranque

> **Objetivo de la fase:** llegar a un baseline medido y reproducible, y a un grafo funcionando sobre el propio repositorio, **sin haber escrito ni una línea del recuperador**.
>
> **Principio rector:** los pasos están ordenados de **más barato y más decisivo** a más caro. Cada paso tiene una puerta. Si una puerta no se pasa, se para y se replantea — no se sigue construyendo encima.

---

## La idea que ordena todo

> **El baseline se mide antes de construir nada, porque no necesita nada.**

Medir cómo se comporta el agente **sin** ArquiGraph no requiere parser, ni grafo, ni memoria. Solo el corpus y el contador de tokens.

Hacerlo primero da tres cosas:

1. El número que todo lo demás tiene que batir.
2. Una publicación honesta en el README desde la primera semana.
3. Protección contra el peor escenario: construir tres semanas y descubrir entonces que no había nada que ganar.

Construir el parser antes del baseline es el error natural y es el caro.

---

## Paso 0 — Repositorio base

**Duración:** ~1 hora · **Riesgo:** ninguno

### Limpieza previa

El repositorio contiene hoy **dos cuerpos de material ajeno** que deben salir del árbol:

| Directorio | Qué es | Por qué sale |
|---|---|---|
| `graphify-out/` | ~1.361 archivos de caché generada por una herramienta de terceros | Regenerable; ruido que confunde el mensaje del portafolio |
| `engram/` | **Código fuente completo de otro proyecto**, con sus activos de marca (logos, banner) | Mezcla licencias en un árbol Apache 2.0, incluye marca ajena, y **contradice ADR-001** ("cero código de Graphify o Engram") |

`engram/` es el caso serio: no es salida, es el proyecto de otra persona dentro del tuyo. Además contaminaría el dogfooding — `arqui build .` parsearía código que no escribiste.

**Diagnóstico primero** (no ejecutar a ciegas: pueden ser submódulos o repos anidados):

```bash
git status --short | head -20
git ls-files engram/ | head -5
git ls-files graphify-out/ | head -5
cat .gitmodules 2>/dev/null
ls -d engram/.git graphify-out/.git 2>/dev/null
```

**Si están versionados como archivos normales:**

```bash
git rm -r --cached engram/ graphify-out/
printf 'engram/\ngraphify-out/\n.arquigraph/\n' >> .gitignore
git add .gitignore
git commit -m "chore: excluir repos de referencia y caché del control de versiones"
```

**Si son submódulos** (`.gitmodules` existe), el procedimiento es distinto: `git submodule deinit` + `git rm`.

**Reubicación, no borrado.** Siguen siendo referencia legítima (RESEARCH.md §5). Fuera del árbol:

```bash
mkdir -p ~/ref && mv engram ~/ref/engram
```

### Andamiaje

```
arquigraph/
  core/  memory/  guardian/  bench/  mcp/  hooks/  cli/
tests/
docs/          ← ya existe
.github/workflows/ci.yml
pyproject.toml
LICENSE        ← Apache 2.0 (ADR-007)
README.md
```

- `pyproject.toml` gestionado con `uv`; `ruff` y `pytest` configurados
- Un test trivial que pase
- `ci.yml` que ejecute `ruff check` y `pytest`
- `DCO` en `CONTRIBUTING.md` (ADR-007)

### Puerta

> Un PR abierto y **CI en verde**. Desde este momento, todo entra por PR — es el flujo que después vigilará el guardián.

---

## Paso 1 — R6: contabilidad de tokens ← **LA COMPUERTA**

**Duración:** ~medio día · **Riesgo:** 🔴 **bloqueante del proyecto entero**

Todo —el banco, el criterio de kill de R1, el principio P7— depende de poder contar tokens de forma programática. Si no se puede, ArquiGraph no se puede evaluar y no tiene sentido construirlo.

### Qué hacer

1. Ejecutar Claude Code en **modo no interactivo** sobre una tarea trivial en un repo de prueba.
2. Inspeccionar **todo** lo que devuelve: salida estándar, formato JSON si lo ofrece, archivos de sesión, logs.
3. Responder por escrito:
   - ¿Expone tokens de entrada y de salida?
   - ¿Distingue tokens cacheados de no cacheados? (importa: cambia el coste real)
   - ¿Es por turno o solo el total?
   - ¿Es estable entre ejecuciones?
4. Escribir `bench/ledger/` que parsee eso a un registro estructurado.
5. **Ejecutar la misma tarea 3 veces** y comprobar que las cifras son consistentes.

### Puerta de decisión

| Resultado | Acción |
|---|---|
| Contabilidad fiable | ✅ Continuar al Paso 2 |
| Parcial (p. ej. solo total) | ⚠️ Evaluar si basta para el criterio de kill; documentar la limitación |
| No hay contabilidad | 🔴 **Parar.** Ir a las alternativas |

### Alternativas si falla

1. **Llamar a la API directamente** en el runner, en vez del CLI. Se pierde fidelidad con el agente real, pero se gana control total de la medición.
2. **Proxy que intercepte** las llamadas HTTP del agente y contabilice. Más fiel, más frágil.

Si ninguna funciona, el proyecto no es medible en su forma actual y hay que replantear el alcance antes de invertir más.

### Entregable

`docs/FINDINGS-token-accounting.md` con los hallazgos. Este documento vale por sí solo: casi nadie ha escrito esto públicamente.

---

## Paso 2 — Hooks del agente

**Duración:** ~medio día · **Riesgo:** 🟡 afecta solo a la Fase 3

Resuelve la pregunta abierta #2 y determina si la memoria procedural (P5) es viable.

### Qué hacer

1. Documentar qué hooks expone Claude Code: cuándo disparan y con qué payload.
2. Responder:
   - ¿Podemos observar las llamadas a herramientas del agente? → captura de trayectorias
   - ¿Podemos saber si los tests pasaron? → verificación de P5
   - ¿Hay un hook de inicio de sesión? → aviso de frescura del grafo (**sin inyectar contexto**)
3. Prototipo mínimo: un hook que escriba una línea a un fichero. Confirmar que dispara.

### Puerta

| Resultado | Acción |
|---|---|
| Hooks con payload suficiente | ✅ Fase 3 viable tal como está diseñada |
| Hooks limitados | ⚠️ Fase 3 se rediseña; **Fases 1 y 2 no se ven afectadas** |
| Sin hooks útiles | ⚠️ La captura de trayectorias pasa a ser manual o se aplaza |

Este paso **no** bloquea el proyecto: el guardián y el recuperador sobreviven aunque salga mal.

### Entregable

`docs/FINDINGS-agent-hooks.md`

---

## Paso 3 — Corpus del banco

**Duración:** ~1 día · **Riesgo:** 🟡 calidad de la medición

### Criterios de selección de repositorios

Dos o tres proyectos OSS **en Python** que cumplan:

- Tamaño medio (ni script ni monorepo)
- Issues cerrados **enlazados a su commit de solución**
- Suite de tests que **discrimine**: falla antes del arreglo, pasa después
- Se instalan y ejecutan sus tests sin fricción

### Criterio por tarea — el que de verdad importa

> Una tarea solo entra al banco si sus tests **fallan en el commit padre** y **pasan en el commit de solución**.

Si no discrimina, no mide nada. Verificar esto **automáticamente**, no a ojo.

### Qué producir

- 20–30 tareas validadas
- Un `Dockerfile` por repositorio que fije el entorno
- `bench/tasks/*.json` con: repo, commit padre, commit solución, comando de test, tests que deben pasar

### Puerta

> Las 20–30 tareas se ejecutan en Docker y **todas discriminan**. Sin intervención manual.

---

## Paso 4 — Baseline A

**Duración:** ~1 día (más tiempo de cómputo) · **Riesgo:** 🟢 bajo

### Qué hacer

Ejecutar el agente **sin ArquiGraph** sobre las 20–30 tareas y registrar por tarea:

| Métrica | |
|---|---|
| Éxito | ¿pasan los tests objetivo? |
| Tokens de entrada / salida | R6 |
| Turnos hasta la solución | fuga #3 |
| Llamadas a herramientas | |
| Tiempo de reloj | |

**Tres ejecuciones por tarea.** Los agentes son no deterministas; un solo pase no es un baseline, es una anécdota. Registrar media y dispersión.

### Puerta

> Baseline publicado en el README con su dispersión, y reproducible por un tercero con un comando.

Esta es la primera credencial verificable del proyecto, y llega antes de haber construido la herramienta.

---

## Paso 5 — Parser y grafo (solo Python)

**Duración:** ~2–3 días · **Riesgo:** 🟢 bajo (trabajo conocido)

Ahora sí, con el baseline en la mano.

1. `core/parser/` — tree-sitter Python → nodos y aristas
2. `core/identity/` — `node_id`, `signature_hash`, `body_hash`, normalización
3. `core/graph/` — esquema SQLite, escritura, consultas
4. Reparseo incremental por archivo
5. `cli/` — `arqui build` y `arqui trace`

### Puerta

```bash
arqui build .
arqui trace --callers core.identity.node_id
```

> El grafo se construye sobre el propio ArquiGraph y `arqui trace` responde correctamente *"¿quién llama a X?"*, con ruta y evidencia citable.

Primer momento de dogfooding real.

---

## Puerta de salida de la Fase 0

Se pasa a Fase 1 solo cuando se cumplen **las tres**:

1. ✅ Contabilidad de tokens fiable y documentada (R6)
2. ✅ Baseline A publicado, con dispersión y reproducible
3. ✅ Grafo funcionando sobre el propio repositorio

---

## Resumen de esfuerzo

| Paso | Duración | Riesgo | Bloquea |
|---|---|---|---|
| 0 · Repo base | 1 h | 🟢 | — |
| 1 · **R6 tokens** | ½ día | 🔴 | **todo** |
| 2 · Hooks | ½ día | 🟡 | Fase 3 |
| 3 · Corpus | 1 día | 🟡 | calidad de medición |
| 4 · **Baseline A** | 1 día | 🟢 | Fase 1 |
| 5 · Parser y grafo | 2–3 días | 🟢 | Fase 1 |

**Total: aproximadamente una semana de trabajo efectivo**, y los dos pasos que pueden matar el proyecto se resuelven el primer día.

---

## Lo que NO se hace en Fase 0

Anotado explícitamente, porque es donde se va el tiempo:

- ❌ Parser de TypeScript → Fase 1.5, y solo si R1 sale bien (C7)
- ❌ Servidor MCP → Fase 1
- ❌ `Memory`, ranking, presupuesto → Fase 1
- ❌ DSL de invariantes → Fase 2
- ❌ Esquema Supabase → Fase 2
- ❌ Captura de trayectorias → Fase 3
- ❌ Optimizar el parser → no hay datos que digan que es lento

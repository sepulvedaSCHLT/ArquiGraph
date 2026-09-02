# Prompt — Corpus sintético del banco

> Especificación ejecutable para `bench/corpus/` y `bench/tasks/`.
> Decisión que lo gobierna: [ADR-010](../adr/ADR-010-corpus-sintetico.md).
>
> **Alcance: solo el corpus y las tareas.** Nada de runner, nada de ledger,
> ningún cambio en `arquigraph/`. Esto son datos, no código de producción.

---

## La regla que no se puede romper

> **Las tareas se escriben ANTES de que exista el recuperador.**

Si se escriben después, se estarían ajustando a lo que ArquiGraph resuelve bien, y ninguna cifra que salga de ahí valdría nada. Por eso este paso va ahora y se congela.

---

## Qué construir

### 1. El repositorio sintético — `bench/corpus/tienda/`

Un paquete Python de tamaño medio, **sin dependencias externas**, con estructura por capas:

```
bench/corpus/tienda/
├── tienda/
│   ├── api/            # entrada: validacion y traduccion de peticiones
│   ├── dominio/        # reglas de negocio: precios, descuentos, inventario
│   ├── infraestructura/# persistencia en memoria, reloj, generacion de ids
│   └── compartido/     # utilidades: dinero, fechas, errores
└── tests/
```

**Objetivo de tamaño:** entre 20 y 30 módulos, unas 1.000–1.500 líneas. Suficiente para que encontrar algo exija navegar; pequeño para que los tests corran en menos de un segundo.

**Requisitos:**

- Solo librería estándar. Ni una dependencia.
- Suite de tests completa que pasa en el estado sano.
- Cadenas de llamada de **tres o más saltos** entre capas — es lo que hace que la navegación importe.
- Nombres realistas, en español, coherentes con el resto del proyecto.
- Sin `random`, sin `datetime.now()` directo, sin nada no determinista: el reloj se inyecta desde `infraestructura`.

### 2. Las tareas — `bench/tasks/`

**Ocho tareas** para empezar. Cada una son dos archivos:

```
bench/tasks/T001.json
bench/tasks/T001.bug.patch
```

#### Formato de la tarea

```json
{
  "task_id": "T001",
  "kind": "synthetic",
  "corpus": "tienda",
  "bug_patch": "T001.bug.patch",
  "problem_statement": "Los pedidos con descuento por volumen estan cobrando el IVA sobre el precio sin descontar. Un pedido de 12 unidades a 10.00 con 15% de descuento deberia totalizar 123.42 y esta dando 145.20.",
  "test_command": "python -m pytest -q",
  "fail_to_pass": ["tests/test_precios.py::test_iva_sobre_precio_con_descuento"],
  "pass_to_pass": ["tests/test_precios.py::test_precio_base_sin_descuento"],
  "hint_files": []
}
```

#### La regla del enunciado

> **`problem_statement` describe el SÍNTOMA, nunca la ubicación.**

| Bien | Mal |
|---|---|
| "el IVA se calcula sobre el precio sin descontar" | "hay un bug en `dominio/precios.py`" |
| "un pedido de 12 unidades da 145.20 y deberia dar 123.42" | "la funcion `calcular_total` esta mal" |

Nombrar el archivo destruye el propósito del banco: si el agente ya sabe dónde ir, no hay navegación que medir. `hint_files` existe solo para documentar dónde está realmente el bug — **el runner nunca se lo pasa al agente**.

Los enunciados deben incluir **números concretos** (esperado y observado), como haría un issue real.

#### Variedad exigida

Las ocho tareas deben repartirse así:

| Cantidad | Tipo | Por qué |
|---|---|---|
| 3 | Bug en **una** función, alcanzable desde el síntoma en 1–2 saltos | Caso base |
| 3 | Bug cuyo síntoma aparece en una capa y la causa está en **otra** | Aquí es donde la navegación paga |
| 1 | Bug en código **compartido** que afecta a varios llamadores | Exige ver quién llama a qué |
| 1 | Bug de **contrato**: una función devuelve algo que su llamador interpreta mal | Exige seguir la cadena completa |

### 3. Verificador de discriminación — `bench/verificar_tareas.py`

Un script sin dependencias que, para cada tarea:

1. Copia el corpus a un directorio temporal
2. Aplica `bug_patch`
3. Ejecuta los tests → **`fail_to_pass` debe FALLAR y `pass_to_pass` debe PASAR**
4. Revierte el parche
5. Ejecuta los tests → **ambos deben PASAR**

Sale con código 0 solo si las ocho tareas discriminan. Imprime una línea por tarea con el resultado.

> Una tarea que no discrimina no mide nada. Esto se verifica con un script, nunca a ojo.

---

## Restricciones

1. **No tocar `arquigraph/`.** Esto son datos del banco.
2. **Sin dependencias externas**, ni en el corpus ni en el verificador. `pytest` ya está en el entorno de desarrollo.
3. **Sin Docker.**
4. **Nada no determinista** en el corpus: sin `random`, sin reloj real, sin E/S de red o disco.
5. Los parches deben aplicarse con `git apply` o `patch -p1` estándar.
6. **No escribir el enunciado mirando la solución.** Primero se decide el síntoma observable, después se inyecta el bug que lo produce.

---

## Criterios de aceptación

- [ ] `cd bench/corpus/tienda && python -m pytest -q` pasa en menos de 2 segundos
- [ ] El corpus tiene entre 20 y 30 módulos y no importa nada fuera de la librería estándar
- [ ] Existe al menos una cadena de llamadas de 3 saltos entre capas distintas
- [ ] Hay 8 tareas con su parche, repartidas según la tabla de variedad
- [ ] **Ningún `problem_statement` menciona un nombre de archivo, módulo o función**
- [ ] Todos los enunciados incluyen valor esperado y valor observado
- [ ] `python bench/verificar_tareas.py` sale con código 0 y reporta las 8 discriminando
- [ ] Los tests de ArquiGraph siguen pasando: `uv run pytest -q` → 152
- [ ] `uv run ruff check .` y `uv run ruff format --check .` limpios

---

## Verificación

```bash
cd bench/corpus/tienda && python -m pytest -q && cd -
python bench/verificar_tareas.py
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

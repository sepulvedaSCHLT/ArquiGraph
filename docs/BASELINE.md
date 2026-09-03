# Baseline — Modo A (sin ArquiGraph)

- **Fecha:** 2026-09-02
- **Ejecuciones:** 60 (12 tareas × 5 repeticiones), 0 descartadas
- **Coste total:** $7.8890
- **Entorno:** `claude-sonnet-5` · Claude Code 2.1.258 · 4 plugins · 0 servidores MCP · 3 herramientas
- **Corpus:** [`bench/corpus/tienda`](../bench/corpus/tienda) — 29 módulos, 1.442 líneas, 115 tests
- **Reproducible:** `uv run arqui bench run --repeticiones 5`

---

## 1. Resultados

```
tarea    validas descart   exito   $ medio   $ desv  turnos
-----------------------------------------------------------
T001           5       0   100%    0.1337   0.0270    12.2
T002           5       0   100%    0.0995   0.0165    11.2
T003           5       0   100%    0.0981   0.0189    10.2
T004           5       0   100%    0.1263   0.0362    13.6
T005           5       0   100%    0.0960   0.0338    12.4
T006           5       0   100%    0.1139   0.0400    14.0
T007           5       0   100%    0.1053   0.0235    11.2
T008           5       0   100%    0.1446   0.0230    15.4
T009           5       0   100%    0.1207   0.0171    14.0
T010           5       0   100%    0.1833   0.0193    16.8
T011           5       0   100%    0.2612   0.0744    21.0
T012           5       0   100%    0.0951   0.0273    12.8
-----------------------------------------------------------
TOTAL         60       0   100%    0.1315   0.0570    13.7
```

## 2. El hallazgo principal

> **El coste de resolver un bug depende de lo lejos que esté la causa del síntoma, no de la dificultad del arreglo.**

Los doce arreglos son de una o dos líneas. El coste varía **2,7 veces** entre el más barato y el más caro:

| | $ medio | Turnos |
|---|---|---|
| T003 (causa a 1 salto) | $0.0981 | 10,2 |
| T011 (causa a 6 saltos, sin test propio) | **$0.2612** | **21,0** |

Todo lo que separa a esas dos tareas es **cuánto hay que navegar para encontrar el sitio**. Es la tesis del proyecto, medida.

## 3. Por grupo

| Grupo | $ medio | Turnos |
|---|---|---|
| **T001–T008** (la suite delata la causa) | $0.1147 | 12,5 |
| **T009–T012** (la suite no la delata) | $0.1651 | 16,2 |
| **Diferencia** | **+44%** | **+29%** |

El criterio del oráculo —*una tarea solo mide navegación si el parche no rompe ningún test cercano a la causa*— se confirma en agregado.

## 4. Pero el grupo difícil no es homogéneo

| Tarea | $ medio | vs. media general | ¿Discrimina? |
|---|---|---|---|
| **T011** | $0.2612 | **+99%** | ✅ Claramente |
| **T010** | $0.1833 | **+39%** | ✅ Sí |
| T009 | $0.1207 | −8% | ⚠️ Apenas |
| **T012** | $0.0951 | **−28%** | ❌ **No** |

### T012 falla, y la razón afina el criterio

T012 rompe la herencia de una excepción, y la API deja de atraparla. El síntoma es un **error sin controlar**, es decir, **un traceback** — y un traceback nombra el archivo y la línea.

> El oráculo no es solo la suite de tests. **Cualquier salida que nombre un archivo lo es.**

Criterio corregido para futuras tareas:

> Una tarea mide navegación si **ni los tests ni el traceback ni ningún mensaje de error** delatan la causa.

## 5. Limitaciones, sin adornos

### El techo de éxito

**60 de 60 resueltas.** Con la línea base al 100%, ArquiGraph **no puede mejorar la tasa de éxito** sobre este corpus. Solo queda el coste como señal, y el criterio de kill de R1 se evalúa sobre una sola dimensión.

### La varianza

Coeficiente de variación por tarea entre el 11% y el 35%; en agregado, 43%. Con 5 repeticiones, el error estándar de la media por tarea ronda el 10–15%.

**Consecuencia práctica:** una mejora del 10% en el coste agregado **no sería distinguible del ruido**. Para que la comparación tenga potencia hay que analizarla **emparejada por tarea**, no como dos conjuntos independientes.

### Solo dos tareas ejercitan lo que ArquiGraph hace

De doce, **T010 y T011** son las que de verdad exigen navegar. Las otras diez se resuelven leyendo lo que el runner o los tests ya señalan.

Eso significa que el efecto esperable sobre la media de las doce es **pequeño por construcción**, aunque sea grande donde importa. El informe de la Fase 1 debe reportar los dos grupos por separado.

### El corpus es sintético y pequeño

29 módulos. Un código real es dos órdenes de magnitud mayor, y ahí la distancia entre síntoma y causa —que es lo que este baseline demuestra que gobierna el coste— es mucho mayor. **Esto acota la medición hacia abajo**: el efecto en un repositorio real debería ser mayor, no menor. Pero eso es una expectativa, no un dato.

## 6. Qué se puede afirmar

✅ **Con estos datos:**
- El coste de una tarea de depuración escala con la distancia entre el síntoma y la causa: **2,7×** entre los extremos de este corpus.
- Cuando la suite de tests no delata la causa, el coste sube un **44%** y los turnos un **29%**.
- Un agente competente resuelve bugs de una línea en un corpus de 29 módulos por **$0.13 y 13,7 turnos** de media.

❌ **Con estos datos, NO:**
- Nada sobre si ArquiGraph ayuda. Eso es la Fase 1.
- Nada sobre repositorios grandes o reales.
- Nada sobre tasa de éxito: aquí está saturada.

## 7. Datos crudos

Los 60 registros están en `bench/runs/`, cada uno con el `init` completo del agente, la trayectoria de llamadas a herramientas y el desglose de tokens. El corpus, las tareas y el runner están en el repositorio: cualquiera puede reproducir esta tabla con un comando.

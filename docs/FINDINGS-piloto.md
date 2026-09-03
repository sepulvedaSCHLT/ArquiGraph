# Hallazgos — Piloto del banco (modo A)

- **Fecha:** 2026-09-02
- **Alcance:** T001 y T007, 2 repeticiones cada una, modo A
- **Coste:** $0.4300
- **Entorno:** `claude-sonnet-5` · 4 plugins · 0 servidores MCP · 3 herramientas

---

## 1. Resultados

```
tarea    validas descart   exito   $ medio   $ desv  turnos
-----------------------------------------------------------
T001           2       0   100%    0.1353   0.0192    11.0
T007           2       0   100%    0.0797   0.0009     9.0
-----------------------------------------------------------
TOTAL          4       0   100%    0.1075   0.0310    10.0
```

## 2. Lo que se valida

| | |
|---|---|
| **La tubería completa** | Copia, parche, comprobación previa, agente, parseo, aislamiento y evaluación. Cero fallos. |
| **El aislamiento, en condiciones reales** | 4/4 válidas, 0 servidores MCP, 3 herramientas. `--strict-mcp-config` cumple. |
| **El presupuesto** | $0.108 por ejecución, no los $1–3 que temíamos. El banco completo cabe holgadamente. |

## 3. El problema: efecto techo

> **El agente resolvió las cuatro ejecuciones. 100% de éxito en el modo A.**

Con la línea base al 100%, **ArquiGraph no puede mejorar la tasa de éxito**. Se pierde una de las dos señales del criterio de kill de R1, y queda solo el coste.

No invalida la medición —el coste era la métrica primaria desde [FINDINGS-token-accounting §4](./FINDINGS-token-accounting.md)— pero la deja coja.

### Y la varianza puede tapar el efecto

```
T001 r1  $0.1162
T001 r2  $0.1545     ← 33% de diferencia en la MISMA tarea
```

Un coeficiente de variación del 14% en T001 con solo dos muestras. **Si ArquiGraph mejorase el coste un 15%, tres repeticiones no bastarían para distinguirlo del ruido.**

## 4. La predicción que fallé, y por qué

Predije que **T007 sería el mejor discriminador**: bug en código compartido, tres síntomas en tres dominios, resoluble solo preguntándose *"¿quién calcula porcentajes aquí?"*.

Salió **la más barata y la más rápida**: $0.0797 frente a $0.1353, y 9 turnos frente a 11. Además con una varianza mínima (1%), señal de que el camino a la solución era evidente.

La causa está en el enunciado que yo mismo aprobé:

> *"Pasa en cualquier calculo con porcentaje, y **siempre en la misma direccion**."*

Esa frase **es el mapa**. Le dice al agente que hay una única causa común en código compartido. Al diseñar el síntoma para que "fuera de código compartido", le entregué la conclusión.

### La lección, generalizable

> Un síntoma que aparece en tres sitios con una causa común evidente **estrecha** la búsqueda, no la amplía.

Una tarea difícil de navegar necesita lo contrario: un síntoma **local y concreto** cuya causa esté lejos, sin ninguna pista de que lo esté.

## 5. Qué hacer

### No tocar las ocho tareas existentes

Endurecerlas después de ver que A las resuelve es ajustar el examen tras conocer la nota. [ADR-010](./adr/ADR-010-corpus-sintetico.md) lo prohíbe y la razón sigue en pie.

### Añadir tareas difíciles, y congelarlas ya

Añadir cuatro tareas diseñadas con la lección de §4, **antes de que exista el recuperador**. Eso es legítimo: no se pueden ajustar a lo que ArquiGraph resuelve bien porque ArquiGraph todavía no resuelve nada.

Criterio para las nuevas: **el enunciado describe un síntoma local y no sugiere dónde está la causa.**

### Subir las repeticiones

De 3 a 5. Con 12 tareas: 60 ejecuciones para el baseline completo, unos **$6.50**.

### Declarar el techo en el README

El corpus de 29 módulos resulta demasiado fácil para el agente. Un código real es dos órdenes de magnitud mayor y ahí la navegación pesa mucho más. **Esto acota la medición, no la invalida** — y hay que decirlo antes de que lo diga un revisor.

---

## 6. Actualización de riesgos

| | |
|---|---|
| **R7** — el banco cuesta dinero | ✅ **Resuelto.** $0.108 por ejecución; baseline completo bajo $7. |
| **R1** — ArquiGraph podría degradar | ⚠️ **Medible solo en coste.** El éxito llega al techo en A. |
| **R8** *(nuevo)* — el corpus no discrimina lo suficiente | La varianza entre ejecuciones puede superar el efecto a detectar. Mitigación: más repeticiones y tareas más difíciles, congeladas antes del recuperador. |

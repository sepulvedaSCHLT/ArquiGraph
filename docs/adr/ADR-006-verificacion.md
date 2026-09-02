# ADR-006 — Verificación obligatoria para persistir procedimientos

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [RESEARCH.md §6, P5, R3](../RESEARCH.md) · [ARCHITECTURE.md §5](../ARCHITECTURE.md)

## Contexto

La memoria procedural es el diferenciador de ArquiGraph y la única capa con evidencia causal de ahorro de tokens: Memp reporta −9 pasos y −685 tokens por tarea; las skills evolucionadas, hasta −62% de tokens totales (§6.2).

Pero hay un modo de falla evidente. Una sesión de agente contiene mayoritariamente **exploración fallida**: intentos que no compilaron, hipótesis descartadas, caminos abandonados. Si destilamos la trayectoria completa, la memoria procedural se convierte en un registro de errores servido con autoridad — envenenando el recurso que debía ahorrar tokens.

## Decisión

### Regla de admisión

> Una trayectoria solo se persiste como `Procedure` si terminó con **evidencia objetiva**: tests en verde **o** commit aplicado.

Sin evidencia, se descarta. No se guarda "por si acaso", no se guarda con confianza baja, no se guarda marcada como dudosa. Se descarta.

```python
Verification {
    tests_passed: [str]     # identificadores de tests en verde
    commit_sha:   str       # el cambio se aplicó de verdad
    captured_at:  datetime
}
```

`verification` es un campo **obligatorio** de `Procedure`. Un procedimiento sin verificación es inválido a nivel de esquema, no solo por convención.

### La destilación es asíncrona y fuera de la ruta caliente

Es el único punto del sistema donde interviene un LLM. Ocurre **después** de la sesión, nunca mientras el usuario trabaja. El coste de destilación no lo paga el desarrollador en su tiempo de espera ni en su presupuesto de sesión.

### Fusión, no acumulación

Si ya existe un `Procedure` con el mismo `intent`, la nueva trayectoria **se fusiona** con él y sube su confianza. No se crea un duplicado.

Acumular variantes del mismo procedimiento reproduce el problema del contexto inflado dentro de nuestra propia base de datos.

### Caducidad

Un `Procedure` cuyos `touched_nodes` cambian de `body_hash` pasa a `suspect` (ADR-003) y deja de servirse. Un procedimiento paso a paso sobre código que ya cambió es activamente dañino.

## Consecuencias

**Positivas**
- La memoria procedural contiene solo lo que demostrablemente funcionó.
- La destilación no cuesta tokens al usuario en tiempo de trabajo.
- La fusión mantiene la base de datos pequeña y de alta señal.

**Negativas**
- **Descartamos información potencialmente útil**: saber qué *no* funciona tiene valor. Aceptado por ahora — el riesgo de envenenar la memoria es mayor que el beneficio, y no tenemos forma barata de distinguir "no funciona" de "no funcionó esta vez".
- El arranque es lento: hacen falta sesiones verificadas antes de que la capa aporte algo. La curva de valor es creciente, no inmediata.
- Requiere que el proyecto tenga tests. En repos sin suite, el disparador queda reducido a "commit aplicado", que es una señal más débil.

## A validar (R3)

> ¿La destilación cuesta más de lo que ahorra?

Contabilizar en el banco:
- `discovery_cost` — tokens que costó descubrir el procedimiento la primera vez
- coste de destilación por procedimiento
- ahorro acumulado por reuso (`uses × ahorro_medio`)

**Umbral de rentabilidad:** un procedimiento debe reutilizarse un mínimo de veces para amortizar su destilación. Si la tasa de reuso medida queda por debajo de ese umbral, la capa procedural no es rentable en su forma actual y hay que replantear el nivel de abstracción (procedimientos más generales, que apliquen a más tareas).

## Revisión futura

Si aparece una forma barata y fiable de distinguir "fallo informativo" de "ruido", reconsiderar el descarte de trayectorias fallidas — la literatura de ReMe (§6.2) apunta en esa dirección con su *análisis de fallos*.

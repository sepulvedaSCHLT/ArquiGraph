# ADR-010 — Corpus sintético para el banco de Fase 0

- **Estado:** Aceptada
- **Fecha:** 2026-09-02
- **Matiza a:** [ADR-007](./ADR-007-licencia.md) (que preveía repos OSS públicos)
- **Base:** [PHASE-0.md §3](../PHASE-0.md) · [RESEARCH.md R7](../RESEARCH.md)

## Contexto

El banco A/B necesita tareas con solución conocida y tests que discriminen. Se evaluaron cuatro opciones.

### SWE-bench Lite — descartada para Fase 0

Es el candidato obvio: 300 tareas Python curadas, MIT, con `FAIL_TO_PASS` validado e imágenes Docker preconstruidas. Tres razones para no usarlo **ahora**:

1. **Recursos.** Cada imagen pesa varios GB y el entorno recomendado son 8 núcleos. La máquina de desarrollo tiene 4 y está ocupada con otros dos proyectos activos. El banco competiría por RAM y CPU con el trabajo diario.

2. **Coste de depuración.** El runner va a tener errores. Cada iteración contra SWE-bench cuesta minutos de descarga y dólares de API. Contra un corpus local cuesta segundos.

3. **Puede no medir lo que ArquiGraph hace.** Los issues de SWE-bench suelen nombrar el archivo o la función, y sus repositorios —django, sympy, scikit-learn— son de los mejor conocidos por los modelos. Si el agente ya sabe dónde mirar, la navegación no aporta nada y B ≈ A. Un resultado plano ahí significaría *"el banco no ejercita esto"*, no *"la herramienta no sirve"*.

## Decisión

**Un corpus sintético propio para Fase 0**, sin Docker.

- Un repositorio Python de tamaño medio (~25 módulos, varias capas) escrito para el banco.
- Cada tarea es un **parche que inyecta un bug**, más el test que lo detecta.
- El enunciado describe **el síntoma, nunca la ubicación**. Eso es lo que obliga a navegar.
- Sin dependencias externas: los tests corren con `pytest` en menos de un segundo.

SWE-bench entra **después**, cuando la tubería funcione y haya una cifra que publicar, si los recursos lo permiten.

## Consecuencias

**Positivas**
- **Coste marginal casi nulo.** Sin Docker, sin descargas, sin competir por recursos.
- **Cero contaminación.** El código no existía antes; no puede estar en datos de entrenamiento.
- **Control sobre lo que se mide.** Podemos escribir tareas que exijan navegar, que es la capacidad que ArquiGraph aporta.
- **Queda como test de regresión del banco**, aunque después se use otro corpus.
- La verificación de discriminación es trivial y automática: aplicar el parche debe hacer fallar `fail_to_pass`; revertirlo debe hacerlo pasar.

**Negativas — asumidas**
- **Es un benchmark de juguete, y hay que decirlo.** La crítica legítima es *"lo diseñaste tú para que ganara"*. No se puede refutar del todo; solo mitigar.
- Las cifras **no son comparables** con la literatura ni con otros sistemas.
- Un corpus escrito por nosotros puede tener sesgos que no vemos.

**Mitigaciones**
1. El corpus y sus tareas se publican íntegros en el repositorio. Cualquiera puede leer si están sesgados.
2. El README dirá **explícitamente** que la cifra es sobre corpus sintético, sin adornos.
3. Las tareas se escriben **antes** de tener el recuperador funcionando, para no ajustarlas a lo que el recuperador resuelve bien.
4. SWE-bench sigue en la hoja de ruta como validación externa.

## Sobre el punto 3

Es la mitigación que de verdad importa. Escribir las tareas después de ver qué resuelve bien ArquiGraph sería ajustar el examen al alumno, y ninguna cifra que salga de ahí valdría nada.

Las tareas se congelan y se commitean **antes** de que exista `arqui_recall`.

## Revisión

Reevaluar cuando se cumplan las dos condiciones: la tubería del banco funciona de extremo a extremo, y hay margen de máquina. Entonces SWE-bench Lite sobre un subconjunto pequeño, como validación externa de lo que el sintético haya indicado.

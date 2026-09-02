# ADR-007 — Licencia Apache 2.0 y banco reproducible por terceros

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [ARCHITECTURE.md §12, §16](../ARCHITECTURE.md) · [ADR-001](./ADR-001-grafo-propio.md)

> **Nota:** esta ADR recoge información factual sobre licencias, no asesoría legal. Antes de montar un esquema de licencia dual con ingresos reales conviene revisión profesional.

## Contexto

ArquiGraph tiene dos objetivos declarados y **están en tensión**:

1. **Portafolio profesional.** Que ingenieros y reclutadores lo lean, lo prueben y lo usen. La moneda es la adopción.
2. **Posible beneficio si lo adopta una organización.** Requiere fricción legal que empuje a comprar.

La fricción que genera ingreso es exactamente la que destruye la adopción. Hay que elegir.

Un dato que enmarca la decisión: el ingreso realista de un proyecto OSS nuevo, de un autor sin marca previa, es prácticamente cero con cualquier licencia. El valor esperado de ArquiGraph está casi por completo en el objetivo 1.

## Decisión

**Apache 2.0.**

Y como consecuencia directa del carácter público del proyecto: **los resultados del banco de medición deben ser reproducibles por un tercero**.

- El corpus del banco se toma de **repositorios OSS públicos**, no de código privado.
- El entorno se fija con Docker.
- El harness se publica en el repo, y CI lo ejecuta.

## Justificación

| Factor | Apache 2.0 |
|---|---|
| Fricción legal en empresas | Ninguna. Un ingeniero puede clonarlo y probarlo sin pasar por su departamento legal. |
| Patentes | Concesión explícita. Señal de proyecto serio, no ingenuo. |
| Ecosistema | Es la licencia del entorno de herramientas para agentes donde ArquiGraph quiere encajar. |
| Objetivo de portafolio | Máxima probabilidad de que quien te evalúa **pueda** probarlo. |

El punto decisivo: en bastantes organizaciones existe una política que impide siquiera clonar un repositorio AGPL en una máquina de trabajo. Si quien evalúa tu candidatura quiere probar tu herramienta y su política se lo impide, se pierde justo el punto que la licencia debía ganar.

### Sobre la reproducibilidad

Un README que afirma *"reduje el consumo de tokens un X% — aquí está el harness, ejecútalo"* es una credencial verificable. Uno que afirma *"funciona muy bien en mi repositorio privado"* no lo es.

La reproducibilidad no es un detalle de rigor académico: es **la parte del proyecto que hace la afirmación creíble**, y por tanto la que cumple el objetivo 1.

## Consecuencias

**Positivas**
- Cero fricción de adopción.
- Compatible con cualquier uso corporativo, lo que maximiza la probabilidad de que alguien relevante lo pruebe.
- El banco público refuerza la credibilidad de las cifras.

**Negativas — asumidas**
- **Renunciamos a la vía de ingreso por licencia comercial.** Una organización puede usar ArquiGraph, modificarlo y ofrecerlo como servicio sin devolver nada ni pagar.
- **La decisión es prácticamente irreversible hacia atrás.** Se puede relicenciar el futuro, pero las versiones ya publicadas siguen siendo Apache 2.0 para siempre y cualquiera puede mantener un fork desde ahí.

**Habilitada por ADR-001**
La decisión de no usar código de Graphify ni de Engram, y construir sobre `tree-sitter` (MIT), deja el proyecto **libre de copyleft heredado**. Podemos elegir cualquier licencia. Si hubiéramos construido el "pegamento" entre ambos repositorios, la licencia la decidirían ellos.

## Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| **MIT** | Casi equivalente, pero sin concesión explícita de patentes. Apache 2.0 domina para el mismo coste. |
| **AGPL-3.0** | Preserva la vía comercial y **es lo que habría que elegir si el objetivo 2 fuera prioritario**. Coste: adopción medible menor, y bloqueo en empresas con política anti-AGPL — la audiencia exacta del objetivo 1. |
| **AGPL + licencia comercial (dual)** | Es el modelo de Grafana, Mattermost, Bitwarden y Nextcloud. Exige poseer el 100% del copyright, lo que obliga a un CLA para cada contribución. Sobrecarga de gobernanza desproporcionada para un ingreso improbable. |
| **BSL / FSL** | Fuente disponible con restricción temporal. **No son licencias aprobadas por la OSI**: parte de la comunidad las percibe como no-abiertas, lo que resta credibilidad ante la audiencia que el proyecto busca impresionar. |

## Nota sobre contribuciones

Si en el futuro se quisiera relicenciar o dual-licenciar, hay que **poseer todo el copyright**. En cuanto se acepte un PR de un tercero sin CLA firmado, esa puerta se cierra.

Dado que esta ADR renuncia explícitamente a la vía comercial, **no se exigirá CLA**. Se adoptará **DCO** (`Signed-off-by`), que es más ligero, no transfiere derechos y basta para la trazabilidad de autoría.

## Revisión

Reevaluar solo si ArquiGraph alcanza adopción sostenida y aparece demanda real de soporte comercial. En ese escenario, el camino es un **servicio** sobre la herramienta abierta (hosting, soporte, integraciones a medida), no un cambio de licencia — porque el cambio de licencia ya no podría recuperar lo publicado.

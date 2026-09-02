# ADR-001 — Grafo propio determinista, sin dependencia de Graphify ni Engram

- **Estado:** Aceptada
- **Fecha:** 2026-09-01
- **Base:** [RESEARCH.md §5.1, §7](../RESEARCH.md)

## Contexto

Graphify resuelve la extracción AST con tree-sitter para 22 lenguajes, a coste cero de tokens y de forma determinista. Los proyectos "Engram" resuelven la persistencia episódica. La tentación evidente era construir ArquiGraph como pegamento entre ambos.

Dos problemas lo desaconsejan:

1. **Legales y de gobernanza.** Son dos repositorios de terceros, con licencias, ciclos de release y decisiones de diseño propias. Acoplarnos a sus formatos de salida nos deja sin control sobre el elemento central de nuestro sistema.
2. **Técnicos.** Nuestro diferenciador (§7) exige que el grafo exponga `signature_hash` y `body_hash` por nodo, y una identidad estable ante refactors (ADR-003). Ningún grafo de terceros está diseñado para servir de ancla de invalidación de memoria; adaptarlo por fuera es frágil.

## Decisión

**Construimos nuestro propio extractor AST y nuestro propio modelo de grafo**, usando `tree-sitter` (MIT) directamente como librería, sin dependencia de código de Graphify ni de Engram.

El grafo es **100% determinista**: cero LLM, cero embeddings. Lo que no se puede extraer del AST se marca `AMBIGUOUS` y no se afirma.

## Consecuencias

**Positivas**
- Control total del esquema de nodos, en particular de la identidad y de los hashes de invalidación, que son la base de P3.
- Sin ambigüedad de licencias ni de atribución. **Esto es lo que habilita ADR-007** (elegir libremente Apache 2.0).

> **Consecuencia operativa:** ni `graphify-out/` ni `engram/` pertenecen al árbol del repositorio. Se consultan como referencia desde fuera (`~/ref/`). Tener el código fuente o los activos de marca de un tercero dentro de un repositorio Apache 2.0 mezcla licencias y, en un proyecto de portafolio, hace imposible distinguir qué escribió el autor. Ver [PHASE-0.md § Limpieza previa](../PHASE-0.md).
- Sin acoplamiento al ciclo de release de terceros.
- Podemos garantizar la propiedad "cero alucinación en la capa semántica", porque controlamos toda la ruta.

**Negativas — asumidas conscientemente**
- Reimplementamos trabajo ya resuelto. Es un anti-objetivo declarado en RESEARCH.md §9 y lo violamos **a propósito**, por C1.
- Empezaremos muy por detrás en cobertura de lenguajes.

**Mitigación del coste**
- Fase 0 cubre **un solo lenguaje** (Python), suficiente para hacer dogfooding sobre este mismo repositorio y para correr el banco de medición.
- La cobertura de lenguajes se amplía en Fase 4, y solo si R1 salió bien. No invertimos en amplitud antes de validar la tesis.

## Alternativas descartadas

| Alternativa | Motivo del descarte |
|---|---|
| Consumir `graphify-out` | Sin `signature_hash` ni identidad estable; dependemos de su formato; cuestiones de licencia y atribución |
| Capa de adaptación sobre varios backends | Abstracción prematura: dos implementaciones de coste antes de tener una que funcione |
| LSP / Language Server como fuente | Requiere un servidor vivo por lenguaje; pesado, con estado, y difícil de correr en hooks y CI |

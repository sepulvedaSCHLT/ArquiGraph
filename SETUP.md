# Puesta en marcha — comandos del Paso 0

Ejecutar en orden desde `/mnt/DATOS/GITHUB_REPOS/ArquiGraph`.

## 1. Licencia (texto canónico, no parafraseado)

```bash
curl -sSL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
head -3 LICENSE
```

Después, añadir al final del archivo el aviso de copyright:

```bash
cat >> LICENSE <<'EOF'

   Copyright 2026 Yordano Schultz

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
EOF
```

## 2. Árbol de paquetes

```bash
mkdir -p arquigraph/{core/{parser,identity,graph},memory/{episodic,procedural,ranking,budget},guardian/{dsl,checker},bench/{ledger,runner},mcp,hooks,cli}
mkdir -p tests bench/{tasks,config,report}

# __init__.py en cada paquete
find arquigraph -type d -exec touch {}/__init__.py \;
```

## 3. Dependencias

```bash
uv sync --all-extras --dev
```

Si `uv sync` falla porque falta el paquete, revisar que `arquigraph/__init__.py` exista.

## 4. Primer test (que el CI tenga algo que correr)

```bash
cat > tests/test_smoke.py <<'EOF'
"""Prueba minima: el paquete importa y el CI tiene algo que ejecutar."""

import arquigraph


def test_paquete_importa() -> None:
    assert arquigraph is not None
EOF

uv run pytest
uv run ruff check .
```

## 5. Repositorio git

```bash
git init -b main
git add -A
git status --short
```

Revisar que **no** aparezcan `ArquiGraph-avance-de-ciclos-bugError/`, `.arquigraph/` ni `.venv/`. Si aparecen, corregir `.gitignore` antes de commitear.

```bash
git commit -s -m "chore: andamiaje inicial del proyecto

Estructura de paquetes, pyproject con uv/ruff/pytest, CI en GitHub
Actions, licencia Apache 2.0 y documentacion de arquitectura.

Fase 0a completada: R6 (contabilidad de tokens) y captura de
trayectorias verificadas. Ver docs/FINDINGS-*.md"
```

## 6. GitHub

```bash
# Crear el repo vacio en github.com, luego:
git remote add origin git@github.com:USUARIO/ArquiGraph.git
git push -u origin main
```

Actualizar la URL en `pyproject.toml` (`[project.urls]`) y en `SETUP.md`.

## 7. Verificación del Paso 0

- [ ] `uv run pytest` pasa en local
- [ ] `uv run ruff check .` sin errores
- [ ] CI en verde en GitHub
- [ ] `git status` limpio, sin material ajeno ni notas personales
- [ ] `LICENSE` con el texto canónico de Apache 2.0

Con eso, el Paso 0 está cerrado y se puede empezar por el paso 1 de
[`docs/SPEC-FASE-0.md` §7](docs/SPEC-FASE-0.md#7-orden-de-implementación):
`core/identity/` con sus tests.

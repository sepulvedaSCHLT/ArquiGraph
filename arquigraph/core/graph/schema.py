"""Esquema SQLite del grafo semantico.

Implementa la seccion 1 de docs/SPEC-FASE-0.md.

Decisiones que se ven aqui y estan justificadas en ADR-002:

- **SQLite y nada mas.** Las consultas del recuperador son de uno o dos
  saltos; no necesitamos un motor de grafos. Cero servicios que levantar
  es lo que hace que la herramienta se pueda probar en treinta segundos.
- **La base es desechable.** Vive en ``.arquigraph/``, se ignora en git y
  se reconstruye con ``arqui build --full``. Nunca es la fuente de verdad:
  el codigo lo es.
- **Sin clave foranea en ``edges.dst``.** Una arista puede apuntar a un
  simbolo externo (una libreria) que no tiene nodo local. Esas aristas se
  marcan ``INFERRED`` o ``AMBIGUOUS``, nunca ``EXTRACTED``.

Las tablas de memoria, procedimientos e invariantes llegan en sus fases.
Un esquema escrito antes de tener el caso de uso se escribe mal.
"""

from __future__ import annotations

import platform
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "SCHEMA_VERSION",
    "GraphSchemaError",
    "connect",
    "get_meta",
    "initialize",
    "open_graph",
    "schema_version",
    "set_meta",
]

SCHEMA_VERSION = 1

# El volcado del AST de CPython puede variar entre versiones mayores, y
# body_hash depende de el. Registrar la version permite detectar que el
# grafo hay que reconstruirlo en vez de invalidar memoria por error.
PARSER_VERSION = f"cpython-{platform.python_version()}"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    path         TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    parsed_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    node_id        TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    path           TEXT NOT NULL,
    signature_hash TEXT NOT NULL,
    body_hash      TEXT NOT NULL,
    start_line     INTEGER NOT NULL,
    end_line       INTEGER NOT NULL,
    layer          TEXT
);

CREATE INDEX IF NOT EXISTS idx_nodes_path      ON nodes(path);
CREATE INDEX IF NOT EXISTS idx_nodes_qname     ON nodes(qualified_name);
CREATE INDEX IF NOT EXISTS idx_nodes_body_hash ON nodes(body_hash);

CREATE TABLE IF NOT EXISTS edges (
    src           TEXT NOT NULL,
    dst           TEXT NOT NULL,
    kind          TEXT NOT NULL,
    evidence_path TEXT NOT NULL,
    evidence_line INTEGER NOT NULL,
    confidence    REAL NOT NULL DEFAULT 1.0,
    resolution    TEXT NOT NULL
        CHECK (resolution IN ('EXTRACTED', 'INFERRED', 'AMBIGUOUS')),
    PRIMARY KEY (src, dst, kind, evidence_path, evidence_line)
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src, kind);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst, kind);
"""


class GraphSchemaError(RuntimeError):
    """La base existe pero no es compatible con esta version del codigo."""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Abre una conexion con los PRAGMA del proyecto.

    ``:memory:`` se acepta tal cual, para tests.
    """
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # WAL permite leer mientras se reparsea; en :memory: SQLite lo ignora.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    """Crea las tablas si faltan y sella los metadatos. Es idempotente."""
    conn.executescript(_SCHEMA)
    existing = get_meta(conn, "schema_version")
    if existing is None:
        set_meta(conn, "schema_version", str(SCHEMA_VERSION))
        set_meta(conn, "parser_version", PARSER_VERSION)
        set_meta(conn, "built_at", datetime.now(UTC).isoformat())
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM graph_meta WHERE key = ?", (key,)).fetchone()
    return None if row is None else str(row["value"])


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO graph_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def schema_version(conn: sqlite3.Connection) -> int | None:
    raw = get_meta(conn, "schema_version")
    return None if raw is None else int(raw)


def open_graph(db_path: Path | str) -> sqlite3.Connection:
    """Abre el grafo, creandolo si no existe, y valida la version.

    Raises:
        GraphSchemaError: si la base la escribio otra version del esquema.
            No migramos en Fase 0: el grafo es desechable y reconstruirlo
            cuesta segundos, asi que fallar claro es mejor que arrastrar
            una migracion que nadie va a mantener.
    """
    conn = connect(db_path)
    initialize(conn)

    found = schema_version(conn)
    if found != SCHEMA_VERSION:
        conn.close()
        raise GraphSchemaError(
            f"El grafo en {db_path} usa el esquema v{found}, "
            f"pero este codigo espera v{SCHEMA_VERSION}. "
            f"Ejecuta 'arqui build --full' para reconstruirlo."
        )
    return conn

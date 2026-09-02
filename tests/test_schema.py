"""Contrato del esquema SQLite (SPEC-FASE-0 seccion 1, ADR-002)."""

import sqlite3
from pathlib import Path

import pytest

from arquigraph.core.graph import (
    PARSER_VERSION,
    SCHEMA_VERSION,
    GraphSchemaError,
    connect,
    get_meta,
    initialize,
    open_graph,
    schema_version,
    set_meta,
)

TABLAS_ESPERADAS = {"graph_meta", "files", "nodes", "edges"}

INDICES_ESPERADOS = {
    "idx_nodes_path",
    "idx_nodes_qname",
    "idx_nodes_body_hash",
    "idx_edges_src",
    "idx_edges_dst",
}


@pytest.fixture
def conn() -> sqlite3.Connection:
    conexion = connect(":memory:")
    initialize(conexion)
    yield conexion
    conexion.close()


def _nombres(conn: sqlite3.Connection, tipo: str) -> set[str]:
    filas = conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (tipo,)).fetchall()
    return {fila["name"] for fila in filas}


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------


def test_crea_todas_las_tablas(conn: sqlite3.Connection) -> None:
    assert TABLAS_ESPERADAS.issubset(_nombres(conn, "table"))


def test_crea_los_indices_de_navegacion(conn: sqlite3.Connection) -> None:
    """idx_edges_dst es el que responde '¿quien llama a X?' sin escanear."""
    assert INDICES_ESPERADOS.issubset(_nombres(conn, "index"))


def test_initialize_es_idempotente(conn: sqlite3.Connection) -> None:
    """Volver a abrir un grafo existente no debe fallar ni duplicar nada."""
    initialize(conn)
    initialize(conn)
    assert TABLAS_ESPERADAS.issubset(_nombres(conn, "table"))


def test_las_claves_foraneas_estan_activas(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_wal_activo_en_base_de_archivo(tmp_path: Path) -> None:
    """WAL permite leer el grafo mientras se reparsea. En :memory: no aplica."""
    conexion = connect(tmp_path / "sub" / "graph.db")
    modo = conexion.execute("PRAGMA journal_mode").fetchone()[0]
    conexion.close()
    assert modo.lower() == "wal"


def test_connect_crea_el_directorio_padre(tmp_path: Path) -> None:
    destino = tmp_path / ".arquigraph" / "graph.db"
    connect(destino).close()
    assert destino.exists()


# ---------------------------------------------------------------------------
# Metadatos
# ---------------------------------------------------------------------------


def test_sella_version_de_esquema_y_de_parser(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) == SCHEMA_VERSION
    assert get_meta(conn, "parser_version") == PARSER_VERSION
    assert get_meta(conn, "built_at") is not None


def test_meta_admite_sobrescritura(conn: sqlite3.Connection) -> None:
    set_meta(conn, "built_from_commit", "aaa111")
    set_meta(conn, "built_from_commit", "bbb222")
    assert get_meta(conn, "built_from_commit") == "bbb222"


def test_meta_inexistente_devuelve_none(conn: sqlite3.Connection) -> None:
    assert get_meta(conn, "no_existe") is None


def test_initialize_no_pisa_metadatos_previos(conn: sqlite3.Connection) -> None:
    """Reabrir el grafo no debe reescribir built_at ni perder el commit."""
    original = get_meta(conn, "built_at")
    set_meta(conn, "built_from_commit", "aaa111")
    conn.commit()
    initialize(conn)
    assert get_meta(conn, "built_at") == original
    assert get_meta(conn, "built_from_commit") == "aaa111"


# ---------------------------------------------------------------------------
# Integridad de los datos
# ---------------------------------------------------------------------------


def _insertar_nodo(conn: sqlite3.Connection, node_id: str = "n1") -> None:
    conn.execute(
        "INSERT INTO nodes (node_id, kind, qualified_name, path, "
        "signature_hash, body_hash, start_line, end_line) "
        "VALUES (?, 'function', 'app.a.f', 'app/a.py', 'sig', 'body', 1, 5)",
        (node_id,),
    )


def test_node_id_es_unico(conn: sqlite3.Connection) -> None:
    _insertar_nodo(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _insertar_nodo(conn)


def test_rechaza_una_resolucion_desconocida(conn: sqlite3.Connection) -> None:
    """El CHECK impide que entren aristas sin clasificar su procedencia."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO edges (src, dst, kind, evidence_path, evidence_line, resolution) "
            "VALUES ('a', 'b', 'CALLS', 'app/a.py', 10, 'INVENTADA')"
        )


def test_acepta_arista_a_simbolo_externo(conn: sqlite3.Connection) -> None:
    """dst puede no tener nodo local: es una libreria de terceros."""
    _insertar_nodo(conn, "n1")
    conn.execute(
        "INSERT INTO edges (src, dst, kind, evidence_path, evidence_line, "
        "confidence, resolution) "
        "VALUES ('n1', 'requests.get', 'CALLS', 'app/a.py', 12, 0.5, 'INFERRED')"
    )
    assert conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0] == 1


def test_la_misma_arista_en_dos_lineas_son_dos_aristas(conn: sqlite3.Connection) -> None:
    """La evidencia forma parte de la clave: dos llamadas, dos pruebas."""
    for linea in (10, 20):
        conn.execute(
            "INSERT INTO edges (src, dst, kind, evidence_path, evidence_line, resolution) "
            "VALUES ('a', 'b', 'CALLS', 'app/a.py', ?, 'EXTRACTED')",
            (linea,),
        )
    assert conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0] == 2


def test_la_arista_duplicada_exacta_se_rechaza(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO edges (src, dst, kind, evidence_path, evidence_line, resolution) "
        "VALUES ('a', 'b', 'CALLS', 'app/a.py', 10, 'EXTRACTED')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO edges (src, dst, kind, evidence_path, evidence_line, resolution) "
            "VALUES ('a', 'b', 'CALLS', 'app/a.py', 10, 'EXTRACTED')"
        )


# ---------------------------------------------------------------------------
# open_graph
# ---------------------------------------------------------------------------


def test_open_graph_crea_y_reabre(tmp_path: Path) -> None:
    destino = tmp_path / "graph.db"
    primera = open_graph(destino)
    set_meta(primera, "built_from_commit", "abc123")
    primera.commit()
    primera.close()

    segunda = open_graph(destino)
    assert get_meta(segunda, "built_from_commit") == "abc123"
    segunda.close()


def test_open_graph_rechaza_un_esquema_ajeno(tmp_path: Path) -> None:
    """Preferimos fallar claro a leer un grafo escrito por otra version."""
    destino = tmp_path / "graph.db"
    conexion = open_graph(destino)
    set_meta(conexion, "schema_version", "999")
    conexion.commit()
    conexion.close()

    with pytest.raises(GraphSchemaError, match="v999"):
        open_graph(destino)

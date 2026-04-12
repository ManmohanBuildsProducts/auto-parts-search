"""SQLite-backed knowledge graph storage.

The assembled graph (nodes + edges + aliases) is materialized as SQLite for
indexed lookup. JSON source files in data/knowledge_graph/ remain the committed
input; the .db is derived and gitignored.

See ADR 007.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id      TEXT PRIMARY KEY,
    type    TEXT NOT NULL,
    name    TEXT NOT NULL,
    data    TEXT NOT NULL,
    source  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS edges (
    src     TEXT NOT NULL,
    dst     TEXT NOT NULL,
    type    TEXT NOT NULL,
    weight  REAL NOT NULL DEFAULT 1.0,
    source  TEXT NOT NULL,
    PRIMARY KEY (src, dst, type)
);
CREATE INDEX IF NOT EXISTS idx_edges_src_type ON edges(src, type);
CREATE INDEX IF NOT EXISTS idx_edges_dst_type ON edges(dst, type);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    id UNINDEXED, name, aliases
);
"""


class GraphDB:
    """Thin wrapper around a SQLite graph file.

    Usage:
        with GraphDB(path) as db:
            db.init_schema()
            db.load_from_graph_dict(graph_dict)
            parts = db.parts_in_system("system:engine")
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> "GraphDB":
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        return self

    def __exit__(self, *exc) -> None:
        if self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    # ------------------------------------------------------------------
    # Schema + loading
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        assert self.conn is not None
        self.conn.executescript(SCHEMA_SQL)

    def reset(self) -> None:
        """Drop and recreate all tables. Use for idempotent rebuilds."""
        assert self.conn is not None
        self.conn.executescript(
            "DROP TABLE IF EXISTS nodes;"
            "DROP TABLE IF EXISTS edges;"
            "DROP TABLE IF EXISTS nodes_fts;"
        )
        self.init_schema()

    def load_from_graph_dict(self, graph: dict) -> None:
        """Populate from the dict returned by build_knowledge_graph().

        Shape: {metadata, nodes: [dict], edges: [dict]}.
        Nodes must have keys: id, node_type, name, provenance.source.
        Edges must have keys: source_id, target_id, edge_type, source.
        """
        assert self.conn is not None
        self.reset()

        # Nodes
        node_rows = []
        fts_rows = []
        for n in graph["nodes"]:
            src = (n.get("provenance") or {}).get("source", "unknown")
            aliases = " ".join(n.get("aliases", []) or [])
            node_rows.append((
                n["id"], n["node_type"], n.get("name", n["id"]),
                json.dumps(n, ensure_ascii=False), src,
            ))
            fts_rows.append((n["id"], n.get("name", ""), aliases))

        self.conn.executemany(
            "INSERT OR REPLACE INTO nodes (id, type, name, data, source) "
            "VALUES (?, ?, ?, ?, ?)",
            node_rows,
        )
        self.conn.executemany(
            "INSERT INTO nodes_fts (id, name, aliases) VALUES (?, ?, ?)",
            fts_rows,
        )

        # Edges
        edge_rows = []
        for e in graph["edges"]:
            edge_rows.append((
                e["source_id"], e["target_id"], e["edge_type"],
                float(e.get("confidence", 1.0)),
                e.get("source", "unknown"),
            ))
        self.conn.executemany(
            "INSERT OR REPLACE INTO edges (src, dst, type, weight, source) "
            "VALUES (?, ?, ?, ?, ?)",
            edge_rows,
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def node(self, node_id: str) -> dict | None:
        assert self.conn is not None
        row = self.conn.execute(
            "SELECT data FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return json.loads(row["data"]) if row else None

    def neighbors(self, node_id: str, edge_type: str | None = None,
                  direction: str = "out") -> list[dict]:
        """Get neighbor nodes via edges from/to node_id."""
        assert self.conn is not None
        if direction == "out":
            col_self, col_other = "src", "dst"
        elif direction == "in":
            col_self, col_other = "dst", "src"
        else:
            raise ValueError("direction must be 'in' or 'out'")

        if edge_type:
            sql = (
                f"SELECT n.data FROM edges e "
                f"JOIN nodes n ON n.id = e.{col_other} "
                f"WHERE e.{col_self} = ? AND e.type = ?"
            )
            rows = self.conn.execute(sql, (node_id, edge_type)).fetchall()
        else:
            sql = (
                f"SELECT n.data FROM edges e "
                f"JOIN nodes n ON n.id = e.{col_other} "
                f"WHERE e.{col_self} = ?"
            )
            rows = self.conn.execute(sql, (node_id,)).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def parts_in_system(self, system_id: str) -> list[dict]:
        return self.neighbors(system_id, edge_type="in_system", direction="in")

    def symptoms_for_part(self, part_id: str) -> list[dict]:
        return self.neighbors(part_id, edge_type="caused_by", direction="in")

    def compatible_vehicles(self, part_id: str) -> list[dict]:
        return self.neighbors(part_id, edge_type="fits", direction="out")

    def cross_references(self, part_id: str) -> list[dict]:
        return self.neighbors(part_id, edge_type="equivalent_to", direction="out")

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 search over node names + aliases."""
        assert self.conn is not None
        rows = self.conn.execute(
            "SELECT n.data FROM nodes_fts f "
            "JOIN nodes n ON n.id = f.id "
            "WHERE nodes_fts MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def counts(self) -> dict:
        assert self.conn is not None
        return {
            "nodes_total": self.conn.execute(
                "SELECT COUNT(*) AS c FROM nodes"
            ).fetchone()["c"],
            "nodes_by_type": {
                r["type"]: r["c"] for r in self.conn.execute(
                    "SELECT type, COUNT(*) AS c FROM nodes GROUP BY type"
                )
            },
            "edges_total": self.conn.execute(
                "SELECT COUNT(*) AS c FROM edges"
            ).fetchone()["c"],
            "edges_by_type": {
                r["type"]: r["c"] for r in self.conn.execute(
                    "SELECT type, COUNT(*) AS c FROM edges GROUP BY type"
                )
            },
        }


@contextmanager
def open_graph_db(path: Path):
    """Convenience context manager."""
    with GraphDB(path) as db:
        yield db

# Decision 007: Knowledge graph stored in SQLite, not JSON

**Date**: 2026-04-12
**Status**: Decided

## Context
Current KG is 2,627 nodes across 6 JSON files in `data/knowledge_graph/` plus an assembly step producing `graph.json`. Works today. Breaks at the next step:
1. Fitment lookup in the search hot path (`WHERE vehicle_id=? AND type='fits'`) is O(N) over JSON.
2. Boodmo→HSN mapping (T112) will add 50K–1M more nodes.
3. Incremental updates require re-serializing the entire graph.

## Decision
Store the assembled graph as SQLite at `data/knowledge_graph/graph.db`. JSON files remain the *input artifacts* (human-auditable, diffable in PRs). The `.db` is *derived* — rebuilt on demand via `python3 -m auto_parts_search build-graph-db`, not committed.

## Why SQLite, not Neo4j/Kuzu/NetworkX
- Our queries are depth-1 and depth-2 traversals, not graph analytics.
- One file, transactional, in stdlib, no infra.
- FTS5 virtual tables give us free full-text search over node names and aliases.

## Schema
```sql
CREATE TABLE nodes (
    id      TEXT PRIMARY KEY,   -- "part:brake_pad", "system:engine"
    type    TEXT NOT NULL,      -- part|category|system|vehicle|symptom|alias|brand
    name    TEXT NOT NULL,
    data    TEXT NOT NULL,      -- type-specific JSON
    source  TEXT NOT NULL       -- hsn|iti|nhtsa|asdc|boodmo|manual
);
CREATE INDEX idx_nodes_type ON nodes(type);
CREATE INDEX idx_nodes_name ON nodes(name COLLATE NOCASE);

CREATE TABLE edges (
    src     TEXT NOT NULL,
    dst     TEXT NOT NULL,
    type    TEXT NOT NULL,      -- is_a|in_system|caused_by|fits|equivalent_to|known_as
    weight  REAL NOT NULL DEFAULT 1.0,
    source  TEXT NOT NULL,
    PRIMARY KEY (src, dst, type)
);
CREATE INDEX idx_edges_src_type ON edges(src, type);
CREATE INDEX idx_edges_dst_type ON edges(dst, type);

CREATE VIRTUAL TABLE nodes_fts USING fts5(id UNINDEXED, name, aliases, content='');
```

## Implementation
- `auto_parts_search/graph_db.py` — schema, loader, query helpers.
- `scripts/build_graph_db.py` — reads JSON sources, rebuilds .db idempotently.
- `tests/test_graph_db.py` — invariants and a performance assertion (lookups <1ms).
- `.gitignore` already excludes `*.db`.

## When to outgrow SQLite
Beyond ~1M nodes with heavy analytical queries, migrate to DuckDB (still file-based) or Postgres. Not a concern for Phase 2–4.

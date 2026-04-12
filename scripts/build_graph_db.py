"""Build the SQLite knowledge graph from committed JSON inputs.

Usage:
    python3 scripts/build_graph_db.py

Reads: data/knowledge_graph/*.json (inputs)
Writes: data/knowledge_graph/graph.db (derived, gitignored)

See ADR 007.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from auto_parts_search.build_graph import build_knowledge_graph
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR
from auto_parts_search.graph_db import GraphDB


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger(__name__)

    log.info("Building graph from JSON sources...")
    graph = build_knowledge_graph()

    db_path = KNOWLEDGE_GRAPH_DIR / "graph.db"
    if db_path.exists():
        db_path.unlink()

    log.info("Materializing to %s", db_path)
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(graph)
        counts = db.counts()

    log.info("--- SQLite Graph Summary ---")
    log.info("Nodes: %d", counts["nodes_total"])
    for t, c in sorted(counts["nodes_by_type"].items(), key=lambda x: -x[1]):
        log.info("  %s: %d", t, c)
    log.info("Edges: %d", counts["edges_total"])
    for t, c in sorted(counts["edges_by_type"].items(), key=lambda x: -x[1]):
        log.info("  %s: %d", t, c)
    log.info("Wrote %s (%.1f KB)", db_path, db_path.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())

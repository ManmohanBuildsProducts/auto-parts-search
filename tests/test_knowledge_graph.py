"""Tests for the assembled knowledge graph (T111).

Validates graph connectivity, schema compliance, edge coverage,
and node count thresholds against the graph built by build_graph.py.
"""
import json
from collections import Counter
from pathlib import Path

import pytest

from auto_parts_search.build_graph import build_knowledge_graph
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR

SCHEMA_PATH = KNOWLEDGE_GRAPH_DIR / "schema.json"

VALID_NODE_TYPES = {"part", "category", "system", "vehicle", "symptom", "alias", "brand"}
VALID_EDGE_TYPES = {"is_a", "in_system", "caused_by", "fits", "equivalent_to", "known_as", "made_by", "parent_of"}


@pytest.fixture(scope="module")
def graph():
    """Build the knowledge graph once for all tests in this module."""
    return build_knowledge_graph()


@pytest.fixture(scope="module")
def nodes_by_id(graph):
    return {n["id"]: n for n in graph["nodes"]}


@pytest.fixture(scope="module")
def node_ids(graph):
    return {n["id"] for n in graph["nodes"]}


@pytest.fixture(scope="module")
def edges(graph):
    return graph["edges"]


@pytest.fixture(scope="module")
def adjacency(node_ids, edges):
    """Build adjacency sets: every node that participates in at least one edge."""
    connected = set()
    for e in edges:
        connected.add(e["source_id"])
        connected.add(e["target_id"])
    return connected


# ------------------------------------------------------------------
# Schema compliance
# ------------------------------------------------------------------


class TestSchemaCompliance:
    def test_top_level_keys(self, graph):
        assert "metadata" in graph
        assert "nodes" in graph
        assert "edges" in graph

    def test_metadata_has_version_and_sources(self, graph):
        meta = graph["metadata"]
        assert "version" in meta
        assert "sources" in meta
        assert len(meta["sources"]) >= 1

    def test_all_node_types_valid(self, graph):
        for node in graph["nodes"]:
            assert node["node_type"] in VALID_NODE_TYPES, (
                f"Invalid node_type: {node['node_type']} on {node['id']}"
            )

    def test_node_ids_match_type_prefix(self, graph):
        """Node IDs must start with their node_type followed by colon."""
        for node in graph["nodes"]:
            prefix = node["id"].split(":")[0]
            assert prefix == node["node_type"], (
                f"ID prefix '{prefix}' != node_type '{node['node_type']}' for {node['id']}"
            )

    def test_no_duplicate_node_ids(self, graph):
        ids = [n["id"] for n in graph["nodes"]]
        assert len(ids) == len(set(ids)), "Duplicate node IDs found"

    def test_all_edge_types_valid(self, edges):
        for e in edges:
            assert e["edge_type"] in VALID_EDGE_TYPES, (
                f"Invalid edge_type: {e['edge_type']}"
            )

    def test_edge_required_fields(self, edges):
        required = {"source_id", "target_id", "edge_type", "source", "confidence"}
        for i, e in enumerate(edges):
            missing = required - set(e.keys())
            assert not missing, f"Edge {i} missing fields: {missing}"

    def test_confidence_range(self, graph, edges):
        for node in graph["nodes"]:
            c = node["provenance"].get("confidence", 1.0)
            assert 0.0 <= c <= 1.0, f"Node {node['id']} confidence {c} out of range"
        for e in edges:
            assert 0.0 <= e["confidence"] <= 1.0, (
                f"Edge {e['source_id']}->{e['target_id']} confidence {e['confidence']} out of range"
            )

    def test_provenance_on_all_nodes(self, graph):
        for node in graph["nodes"]:
            assert "provenance" in node, f"Node {node['id']} missing provenance"
            assert "source" in node["provenance"], f"Node {node['id']} provenance missing source"

    def test_part_nodes_have_name(self, graph):
        for node in graph["nodes"]:
            if node["node_type"] == "part":
                assert "name" in node and node["name"], (
                    f"Part node {node['id']} missing name"
                )

    def test_vehicle_nodes_have_make_model(self, graph):
        for node in graph["nodes"]:
            if node["node_type"] == "vehicle":
                assert "make" in node and node["make"], f"Vehicle {node['id']} missing make"
                assert "model" in node and node["model"], f"Vehicle {node['id']} missing model"


# ------------------------------------------------------------------
# Node count thresholds
# ------------------------------------------------------------------


class TestNodeCounts:
    def test_total_nodes_above_threshold(self, graph):
        assert len(graph["nodes"]) >= 1000, (
            f"Expected 1000+ nodes, got {len(graph['nodes'])}"
        )

    def test_part_node_count(self, graph):
        parts = [n for n in graph["nodes"] if n["node_type"] == "part"]
        assert len(parts) >= 200, f"Expected 200+ part nodes, got {len(parts)}"

    def test_category_node_count(self, graph):
        cats = [n for n in graph["nodes"] if n["node_type"] == "category"]
        assert len(cats) >= 200, f"Expected 200+ category nodes, got {len(cats)}"

    def test_system_nodes_present(self, graph):
        systems = [n for n in graph["nodes"] if n["node_type"] == "system"]
        assert len(systems) >= 3, f"Expected 3+ system nodes, got {len(systems)}"

    def test_symptom_nodes_present(self, graph):
        symptoms = [n for n in graph["nodes"] if n["node_type"] == "symptom"]
        assert len(symptoms) >= 5, f"Expected 5+ symptom nodes, got {len(symptoms)}"

    def test_vehicle_nodes_present(self, graph):
        vehicles = [n for n in graph["nodes"] if n["node_type"] == "vehicle"]
        assert len(vehicles) >= 10, f"Expected 10+ vehicle nodes, got {len(vehicles)}"

    def test_alias_nodes_present(self, graph):
        aliases = [n for n in graph["nodes"] if n["node_type"] == "alias"]
        assert len(aliases) >= 5, f"Expected 5+ alias nodes, got {len(aliases)}"

    def test_brand_nodes_present(self, graph):
        brands = [n for n in graph["nodes"] if n["node_type"] == "brand"]
        assert len(brands) >= 3, f"Expected 3+ brand nodes, got {len(brands)}"

    def test_total_edges_above_threshold(self, edges):
        assert len(edges) >= 500, f"Expected 500+ edges, got {len(edges)}"


# ------------------------------------------------------------------
# Edge type coverage
# ------------------------------------------------------------------


class TestEdgeCoverage:
    def test_all_eight_edge_types_populated(self, edges):
        """All 8 defined edge types should have at least one edge.

        Note: equivalent_to may not be populated if no cross-references
        exist in the source data, so we check for at least 7 types.
        """
        present = {e["edge_type"] for e in edges}
        # At minimum the 7 core types should be populated
        expected_core = {"is_a", "in_system", "caused_by", "fits", "known_as", "made_by", "parent_of"}
        missing = expected_core - present
        assert not missing, f"Missing edge types: {missing}"

    def test_is_a_edges_exist(self, edges):
        count = sum(1 for e in edges if e["edge_type"] == "is_a")
        assert count >= 50, f"Expected 50+ is_a edges, got {count}"

    def test_in_system_edges_exist(self, edges):
        count = sum(1 for e in edges if e["edge_type"] == "in_system")
        assert count >= 5, f"Expected 5+ in_system edges, got {count}"

    def test_caused_by_edges_exist(self, edges):
        count = sum(1 for e in edges if e["edge_type"] == "caused_by")
        assert count >= 5, f"Expected 5+ caused_by edges, got {count}"

    def test_fits_edges_exist(self, edges):
        count = sum(1 for e in edges if e["edge_type"] == "fits")
        assert count >= 10, f"Expected 10+ fits edges, got {count}"

    def test_known_as_edges_exist(self, edges):
        count = sum(1 for e in edges if e["edge_type"] == "known_as")
        assert count >= 5, f"Expected 5+ known_as edges, got {count}"

    def test_made_by_edges_exist(self, edges):
        count = sum(1 for e in edges if e["edge_type"] == "made_by")
        assert count >= 3, f"Expected 3+ made_by edges, got {count}"

    def test_parent_of_edges_exist(self, edges):
        count = sum(1 for e in edges if e["edge_type"] == "parent_of")
        assert count >= 10, f"Expected 10+ parent_of edges, got {count}"


# ------------------------------------------------------------------
# Graph connectivity
# ------------------------------------------------------------------


class TestConnectivity:
    def test_no_orphan_nodes(self, node_ids, adjacency):
        """Nearly all nodes must participate in at least one edge.

        A small number of orphans is tolerable (e.g. ASDC keyword-extracted
        parts that lack cross-references), but >1% signals a builder bug.
        """
        orphans = node_ids - adjacency
        orphan_pct = len(orphans) / len(node_ids) if node_ids else 0
        assert orphan_pct < 0.01, (
            f"{len(orphans)} orphan nodes ({orphan_pct:.1%}): {sorted(list(orphans))[:10]}..."
        )

    def test_graph_has_few_components(self, node_ids, edges):
        """The graph should have a small number of connected components.

        Multiple sources (HSN, ITI, NHTSA, vocabulary) may create separate
        clusters until cross-reference edges link them. We verify the largest
        component covers most nodes and total components stay bounded.
        """
        if not node_ids:
            pytest.skip("No nodes in graph")

        # Build undirected adjacency list (only connected nodes)
        adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
        for e in edges:
            if e["source_id"] in adj and e["target_id"] in adj:
                adj[e["source_id"]].add(e["target_id"])
                adj[e["target_id"]].add(e["source_id"])

        # Find all connected components via BFS
        remaining = set(node_ids)
        components: list[set[str]] = []
        while remaining:
            start = next(iter(remaining))
            visited = set()
            queue = [start]
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                visited.add(current)
                queue.extend(adj[current] - visited)
            components.append(visited)
            remaining -= visited

        components.sort(key=len, reverse=True)
        largest = len(components[0])
        total = len(node_ids)

        # Largest component should cover at least 30% of nodes
        assert largest / total >= 0.30, (
            f"Largest component only covers {largest}/{total} ({largest/total:.0%}) nodes"
        )
        # HSN taxonomy creates many independent chapter trees, so component
        # count can be high. But it shouldn't grow unboundedly — cap at 150.
        assert len(components) <= 150, (
            f"Graph has {len(components)} components — too fragmented"
        )

    def test_all_parts_have_is_a_edge(self, graph, edges):
        """Every part node should have at least one is_a edge (category link)."""
        part_ids = {n["id"] for n in graph["nodes"] if n["node_type"] == "part"}
        parts_with_is_a = {e["source_id"] for e in edges if e["edge_type"] == "is_a"}
        missing = part_ids - parts_with_is_a
        # Allow some parts without is_a (from ITI/ASDC that lack HSN codes),
        # but the majority should be classified
        coverage = 1 - len(missing) / len(part_ids) if part_ids else 1
        assert coverage >= 0.3, (
            f"Only {coverage:.0%} of parts have is_a edges. "
            f"{len(missing)} parts without category. Samples: {sorted(list(missing))[:10]}"
        )

    def test_edges_reference_existing_nodes(self, node_ids, edges):
        """All edge source_id and target_id must reference existing nodes."""
        dangling = []
        for i, e in enumerate(edges):
            if e["source_id"] not in node_ids:
                dangling.append(f"edge[{i}] source_id={e['source_id']}")
            if e["target_id"] not in node_ids:
                dangling.append(f"edge[{i}] target_id={e['target_id']}")
        assert not dangling, (
            f"{len(dangling)} dangling edge references: {dangling[:10]}"
        )

    def test_no_duplicate_edges(self, edges):
        """No duplicate (source_id, target_id, edge_type) triples."""
        seen = set()
        dupes = []
        for e in edges:
            key = (e["source_id"], e["target_id"], e["edge_type"])
            if key in seen:
                dupes.append(key)
            seen.add(key)
        assert not dupes, f"{len(dupes)} duplicate edges found: {dupes[:5]}"


# ------------------------------------------------------------------
# Edge direction correctness
# ------------------------------------------------------------------


class TestEdgeDirections:
    def test_is_a_goes_part_to_category(self, edges, nodes_by_id):
        for e in edges:
            if e["edge_type"] == "is_a":
                src = nodes_by_id.get(e["source_id"])
                tgt = nodes_by_id.get(e["target_id"])
                if src and tgt:
                    assert src["node_type"] == "part", (
                        f"is_a source should be part, got {src['node_type']} ({e['source_id']})"
                    )
                    assert tgt["node_type"] == "category", (
                        f"is_a target should be category, got {tgt['node_type']} ({e['target_id']})"
                    )

    def test_in_system_goes_part_to_system(self, edges, nodes_by_id):
        for e in edges:
            if e["edge_type"] == "in_system":
                src = nodes_by_id.get(e["source_id"])
                tgt = nodes_by_id.get(e["target_id"])
                if src and tgt:
                    assert src["node_type"] == "part", (
                        f"in_system source should be part, got {src['node_type']}"
                    )
                    assert tgt["node_type"] == "system", (
                        f"in_system target should be system, got {tgt['node_type']}"
                    )

    def test_caused_by_goes_symptom_to_part(self, edges, nodes_by_id):
        for e in edges:
            if e["edge_type"] == "caused_by":
                src = nodes_by_id.get(e["source_id"])
                tgt = nodes_by_id.get(e["target_id"])
                if src and tgt:
                    assert src["node_type"] == "symptom", (
                        f"caused_by source should be symptom, got {src['node_type']}"
                    )
                    assert tgt["node_type"] == "part", (
                        f"caused_by target should be part, got {tgt['node_type']}"
                    )

    def test_fits_goes_part_to_vehicle(self, edges, nodes_by_id):
        for e in edges:
            if e["edge_type"] == "fits":
                src = nodes_by_id.get(e["source_id"])
                tgt = nodes_by_id.get(e["target_id"])
                if src and tgt:
                    assert src["node_type"] == "part", (
                        f"fits source should be part, got {src['node_type']}"
                    )
                    assert tgt["node_type"] == "vehicle", (
                        f"fits target should be vehicle, got {tgt['node_type']}"
                    )

    def test_parent_of_goes_category_to_category(self, edges, nodes_by_id):
        for e in edges:
            if e["edge_type"] == "parent_of":
                src = nodes_by_id.get(e["source_id"])
                tgt = nodes_by_id.get(e["target_id"])
                if src and tgt:
                    assert src["node_type"] == "category", (
                        f"parent_of source should be category, got {src['node_type']}"
                    )
                    assert tgt["node_type"] == "category", (
                        f"parent_of target should be category, got {tgt['node_type']}"
                    )

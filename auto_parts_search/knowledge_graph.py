"""Knowledge graph schema for Indian auto parts domain.

Node types: Part, Category, System, Vehicle, Symptom, Alias, Brand
Edge types: is_a, in_system, caused_by, fits, equivalent_to, known_as, made_by, parent_of

Design: ADR-003 (context/decisions/003-knowledge-graph-approach.md)
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    PART = "part"
    CATEGORY = "category"
    SYSTEM = "system"
    VEHICLE = "vehicle"
    SYMPTOM = "symptom"
    ALIAS = "alias"
    BRAND = "brand"


class EdgeType(str, Enum):
    IS_A = "is_a"              # Part → Category
    IN_SYSTEM = "in_system"    # Part → System
    CAUSED_BY = "caused_by"    # Symptom → Part
    FITS = "fits"              # Part → Vehicle
    EQUIVALENT_TO = "equivalent_to"  # Part → Part
    KNOWN_AS = "known_as"      # Part → Alias
    MADE_BY = "made_by"        # Part → Brand
    PARENT_OF = "parent_of"    # Category → Category


class AliasType(str, Enum):
    HINDI = "hindi"
    HINGLISH = "hinglish"
    MISSPELLING = "misspelling"
    BRAND_GENERIC = "brand_generic"
    BRITISH_ENGLISH = "british_english"


# ---------------------------------------------------------------------------
# Node dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Provenance:
    """Tracks where a node or edge came from."""
    source: str          # e.g., "hsn_cbic", "iti_dgt", "nhtsa", "tecdoc", "vocabulary_research"
    confidence: float = 1.0  # 0.0–1.0
    source_id: str = ""  # ID in the source system (e.g., HSN code, NHTSA make_id)
    added_date: str = ""  # ISO date string


@dataclass
class PartNode:
    id: str                              # e.g., "part:brake_pad"
    name: str
    aliases: list[str] = field(default_factory=list)
    hsn_code: str = ""
    part_numbers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(source=""))

    @property
    def node_type(self) -> str:
        return NodeType.PART.value


@dataclass
class CategoryNode:
    id: str                              # e.g., "category:8708_30"
    name: str
    hsn_code: str = ""
    level: int = 0                       # depth in HSN hierarchy (0=chapter, 1=heading, 2=subheading)
    provenance: Provenance = field(default_factory=lambda: Provenance(source=""))

    @property
    def node_type(self) -> str:
        return NodeType.CATEGORY.value


@dataclass
class SystemNode:
    id: str                              # e.g., "system:braking"
    name: str
    description: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(source=""))

    @property
    def node_type(self) -> str:
        return NodeType.SYSTEM.value


@dataclass
class VehicleNode:
    id: str                              # e.g., "vehicle:honda_city_2019"
    make: str
    model: str
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    provenance: Provenance = field(default_factory=lambda: Provenance(source=""))

    @property
    def node_type(self) -> str:
        return NodeType.VEHICLE.value


@dataclass
class SymptomNode:
    id: str                              # e.g., "symptom:grinding_noise_braking"
    description: str
    hindi_description: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(source=""))

    @property
    def node_type(self) -> str:
        return NodeType.SYMPTOM.value


@dataclass
class AliasNode:
    id: str                              # e.g., "alias:shocker_hinglish"
    name: str
    language: str = "en"                 # "en", "hi", "hinglish"
    alias_type: str = ""                 # AliasType value
    provenance: Provenance = field(default_factory=lambda: Provenance(source=""))

    @property
    def node_type(self) -> str:
        return NodeType.ALIAS.value


@dataclass
class BrandNode:
    id: str                              # e.g., "brand:bosch"
    name: str
    country: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(source=""))

    @property
    def node_type(self) -> str:
        return NodeType.BRAND.value


# ---------------------------------------------------------------------------
# Edge dataclass
# ---------------------------------------------------------------------------

@dataclass
class Edge:
    source_id: str       # node ID
    target_id: str       # node ID
    edge_type: str       # EdgeType value
    source: str          # data source that provided this edge
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)  # edge-specific extra data


# ---------------------------------------------------------------------------
# Knowledge Graph container
# ---------------------------------------------------------------------------

# Union type for all node types
Node = PartNode | CategoryNode | SystemNode | VehicleNode | SymptomNode | AliasNode | BrandNode

# Map node_type string to dataclass for deserialization
_NODE_CLASSES = {
    NodeType.PART.value: PartNode,
    NodeType.CATEGORY.value: CategoryNode,
    NodeType.SYSTEM.value: SystemNode,
    NodeType.VEHICLE.value: VehicleNode,
    NodeType.SYMPTOM.value: SymptomNode,
    NodeType.ALIAS.value: AliasNode,
    NodeType.BRAND.value: BrandNode,
}


@dataclass
class KnowledgeGraph:
    """Container for the full knowledge graph. Serializes to/from JSON."""
    nodes: list[dict] = field(default_factory=list)  # serialized node dicts
    edges: list[dict] = field(default_factory=list)  # serialized edge dicts
    metadata: dict = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        """Add a node, skipping if ID already exists."""
        node_dict = asdict(node)
        node_dict["node_type"] = node.node_type
        # Deduplicate by ID
        for existing in self.nodes:
            if existing["id"] == node_dict["id"]:
                return
        self.nodes.append(node_dict)

    def add_edge(self, edge: Edge) -> None:
        """Add an edge, skipping exact duplicates."""
        edge_dict = asdict(edge)
        for existing in self.edges:
            if (existing["source_id"] == edge_dict["source_id"]
                    and existing["target_id"] == edge_dict["target_id"]
                    and existing["edge_type"] == edge_dict["edge_type"]):
                return
        self.edges.append(edge_dict)

    def get_node(self, node_id: str) -> Optional[dict]:
        for n in self.nodes:
            if n["id"] == node_id:
                return n
        return None

    def get_edges(self, node_id: str, edge_type: Optional[str] = None) -> list[dict]:
        """Get all edges where node_id is source or target."""
        results = []
        for e in self.edges:
            if e["source_id"] == node_id or e["target_id"] == node_id:
                if edge_type is None or e["edge_type"] == edge_type:
                    results.append(e)
        return results

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "metadata": self.metadata,
            "nodes": self.nodes,
            "edges": self.edges,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            metadata=data.get("metadata", {}),
        )

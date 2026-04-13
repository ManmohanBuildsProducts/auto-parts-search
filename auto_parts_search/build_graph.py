"""Build unified knowledge graph from Phase 2 data sources.

Reads:
  data/knowledge_graph/hsn_taxonomy.json
  data/knowledge_graph/iti_diagnostics.json
  data/knowledge_graph/nhtsa_recalls.json
  data/knowledge_graph/asdc_tasks.json

Writes:
  data/knowledge_graph/graph.json
"""
import json
import logging
import re
from datetime import date
from pathlib import Path

from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()


def _slugify(text: str) -> str:
    """Convert text to a slug for node IDs."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class GraphBuilder:
    """Assembles nodes and edges from multiple sources into a unified graph."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}  # id -> node
        self.edges: list[dict] = []

    def _add_node(self, node_id: str, node: dict) -> str:
        """Add node if not already present. Returns the node ID."""
        if node_id not in self.nodes:
            self.nodes[node_id] = node
        return node_id

    def _add_edge(self, source_id: str, target_id: str, edge_type: str,
                  source: str, confidence: float = 1.0, metadata: dict | None = None):
        """Add an edge between two nodes."""
        self.edges.append({
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "source": source,
            "confidence": confidence,
            "metadata": metadata or {},
        })

    # ------------------------------------------------------------------
    # HSN taxonomy -> Category nodes + parent_of edges
    # ------------------------------------------------------------------
    def ingest_hsn(self, path: Path):
        """Create Category nodes from HSN codes with parent_of hierarchy.

        Leaf codes (no children) are promoted to Part nodes with is_a edges
        back to their parent Category, since they describe specific parts.
        """
        with open(path) as f:
            data = json.load(f)

        part_count = 0

        for code_entry in data["codes"]:
            code = code_entry["code"]
            desc = code_entry["description"]
            level = code_entry["level"]
            is_leaf = not code_entry.get("children")
            parent_code = code_entry.get("parent_code", "")

            if is_leaf:
                # Leaf codes become Part nodes
                node_id = f"part:hsn_{code}"
                self._add_node(node_id, {
                    "id": node_id,
                    "node_type": "part",
                    "name": desc,
                    "aliases": [],
                    "hsn_code": code,
                    "part_numbers": [],
                    "provenance": {
                        "source": "hsn_cbic",
                        "confidence": 1.0,
                        "source_id": code,
                        "added_date": TODAY,
                    },
                })
                part_count += 1

                # is_a edge: Part -> parent Category
                if parent_code:
                    parent_id = f"category:hsn_{parent_code}"
                    self._add_edge(node_id, parent_id, "is_a", "hsn_cbic")
            else:
                # Non-leaf codes become Category nodes
                node_id = f"category:hsn_{code}"
                self._add_node(node_id, {
                    "id": node_id,
                    "node_type": "category",
                    "name": desc,
                    "hsn_code": code,
                    "level": level - 1,  # schema: 0=chapter, 1=heading, 2=subheading
                    "provenance": {
                        "source": "hsn_cbic",
                        "confidence": 1.0,
                        "source_id": code,
                        "added_date": TODAY,
                    },
                })

                # parent_of edge
                if parent_code:
                    parent_id = f"category:hsn_{parent_code}"
                    self._add_edge(parent_id, node_id, "parent_of", "hsn_cbic")

        cat_count = len([n for n in self.nodes if n.startswith("category:hsn_")])
        logger.info("HSN: %d category nodes, %d part nodes (leaf codes)", cat_count, part_count)

    # ------------------------------------------------------------------
    # ITI diagnostics -> System, Part, Symptom nodes + edges
    # ------------------------------------------------------------------
    def ingest_iti(self, path: Path):
        """Create System, Part, Symptom nodes from ITI diagnostic chains."""
        with open(path) as f:
            data = json.load(f)

        systems_added = set()
        parts_added = set()

        for chain in data["chains"]:
            system_name = chain["system"]
            system_slug = _slugify(system_name)
            system_id = f"system:{system_slug}"

            # System node
            if system_id not in systems_added:
                self._add_node(system_id, {
                    "id": system_id,
                    "node_type": "system",
                    "name": system_name.replace("_", " ").title(),
                    "description": "",
                    "provenance": {
                        "source": "iti_dgt",
                        "confidence": 0.9,
                        "source_id": system_name,
                        "added_date": TODAY,
                    },
                })
                systems_added.add(system_id)

            # Symptom node
            symptom_slug = _slugify(chain["symptom"])
            symptom_id = f"symptom:{symptom_slug}"
            self._add_node(symptom_id, {
                "id": symptom_id,
                "node_type": "symptom",
                "description": chain["symptom"],
                "hindi_description": "",
                "provenance": {
                    "source": "iti_dgt",
                    "confidence": chain.get("confidence", 0.8),
                    "source_id": chain["id"],
                    "added_date": TODAY,
                },
            })

            # Part nodes + edges
            for part_name in chain["related_parts"]:
                part_slug = _slugify(part_name)
                part_id = f"part:{part_slug}"

                if part_id not in parts_added:
                    self._add_node(part_id, {
                        "id": part_id,
                        "node_type": "part",
                        "name": part_name.title(),
                        "aliases": [],
                        "hsn_code": "",
                        "part_numbers": [],
                        "provenance": {
                            "source": "iti_dgt",
                            "confidence": chain.get("confidence", 0.8),
                            "source_id": chain["id"],
                            "added_date": TODAY,
                        },
                    })
                    parts_added.add(part_id)

                # Part in_system System
                self._add_edge(part_id, system_id, "in_system", "iti_dgt",
                               confidence=chain.get("confidence", 0.8))

                # Symptom caused_by Part
                self._add_edge(symptom_id, part_id, "caused_by", "iti_dgt",
                               confidence=chain.get("confidence", 0.8),
                               metadata={"diagnosis_steps": chain["diagnosis_steps"]})

        logger.info("ITI: %d systems, %d parts, %d symptoms",
                     len(systems_added), len(parts_added),
                     len([n for n in self.nodes if n.startswith("symptom:")]))

    def ingest_iti_v2(self, systems_path: Path, diagnostics_path: Path, aliases_path: Path):
        """Ingest merged v1+v2 ITI files with per-entry provenance (ADR 008, T110b).

        Supersedes ingest_iti. Reads three files:
        - iti_systems_v2.json: authoritative systems + parts list (wasn't ingested in v1)
        - iti_diagnostics_v2.json: merged hand-curated + LLM-extracted chains
        - iti_aliases_v2.json: standalone Indian-English / Hindi alias layer
        """
        systems_count = parts_count = symptom_count = alias_count = 0
        alias_nodes_added: set[str] = set()

        # 1) Systems + their parts (the new rich source)
        with open(systems_path) as f:
            sys_data = json.load(f)

        for system in sys_data["systems"]:
            sid = system["system_id"]
            if not sid.startswith("system:"):
                sid = f"system:{_slugify(sid)}"

            self._add_node(sid, {
                "id": sid,
                "node_type": "system",
                "name": system.get("system_name", sid.replace("system:", "").replace("_", " ").title()),
                "description": system.get("description", ""),
                "provenance": {
                    "source": "iti_dgt_v2",
                    "source_trades": system.get("source_trades", []),
                    "confidence": 0.9,
                    "added_date": TODAY,
                },
            })
            systems_count += 1

            for part in system.get("parts", []):
                pname = part.get("name", "").strip()
                if not pname:
                    continue
                pslug = _slugify(pname)
                pid = f"part:{pslug}"

                # Confidence: dual-sourced > hand_curated-only > llm-only
                methods = sorted({p.get("method") for p in part.get("provenance", []) if p.get("method")})
                if "hand_curated" in methods and "llm_extracted" in methods:
                    confidence = 0.95
                elif "hand_curated" in methods:
                    confidence = 0.9
                else:
                    confidence = 0.8

                source_pages = sorted({
                    p.get("page") for p in part.get("provenance", [])
                    if p.get("page")
                })

                if pid not in self.nodes:
                    self._add_node(pid, {
                        "id": pid,
                        "node_type": "part",
                        "name": pname,
                        "aliases": list(part.get("aliases", [])),
                        "role": part.get("role", ""),
                        "hsn_code": "",
                        "part_numbers": [],
                        "provenance": {
                            "source": "iti_dgt_v2",
                            "methods": methods,
                            "confidence": confidence,
                            "source_pages": source_pages,
                            "added_date": TODAY,
                        },
                    })
                    parts_count += 1

                self._add_edge(pid, sid, "in_system", "iti_dgt_v2", confidence=confidence)

                # Each alias → Alias node → known_as → Part
                for alias_text in part.get("aliases", []):
                    if not alias_text:
                        continue
                    aslug = _slugify(alias_text)
                    aid = f"alias:{aslug}"
                    if aid not in alias_nodes_added and aid not in self.nodes:
                        self._add_node(aid, {
                            "id": aid,
                            "node_type": "alias",
                            "name": alias_text,
                            "provenance": {
                                "source": "iti_dgt_v2",
                                "confidence": 0.8,
                                "added_date": TODAY,
                            },
                        })
                        alias_nodes_added.add(aid)
                    self._add_edge(aid, pid, "known_as", "iti_dgt_v2", confidence=0.8)

        # 2) Diagnostic chains — symptoms + caused_by edges to parts
        with open(diagnostics_path) as f:
            diag_data = json.load(f)

        for chain in diag_data["chains"]:
            symptom_text = chain.get("symptom", "").strip()
            if not symptom_text:
                continue
            symptom_slug = _slugify(symptom_text)
            symptom_id = f"symptom:{symptom_slug}"

            methods = sorted({p.get("method") for p in chain.get("provenance", []) if p.get("method")})
            confidences = [p.get("confidence") for p in chain.get("provenance", []) if p.get("confidence") is not None]
            confidence = max(confidences) if confidences else 0.8

            self._add_node(symptom_id, {
                "id": symptom_id,
                "node_type": "symptom",
                "description": symptom_text,
                "hindi_description": "",
                "provenance": {
                    "source": "iti_dgt_v2",
                    "methods": methods,
                    "confidence": confidence,
                    "source_id": chain.get("id", ""),
                    "added_date": TODAY,
                },
            })
            symptom_count += 1

            # System node (may already exist from systems ingest)
            raw_sys = chain.get("system", "")
            if raw_sys:
                system_slug = _slugify(raw_sys)
                system_id = f"system:{system_slug}"
                if system_id not in self.nodes:
                    self._add_node(system_id, {
                        "id": system_id,
                        "node_type": "system",
                        "name": raw_sys.replace("_", " ").title(),
                        "description": "",
                        "provenance": {
                            "source": "iti_dgt_v2",
                            "confidence": 0.8,
                            "added_date": TODAY,
                        },
                    })

            # Part nodes + caused_by edges
            for part_name in chain.get("related_parts", []):
                if not part_name:
                    continue
                part_slug = _slugify(part_name)
                part_id = f"part:{part_slug}"
                if part_id not in self.nodes:
                    self._add_node(part_id, {
                        "id": part_id,
                        "node_type": "part",
                        "name": part_name.title(),
                        "aliases": [],
                        "hsn_code": "",
                        "part_numbers": [],
                        "provenance": {
                            "source": "iti_dgt_v2",
                            "methods": methods or ["llm_extracted"],
                            "confidence": confidence,
                            "added_date": TODAY,
                        },
                    })
                    parts_count += 1
                self._add_edge(symptom_id, part_id, "caused_by", "iti_dgt_v2",
                               confidence=confidence,
                               metadata={"diagnosis_steps": chain.get("diagnosis_steps", [])})

        # 3) Standalone aliases layer
        if aliases_path.exists():
            with open(aliases_path) as f:
                alias_data = json.load(f)

            for a in alias_data.get("aliases", []):
                canonical = a.get("canonical", "").strip()
                alias = a.get("alias", "").strip()
                if not (canonical and alias):
                    continue
                canonical_id = f"part:{_slugify(canonical)}"
                alias_id = f"alias:{_slugify(alias)}"

                if alias_id not in self.nodes:
                    self._add_node(alias_id, {
                        "id": alias_id,
                        "node_type": "alias",
                        "name": alias,
                        "provenance": {
                            "source": "iti_dgt_v2",
                            "confidence": 0.85,
                            "added_date": TODAY,
                        },
                    })
                    alias_count += 1

                # Only edge if the canonical part exists in the graph
                if canonical_id in self.nodes:
                    self._add_edge(alias_id, canonical_id, "known_as", "iti_dgt_v2", confidence=0.85)

        logger.info(
            "ITI v2: %d systems, %d parts (newly added), %d symptoms, %d standalone aliases",
            systems_count, parts_count, symptom_count, alias_count,
        )

    # ------------------------------------------------------------------
    # NHTSA recalls -> Part, Vehicle nodes + fits edges
    # ------------------------------------------------------------------
    def ingest_nhtsa(self, path: Path):
        """Create Part and Vehicle nodes from NHTSA component cross-references."""
        with open(path) as f:
            data = json.load(f)

        crossref = data["component_crossref"]
        vehicles_added = set()

        for component_name, vehicle_list in crossref.items():
            # Part node from component name
            part_slug = _slugify(component_name)
            part_id = f"part:{part_slug}"

            self._add_node(part_id, {
                "id": part_id,
                "node_type": "part",
                "name": component_name.title(),
                "aliases": [],
                "hsn_code": "",
                "part_numbers": [],
                "provenance": {
                    "source": "nhtsa",
                    "confidence": 0.9,
                    "source_id": component_name,
                    "added_date": TODAY,
                },
            })

            for vehicle_str in vehicle_list:
                # Parse "MAKE|MODEL"
                parts = vehicle_str.split("|")
                if len(parts) != 2:
                    continue
                make, model = parts[0].strip(), parts[1].strip()
                vehicle_slug = _slugify(f"{make}_{model}")
                vehicle_id = f"vehicle:{vehicle_slug}"

                if vehicle_id not in vehicles_added:
                    self._add_node(vehicle_id, {
                        "id": vehicle_id,
                        "node_type": "vehicle",
                        "make": make.title(),
                        "model": model.title(),
                        "year_start": None,
                        "year_end": None,
                        "provenance": {
                            "source": "nhtsa",
                            "confidence": 0.9,
                            "source_id": vehicle_str,
                            "added_date": TODAY,
                        },
                    })
                    vehicles_added.add(vehicle_id)

                # Part fits Vehicle
                self._add_edge(part_id, vehicle_id, "fits", "nhtsa", confidence=0.9,
                               metadata={"source_recall": True})

        logger.info("NHTSA: %d part nodes, %d vehicle nodes",
                     len([n for n in self.nodes if n.startswith("part:")]),
                     len(vehicles_added))

    # ------------------------------------------------------------------
    # ASDC qualification packs -> Part nodes from task descriptions
    # ------------------------------------------------------------------
    def ingest_asdc(self, path: Path):
        """Extract part references from ASDC qualification pack tasks."""
        with open(path) as f:
            data = json.load(f)

        # Auto-parts keywords to extract from task descriptions
        part_keywords = [
            "brake pad", "brake shoe", "brake drum", "brake disc", "wheel cylinder",
            "clutch", "clutch plate", "clutch cable", "suspension", "shock absorber",
            "steering", "fuel injector", "fuel pump", "fuel filter", "air filter",
            "oil filter", "spark plug", "battery", "alternator", "starter motor",
            "radiator", "thermostat", "water pump", "compressor", "condenser",
            "evaporator", "belt", "hose", "bearing", "gasket", "valve",
            "piston", "cylinder", "exhaust", "muffler", "catalytic converter",
            "wiper", "headlight", "tail light", "indicator", "horn",
            "control arm", "tie rod", "ball joint", "cv joint", "drive shaft",
            "chain sprocket", "chain", "sprocket", "caliper", "rotor",
            "high voltage battery", "motor controller", "inverter", "charger",
            "body panel", "bumper", "fender", "door", "windshield",
        ]

        parts_found = set()

        for qp in data["qualification_packs"]:
            qp_name = qp["name"]
            for nos in qp["nos_units"]:
                # Scan performance criteria for part mentions
                for pc in nos["performance_criteria"]:
                    task_lower = pc["task"].lower()
                    for keyword in part_keywords:
                        if keyword in task_lower:
                            part_slug = _slugify(keyword)
                            part_id = f"part:{part_slug}"
                            if part_id not in parts_found:
                                self._add_node(part_id, {
                                    "id": part_id,
                                    "node_type": "part",
                                    "name": keyword.title(),
                                    "aliases": [],
                                    "hsn_code": "",
                                    "part_numbers": [],
                                    "provenance": {
                                        "source": "iti_dgt",  # ASDC is under DGT umbrella
                                        "confidence": 0.7,
                                        "source_id": f"{qp['qp_code']}/{nos['nos_code']}/{pc['id']}",
                                        "added_date": TODAY,
                                    },
                                })
                                parts_found.add(part_id)

                # Scan knowledge items too
                for ku in nos.get("knowledge", []):
                    desc_lower = ku["description"].lower()
                    for keyword in part_keywords:
                        if keyword in desc_lower:
                            part_slug = _slugify(keyword)
                            part_id = f"part:{part_slug}"
                            if part_id not in parts_found:
                                self._add_node(part_id, {
                                    "id": part_id,
                                    "node_type": "part",
                                    "name": keyword.title(),
                                    "aliases": [],
                                    "hsn_code": "",
                                    "part_numbers": [],
                                    "provenance": {
                                        "source": "iti_dgt",
                                        "confidence": 0.7,
                                        "source_id": f"{qp['qp_code']}/{nos['nos_code']}/{ku['id']}",
                                        "added_date": TODAY,
                                    },
                                })
                                parts_found.add(part_id)

        logger.info("ASDC: %d additional part nodes extracted", len(parts_found))

    # ------------------------------------------------------------------
    # Vocabulary research -> Alias, Brand nodes + known_as, made_by edges
    # ------------------------------------------------------------------
    def ingest_vocabulary(self):
        """Create Alias and Brand nodes from vocabulary research data.

        Imports synonym pairs (Hindi/Hinglish), misspellings, and
        brand-as-generic pairs from training/vocabulary_pairs.py.
        """
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from training.vocabulary_pairs import (
            SYNONYM_PAIRS_RAW, MISSPELLING_PAIRS_RAW, BRAND_GENERIC_PAIRS_RAW,
        )

        aliases_added = set()
        brands_added = set()

        # --- Synonym pairs: create Alias nodes with known_as edges ---
        for english, hindi_or_alt in SYNONYM_PAIRS_RAW:
            if english.lower() == hindi_or_alt.lower():
                continue

            # Determine alias type
            has_hindi = any(ord(c) > 127 or c in "āīūṇṭḍ" for c in hindi_or_alt)
            # Heuristic: if the alt contains non-ASCII or known Hinglish patterns
            is_hinglish = not has_hindi and hindi_or_alt.lower() != english.lower()

            if has_hindi:
                alias_type = "hindi"
                language = "hi"
            else:
                alias_type = "hinglish"
                language = "hinglish"

            alias_slug = _slugify(hindi_or_alt)
            alias_id = f"alias:{alias_slug}"

            if alias_id not in aliases_added:
                self._add_node(alias_id, {
                    "id": alias_id,
                    "node_type": "alias",
                    "name": hindi_or_alt,
                    "language": language,
                    "alias_type": alias_type,
                    "provenance": {
                        "source": "vocabulary_research",
                        "confidence": 0.9,
                        "source_id": "",
                        "added_date": TODAY,
                    },
                })
                aliases_added.add(alias_id)

            # Ensure part node exists
            part_slug = _slugify(english)
            part_id = f"part:{part_slug}"
            self._add_node(part_id, {
                "id": part_id,
                "node_type": "part",
                "name": english.title(),
                "aliases": [],
                "hsn_code": "",
                "part_numbers": [],
                "provenance": {
                    "source": "vocabulary_research",
                    "confidence": 0.9,
                    "source_id": "",
                    "added_date": TODAY,
                },
            })

            # Part known_as Alias
            self._add_edge(part_id, alias_id, "known_as", "vocabulary_research",
                           confidence=0.9)

        # --- Misspelling pairs: create Alias nodes (misspelling type) ---
        for misspelled, correct in MISSPELLING_PAIRS_RAW:
            alias_slug = _slugify(misspelled)
            alias_id = f"alias:{alias_slug}"

            if alias_id not in aliases_added:
                self._add_node(alias_id, {
                    "id": alias_id,
                    "node_type": "alias",
                    "name": misspelled,
                    "language": "en",
                    "alias_type": "misspelling",
                    "provenance": {
                        "source": "vocabulary_research",
                        "confidence": 1.0,
                        "source_id": "",
                        "added_date": TODAY,
                    },
                })
                aliases_added.add(alias_id)

            # Ensure part node exists
            part_slug = _slugify(correct)
            part_id = f"part:{part_slug}"
            self._add_node(part_id, {
                "id": part_id,
                "node_type": "part",
                "name": correct.title(),
                "aliases": [],
                "hsn_code": "",
                "part_numbers": [],
                "provenance": {
                    "source": "vocabulary_research",
                    "confidence": 1.0,
                    "source_id": "",
                    "added_date": TODAY,
                },
            })

            # Part known_as Alias (misspelling)
            self._add_edge(part_id, alias_id, "known_as", "vocabulary_research",
                           confidence=1.0)

        # --- Brand-as-generic pairs: create Brand nodes + made_by edges ---
        for brand_name, generic in BRAND_GENERIC_PAIRS_RAW:
            brand_slug = _slugify(brand_name)
            brand_id = f"brand:{brand_slug}"

            if brand_id not in brands_added:
                self._add_node(brand_id, {
                    "id": brand_id,
                    "node_type": "brand",
                    "name": brand_name.title(),
                    "country": "",
                    "provenance": {
                        "source": "vocabulary_research",
                        "confidence": 0.9,
                        "source_id": "",
                        "added_date": TODAY,
                    },
                })
                brands_added.add(brand_id)

            # Ensure part node exists for the generic term
            part_slug = _slugify(generic)
            part_id = f"part:{part_slug}"
            self._add_node(part_id, {
                "id": part_id,
                "node_type": "part",
                "name": generic.title(),
                "aliases": [],
                "hsn_code": "",
                "part_numbers": [],
                "provenance": {
                    "source": "vocabulary_research",
                    "confidence": 0.9,
                    "source_id": "",
                    "added_date": TODAY,
                },
            })

            # Part made_by Brand
            self._add_edge(part_id, brand_id, "made_by", "vocabulary_research",
                           confidence=0.9)

        logger.info("Vocabulary: %d alias nodes, %d brand nodes",
                     len(aliases_added), len(brands_added))

    # ------------------------------------------------------------------
    # Deduplicate edges
    # ------------------------------------------------------------------
    def _dedupe_edges(self):
        """Remove duplicate edges (same source_id, target_id, edge_type)."""
        seen = set()
        deduped = []
        for edge in self.edges:
            key = (edge["source_id"], edge["target_id"], edge["edge_type"])
            if key not in seen:
                seen.add(key)
                deduped.append(edge)
        self.edges = deduped

    # ------------------------------------------------------------------
    # Build and export
    # ------------------------------------------------------------------
    def build(self) -> dict:
        """Return the final graph as a dict matching schema.json."""
        self._dedupe_edges()

        sources_used = set()
        for node in self.nodes.values():
            sources_used.add(node["provenance"]["source"])
        for edge in self.edges:
            sources_used.add(edge["source"])

        return {
            "metadata": {
                "version": "1.0",
                "created_date": TODAY,
                "sources": sorted(sources_used),
            },
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }


def build_knowledge_graph() -> dict:
    """Main entry point: ingest all sources and return the graph."""
    builder = GraphBuilder()

    hsn_path = KNOWLEDGE_GRAPH_DIR / "hsn_taxonomy.json"
    iti_path = KNOWLEDGE_GRAPH_DIR / "iti_diagnostics.json"
    iti_systems_v2 = KNOWLEDGE_GRAPH_DIR / "iti_systems_v2.json"
    iti_diagnostics_v2 = KNOWLEDGE_GRAPH_DIR / "iti_diagnostics_v2.json"
    iti_aliases_v2 = KNOWLEDGE_GRAPH_DIR / "iti_aliases_v2.json"
    nhtsa_path = KNOWLEDGE_GRAPH_DIR / "nhtsa_recalls.json"
    asdc_path = KNOWLEDGE_GRAPH_DIR / "asdc_tasks.json"

    if hsn_path.exists():
        builder.ingest_hsn(hsn_path)
    else:
        logger.warning("Missing %s", hsn_path)

    # Prefer ITI v2 (merged hand-curated + LLM-extracted with provenance) per ADR 008.
    # Fall back to v1 only if v2 files are missing.
    if iti_systems_v2.exists() and iti_diagnostics_v2.exists():
        builder.ingest_iti_v2(iti_systems_v2, iti_diagnostics_v2, iti_aliases_v2)
    elif iti_path.exists():
        logger.warning("ITI v2 files missing; falling back to v1 %s", iti_path)
        builder.ingest_iti(iti_path)
    else:
        logger.warning("Missing %s (no v1 or v2 ITI files)", iti_path)

    if nhtsa_path.exists():
        builder.ingest_nhtsa(nhtsa_path)
    else:
        logger.warning("Missing %s", nhtsa_path)

    if asdc_path.exists():
        builder.ingest_asdc(asdc_path)
    else:
        logger.warning("Missing %s", asdc_path)

    # Vocabulary research (always available — hardcoded in training/vocabulary_pairs.py)
    builder.ingest_vocabulary()

    graph = builder.build()

    # Stats
    from collections import Counter
    type_counts = Counter(n["node_type"] for n in graph["nodes"])
    edge_type_counts = Counter(e["edge_type"] for e in graph["edges"])

    logger.info("--- Graph Summary ---")
    logger.info("Total nodes: %d", len(graph["nodes"]))
    for t, c in type_counts.most_common():
        logger.info("  %s: %d", t, c)
    logger.info("Total edges: %d", len(graph["edges"]))
    for t, c in edge_type_counts.most_common():
        logger.info("  %s: %d", t, c)
    logger.info("Sources: %s", ", ".join(graph["metadata"]["sources"]))

    return graph


def save_graph(graph: dict, path: Path):
    """Write graph to JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (%d nodes, %d edges)", path, len(graph["nodes"]), len(graph["edges"]))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    graph = build_knowledge_graph()
    output = KNOWLEDGE_GRAPH_DIR / "graph.json"
    save_graph(graph, output)

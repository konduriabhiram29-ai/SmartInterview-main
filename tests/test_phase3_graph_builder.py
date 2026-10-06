"""
SmartInterview — Phase 3 Tests: Graph Construction & Pipeline Validation

Tests that verify:
  1. Pipeline components in graph_builder.py (Stage A, Stage B, dedup, dry-run)
  2. The generated graph artefact (data/graph_data.json) schema and contents
  3. Node integrity: all 4 node types (Domain, Concept, Chunk, Skill)
  4. Edge integrity: CONTAINS, HAS_CHUNK, MAPS_TO, PREREQUISITE_OF, RELATED_TO
  5. Strict evidence requirements: every LLM-derived edge has text quotes and confidence
  6. Topological invariants: no dangling edge endpoints, no self-loops, no orphan concepts
"""

import os
import sys
import json
import pytest
from typing import Dict, Set

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.graph_schema import (
    NodeType,
    RelationType,
    DerivationStrategy,
    CANONICAL_DOMAIN_CATALOGUE,
    CANONICAL_CONCEPT_CATALOGUE,
)
from app.rag.graph_builder import (
    build_metadata_edges,
    build_skill_maps,
    deduplicate_edges,
    build_graph,
    GraphEdgeRecord,
    GraphNode,
    _processed_dir,
    _output_path,
)


@pytest.fixture(scope="module")
def graph_data():
    """Load the built graph_data.json file."""
    path = _output_path()
    assert os.path.exists(path), f"Graph data file does not exist at {path}. Run graph_builder first."
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# ── Pipeline Unit Tests ───────────────────────────────────────────────

class TestGraphPipelineUnits:
    def test_processed_dir_exists(self):
        proc_dir = _processed_dir()
        assert os.path.isdir(proc_dir), f"Processed dir not found: {proc_dir}"

    def test_stage_a_metadata_edges(self):
        proc_dir = _processed_dir()
        nodes, edges = build_metadata_edges(proc_dir)
        # 8 domains + 50 concepts + 402 chunks = 460
        assert len(nodes) == 460
        # 50 CONTAINS + 402 HAS_CHUNK = 452
        assert len(edges) == 452

        # Verify edge types
        contains_edges = [e for e in edges if e.relation == "CONTAINS"]
        has_chunk_edges = [e for e in edges if e.relation == "HAS_CHUNK"]
        assert len(contains_edges) == 50
        assert len(has_chunk_edges) == 402

        # All metadata derivation
        assert all(e.derivation == "metadata" for e in edges)
        assert all(e.confidence == 1.0 for e in edges)

    def test_stage_a_skill_maps(self):
        nodes, edges = build_skill_maps()
        assert len(nodes) == 69  # 69 unique skills
        assert len(edges) == 117  # 117 MAPS_TO edges
        assert all(n.type == "Skill" for n in nodes)
        assert all(e.relation == "MAPS_TO" for e in edges)

    def test_deduplicate_edges(self):
        e1 = GraphEdgeRecord(source_id="A", target_id="B", relation="RELATED_TO", derivation="metadata", evidence="rule 1", confidence=0.8)
        e2 = GraphEdgeRecord(source_id="A", target_id="B", relation="RELATED_TO", derivation="llm", evidence="quote 2", confidence=0.95)
        e3 = GraphEdgeRecord(source_id="B", target_id="C", relation="CONTAINS", derivation="metadata", evidence="rule 3", confidence=1.0)
        deduped = deduplicate_edges([e1, e2, e3])
        assert len(deduped) == 2
        # Preserved the one with confidence 0.95
        ab = next(e for e in deduped if e.source_id == "A" and e.target_id == "B")
        assert ab.confidence == 0.95

    def test_dry_run_pipeline_execution(self, tmp_path):
        tmp_out = str(tmp_path / "test_graph.json")
        result = build_graph(dry_run=True, output_path=tmp_out)
        assert os.path.exists(tmp_out)
        assert result["stats"]["total_nodes"] == 529
        assert result["stats"]["edge_by_derivation"]["metadata"] == 569
        assert result["build_meta"]["dry_run"] is True


# ── Generated Graph Artefact Tests ────────────────────────────────────

class TestGraphArtefactValidation:
    def test_graph_data_top_level_structure(self, graph_data):
        assert "nodes" in graph_data
        assert "edges" in graph_data
        assert "stats" in graph_data
        assert "build_meta" in graph_data

    def test_node_counts_and_types(self, graph_data):
        nodes = graph_data["nodes"]
        stats = graph_data["stats"]
        assert len(nodes) == 529
        assert stats["total_nodes"] == 529

        node_types = stats["node_types"]
        assert node_types["Domain"] == 8
        assert node_types["Concept"] == 50
        assert node_types["KnowledgeChunk"] == 402
        assert node_types["Skill"] == 69

    def test_canonical_domains_present(self, graph_data):
        domain_nodes = [n for n in graph_data["nodes"] if n["type"] == "Domain"]
        assert len(domain_nodes) == 8
        domain_ids = {d["id"] for d in domain_nodes}
        expected_ids = {d.id for d in CANONICAL_DOMAIN_CATALOGUE}
        assert domain_ids == expected_ids

    def test_canonical_concepts_present(self, graph_data):
        concept_nodes = [n for n in graph_data["nodes"] if n["type"] == "Concept"]
        assert len(concept_nodes) == 50
        concept_ids = {c["id"] for c in concept_nodes}
        expected_ids = {c.id for c in CANONICAL_CONCEPT_CATALOGUE}
        assert concept_ids == expected_ids

    def test_edge_counts_and_types(self, graph_data):
        edges = graph_data["edges"]
        stats = graph_data["stats"]
        assert len(edges) == stats["total_edges"]
        assert len(edges) >= 569

        edge_types = stats["edge_types"]
        assert edge_types["CONTAINS"] == 50
        assert edge_types["HAS_CHUNK"] == 402
        assert edge_types["MAPS_TO"] == 117
        assert edge_types.get("PREREQUISITE_OF", 0) > 0
        assert edge_types.get("RELATED_TO", 0) > 0

    def test_no_orphan_concepts(self, graph_data):
        # Every concept must have an incoming CONTAINS edge from its domain
        concept_ids = {n["id"] for n in graph_data["nodes"] if n["type"] == "Concept"}
        contained_targets = {
            e["target_id"] for e in graph_data["edges"]
            if e["relation"] == "CONTAINS"
        }
        assert concept_ids == contained_targets

    def test_no_orphan_chunks(self, graph_data):
        # Every chunk must have an incoming HAS_CHUNK edge from a concept
        chunk_ids = {n["id"] for n in graph_data["nodes"] if n["type"] == "KnowledgeChunk"}
        chunk_targets = {
            e["target_id"] for e in graph_data["edges"]
            if e["relation"] == "HAS_CHUNK"
        }
        assert chunk_ids == chunk_targets

    def test_no_dangling_edge_endpoints(self, graph_data):
        # Every edge source and target must exist in the node set
        all_node_ids = {n["id"] for n in graph_data["nodes"]}
        for e in graph_data["edges"]:
            assert e["source_id"] in all_node_ids, f"Dangling source: {e['source_id']}"
            assert e["target_id"] in all_node_ids, f"Dangling target: {e['target_id']}"

    def test_no_self_loops(self, graph_data):
        for e in graph_data["edges"]:
            assert e["source_id"] != e["target_id"], f"Self-loop detected: {e}"

    def test_valid_relations_and_derivations(self, graph_data):
        valid_relations = {r.value for r in RelationType}
        valid_derivations = {d.value for d in DerivationStrategy}
        for e in graph_data["edges"]:
            assert e["relation"] in valid_relations, f"Invalid relation: {e['relation']}"
            assert e["derivation"] in valid_derivations, f"Invalid derivation: {e['derivation']}"

    def test_llm_edges_have_mandatory_evidence_and_confidence(self, graph_data):
        llm_edges = [e for e in graph_data["edges"] if e["derivation"] == "llm"]
        assert len(llm_edges) > 0, "No LLM edges found in graph artefact"
        for e in llm_edges:
            assert isinstance(e["evidence"], str) and len(e["evidence"].strip()) > 0, (
                f"Missing evidence for LLM edge: {e['source_id']} -> {e['target_id']}"
            )
            assert 0.0 < e["confidence"] <= 1.0, (
                f"Confidence out of range for LLM edge: {e['confidence']}"
            )

    def test_prerequisite_edges_are_between_concepts(self, graph_data):
        concept_ids = {n["id"] for n in graph_data["nodes"] if n["type"] == "Concept"}
        prereq_edges = [e for e in graph_data["edges"] if e["relation"] == "PREREQUISITE_OF"]
        assert len(prereq_edges) >= 5, "Expected at least 5 confirmed prerequisites"
        for e in prereq_edges:
            assert e["source_id"] in concept_ids
            assert e["target_id"] in concept_ids
            # Must have non-empty evidence
            assert len(e["evidence"].strip()) > 0

    def test_related_edges_are_between_concepts(self, graph_data):
        concept_ids = {n["id"] for n in graph_data["nodes"] if n["type"] == "Concept"}
        related_edges = [e for e in graph_data["edges"] if e["relation"] == "RELATED_TO"]
        assert len(related_edges) >= 6, "Expected confirmed related edges"
        for e in related_edges:
            assert e["source_id"] in concept_ids
            assert e["target_id"] in concept_ids
            assert len(e["evidence"].strip()) > 0

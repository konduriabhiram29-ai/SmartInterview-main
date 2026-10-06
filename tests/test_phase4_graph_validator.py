"""
SmartInterview — Phase 4 Tests: Knowledge Graph Validation Engine

Tests that verify:
  1. The canonical graph (data/graph_data.json) passes all validation checks with zero errors.
  2. The validator correctly catches synthetic edge and node corruptions:
     - Duplicate node IDs
     - Duplicate edge triples
     - Self-referencing edges (self loops)
     - Dangling edge endpoints
     - Unsupported node and relationship types
     - Missing evidence quotes on LLM edges
     - Invalid confidence values
     - Orphan concepts and orphan chunks
     - Domain mismatches between chunks and concepts
     - Cyclic prerequisite dependencies (cycle detection in DAG)
  3. Report formatting and serialization.
"""

import os
import sys
import copy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.graph_validator import (
    validate_graph,
    validate_graph_file,
    check_node_uniqueness,
    check_edge_uniqueness,
    check_no_self_loops,
    check_endpoints_exist,
    check_relationship_types_and_derivations,
    check_evidence_requirements,
    check_domain_consistency,
    check_orphan_concepts,
    check_orphan_chunks,
    check_prerequisite_acyclicity,
)
from app.rag.graph_builder import _output_path


@pytest.fixture(scope="module")
def canonical_graph():
    """Load the built graph_data.json file."""
    path = _output_path()
    assert os.path.exists(path), f"Graph data file does not exist at {path}"
    with open(path, "r", encoding="utf-8") as f:
        import json
        return json.load(f)


# ── Canonical Graph Validation ────────────────────────────────────────

class TestCanonicalGraphIntegrity:
    def test_canonical_graph_passes_validation(self):
        report = validate_graph_file()
        assert report.is_valid is True, f"Graph validation failed: {report.issues}"
        assert report.error_count == 0
        assert len(report.invalid_edges) == 0
        assert len(report.orphan_concepts) == 0
        assert len(report.orphan_chunks) == 0
        assert report.prerequisite_acyclic is True

    def test_canonical_graph_counts(self, canonical_graph):
        report = validate_graph(canonical_graph)
        assert report.total_nodes == 529
        assert report.total_edges == 591
        assert report.node_types["Domain"] == 8
        assert report.node_types["Concept"] == 50
        assert report.node_types["KnowledgeChunk"] == 402
        assert report.node_types["Skill"] == 69
        assert report.edge_types["CONTAINS"] == 50
        assert report.edge_types["HAS_CHUNK"] == 402
        assert report.edge_types["MAPS_TO"] == 117
        assert report.edge_types["PREREQUISITE_OF"] == 10
        assert report.edge_types["RELATED_TO"] == 12

    def test_report_formatting_and_dict(self, canonical_graph):
        report = validate_graph(canonical_graph)
        text = report.format_text_report()
        assert "SMARTINTERVIEW" in text
        assert "Total nodes" in text
        assert "Status: PASS (VALID GRAPH)" in text

        d = report.to_dict()
        assert d["is_valid"] is True
        assert d["total_nodes"] == 529
        assert d["total_edges"] == 591
        assert d["error_count"] == 0


# ── Synthetic Defect Detection Unit Tests ─────────────────────────────

class TestDefectDetection:
    def test_duplicate_node_id_detected(self):
        nodes = [
            {"id": "dsa_tree", "type": "Concept"},
            {"id": "dsa_tree", "type": "Concept"},
        ]
        _, issues = check_node_uniqueness(nodes)
        assert len(issues) == 1
        assert issues[0].severity == "ERROR"
        assert "Duplicate node ID" in issues[0].message

    def test_duplicate_edge_detected(self):
        edges = [
            {"source_id": "A", "target_id": "B", "relation": "RELATED_TO"},
            {"source_id": "A", "target_id": "B", "relation": "RELATED_TO"},
        ]
        issues = check_edge_uniqueness(edges)
        assert len(issues) == 1
        assert issues[0].severity == "ERROR"
        assert "Duplicate edge" in issues[0].message

    def test_self_loop_detected(self):
        edges = [
            {"source_id": "concept_a", "target_id": "concept_a", "relation": "RELATED_TO"}
        ]
        invalid, issues = check_no_self_loops(edges)
        assert len(invalid) == 1
        assert len(issues) == 1
        assert "Self-referencing" in issues[0].message

    def test_dangling_endpoints_detected(self):
        nodes_map = {"valid_node": {"id": "valid_node", "type": "Concept"}}
        edges = [
            {"source_id": "valid_node", "target_id": "missing_node", "relation": "RELATED_TO"},
            {"source_id": "unknown_src", "target_id": "valid_node", "relation": "RELATED_TO"},
        ]
        invalid, issues = check_endpoints_exist(nodes_map, edges)
        assert len(invalid) == 2
        assert len(issues) == 2

    def test_invalid_relationship_type_detected(self):
        edges = [
            {"source_id": "A", "target_id": "B", "relation": "FAVORITE_OF", "derivation": "metadata"}
        ]
        _, _, issues = check_relationship_types_and_derivations(edges)
        assert any("Invalid relation type" in i.message for i in issues)

    def test_missing_evidence_on_llm_edge_detected(self):
        edges = [
            {
                "source_id": "A",
                "target_id": "B",
                "relation": "PREREQUISITE_OF",
                "derivation": "llm",
                "evidence": "",  # missing evidence
                "confidence": 0.9,
            }
        ]
        issues = check_evidence_requirements(edges)
        assert any("lacks mandatory evidence" in i.message for i in issues)

    def test_invalid_confidence_detected(self):
        edges = [
            {
                "source_id": "A",
                "target_id": "B",
                "relation": "PREREQUISITE_OF",
                "derivation": "llm",
                "evidence": "some quote",
                "confidence": 1.5,  # out of range
            }
        ]
        issues = check_evidence_requirements(edges)
        assert any("out of valid range" in i.message for i in issues)

    def test_orphan_concept_detected(self):
        nodes_map = {
            "c1": {"id": "c1", "type": "Concept"},
            "c2": {"id": "c2", "type": "Concept"},  # orphan
        }
        edges = [
            {"source_id": "domain_a", "target_id": "c1", "relation": "CONTAINS"}
        ]
        orphans, issues = check_orphan_concepts(nodes_map, edges)
        assert orphans == ["c2"]
        assert len(issues) == 1
        assert "orphaned" in issues[0].message

    def test_orphan_chunk_detected(self):
        nodes_map = {
            "ch1": {"id": "ch1", "type": "KnowledgeChunk"},
            "ch2": {"id": "ch2", "type": "KnowledgeChunk"},  # orphan
        }
        edges = [
            {"source_id": "concept_a", "target_id": "ch1", "relation": "HAS_CHUNK"}
        ]
        orphans, issues = check_orphan_chunks(nodes_map, edges)
        assert orphans == ["ch2"]
        assert len(issues) == 1
        assert "orphaned" in issues[0].message

    def test_domain_mismatch_detected(self):
        nodes_map = {
            "chunk_1": {
                "id": "chunk_1",
                "type": "KnowledgeChunk",
                "properties": {"domain_id": "os"},  # mismatch
            }
        }
        edges = [
            {"source_id": "dsa", "target_id": "dsa_tree", "relation": "CONTAINS"},
            {"source_id": "dsa_tree", "target_id": "chunk_1", "relation": "HAS_CHUNK"},
        ]
        issues = check_domain_consistency(nodes_map, edges)
        assert any("Chunk 'chunk_1' has domain 'os'" in i.message for i in issues)

    def test_prerequisite_cycle_detected(self):
        # A -> B -> C -> A (cycle!)
        edges = [
            {"source_id": "A", "target_id": "B", "relation": "PREREQUISITE_OF"},
            {"source_id": "B", "target_id": "C", "relation": "PREREQUISITE_OF"},
            {"source_id": "C", "target_id": "A", "relation": "PREREQUISITE_OF"},
        ]
        is_acyclic, issues = check_prerequisite_acyclicity(edges)
        assert is_acyclic is False
        assert len(issues) >= 1
        assert "Cycle detected" in issues[0].message

    def test_prerequisite_dag_valid(self):
        # A -> B, A -> C, B -> D, C -> D (diamond DAG, valid!)
        edges = [
            {"source_id": "A", "target_id": "B", "relation": "PREREQUISITE_OF"},
            {"source_id": "A", "target_id": "C", "relation": "PREREQUISITE_OF"},
            {"source_id": "B", "target_id": "D", "relation": "PREREQUISITE_OF"},
            {"source_id": "C", "target_id": "D", "relation": "PREREQUISITE_OF"},
        ]
        is_acyclic, issues = check_prerequisite_acyclicity(edges)
        assert is_acyclic is True
        assert len(issues) == 0

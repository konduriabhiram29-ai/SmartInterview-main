"""
SmartInterview — Phase 5 Tests: Knowledge Graph Storage & Query Layer

Tests that verify:
  1. BaseGraphStore abstract contract enforcement
  2. NetworkXGraphStore ingestion, indexing, and all graph query methods:
     - Domain and Concept lookups
     - KnowledgeChunk traversal via HAS_CHUNK
     - Prerequisite traversal via PREREQUISITE_OF
     - Dependent traversal via reverse PREREQUISITE_OF
     - Related concepts via bidirectional RELATED_TO
     - Domain concept filtering via CONTAINS
     - Skill-to-Concept resolution via Skill -> MAPS_TO -> Domain -> CONTAINS -> Concept
     - Ego subgraph extraction
     - Accurate graph statistics
  3. Neo4jGraphStore configuration and connection handling
  4. Factory resolution and automatic fallback logic
  5. End-to-end ingestion pipeline with pre-validation
"""

import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.graph_store import (
    BaseGraphStore,
    NetworkXGraphStore,
    Neo4jGraphStore,
    get_graph_store,
    reset_graph_store,
)
from app.rag.graph_ingestion import ingest_graph_pipeline
from app.rag.graph_builder import _output_path


@pytest.fixture(scope="module")
def graph_data():
    """Load canonical graph_data.json."""
    path = _output_path()
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def store(graph_data):
    """Clean NetworkX store loaded with canonical graph data."""
    s = NetworkXGraphStore()
    s.initialize_schema()
    s.ingest_graph(graph_data)
    return s


# ── Contract Tests ────────────────────────────────────────────────────

class TestBaseGraphStoreContract:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseGraphStore()  # type: ignore


# ── NetworkX Graph Store Query Tests ──────────────────────────────────

class TestNetworkXGraphStoreQueries:
    def test_stats_and_counts(self, store):
        stats = store.get_stats()
        assert stats["backend"] == "networkx"
        assert stats["total_nodes"] == 529
        assert stats["total_edges"] == 591
        assert stats["node_types"]["Domain"] == 8
        assert stats["node_types"]["Concept"] == 50
        assert stats["node_types"]["KnowledgeChunk"] == 402
        assert stats["node_types"]["Skill"] == 69

    def test_get_domain(self, store):
        domain = store.get_domain("dbms")
        assert domain is not None
        assert domain["id"] == "dbms"
        assert domain["display_name"] == "Database Management Systems"

        missing = store.get_domain("non_existent_domain")
        assert missing is None

    def test_get_concept(self, store):
        concept = store.get_concept("dbms_acid-properties")
        assert concept is not None
        assert concept["id"] == "dbms_acid-properties"
        assert concept["name"] == "acid-properties"
        assert concept["domain_id"] == "dbms"

        missing = store.get_concept("fake_concept")
        assert missing is None

    def test_get_chunks_for_concept(self, store):
        chunks = store.get_chunks_for_concept("dbms_acid-properties")
        assert len(chunks) == 8
        assert all(c["type"] == "KnowledgeChunk" for c in chunks)
        assert all(c["concept_id"] == "dbms_acid-properties" for c in chunks)

        # Empty for concept with no chunks
        assert store.get_chunks_for_concept("non_existent") == []

    def test_get_prerequisites(self, store):
        # We confirmed in Phase 3 that transactions is a prerequisite of acid-properties
        prereqs = store.get_prerequisites("dbms_acid-properties")
        assert len(prereqs) >= 1
        prereq_ids = [p["id"] for p in prereqs]
        assert "dbms_transactions" in prereq_ids

        # Check edge metadata preserved
        trans_node = next(p for p in prereqs if p["id"] == "dbms_transactions")
        assert "edge" in trans_node
        assert trans_node["edge"]["relation"] == "PREREQUISITE_OF"
        assert trans_node["edge"]["derivation"] == "llm"
        assert len(trans_node["edge"]["evidence"]) > 0
        assert trans_node["edge"]["confidence"] >= 0.80

    def test_get_dependents(self, store):
        # Inverse of prerequisite
        deps = store.get_dependents("dbms_transactions")
        dep_ids = [d["id"] for d in deps]
        assert "dbms_acid-properties" in dep_ids

        dep_node = next(d for d in deps if d["id"] == "dbms_acid-properties")
        assert dep_node["edge"]["relation"] == "PREREQUISITE_OF"

    def test_get_related_concepts(self, store):
        # Tree and Graph are related
        related_tree = store.get_related_concepts("dsa_tree")
        rel_ids = [r["id"] for r in related_tree]
        assert "dsa_graph" in rel_ids

        # Bidirectional check: Graph must also be related to Tree
        related_graph = store.get_related_concepts("dsa_graph")
        graph_rel_ids = [r["id"] for r in related_graph]
        assert "dsa_tree" in graph_rel_ids

    def test_get_concepts_by_domain(self, store):
        dbms_concepts = store.get_concepts_by_domain("dbms")
        assert len(dbms_concepts) == 6
        expected_names = {
            "acid-properties", "indexing", "keys", "normalization", "sql-joins", "transactions"
        }
        actual_names = {c["name"] for c in dbms_concepts}
        assert actual_names == expected_names

    def test_get_concepts_by_skill(self, store):
        # Python maps to DSA and ML/DL domains in generate_question.py
        py_concepts = store.get_concepts_by_skill("python")
        assert len(py_concepts) > 0
        py_concept_ids = {c["id"] for c in py_concepts}
        assert "dsa_array" in py_concept_ids
        assert "mldl_neural-networks" in py_concept_ids

        # SQL maps to DBMS
        sql_concepts = store.get_concepts_by_skill("sql")
        assert len(sql_concepts) == 6
        assert any(c["id"] == "dbms_indexing" for c in sql_concepts)

    def test_get_subgraph(self, store):
        subgraph = store.get_subgraph(
            concept_ids=["dbms_acid-properties", "dbms_transactions"],
            max_depth=1,
        )
        assert subgraph["node_count"] >= 2
        assert subgraph["edge_count"] >= 1
        node_ids = {n["id"] for n in subgraph["nodes"]}
        assert "dbms_acid-properties" in node_ids
        assert "dbms_transactions" in node_ids


# ── Neo4j Store Unit & Connection Tests ───────────────────────────────

class TestNeo4jGraphStore:
    def test_neo4j_initialization_with_env(self):
        store = Neo4jGraphStore(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="testpassword",
            database="neo4j",
        )
        assert store._uri == "bolt://localhost:7687"
        assert store._user == "neo4j"
        assert store._password == "testpassword"
        assert store._database == "neo4j"

    def test_neo4j_unreachable_probe_returns_false(self):
        # Non-existent port to test connection probe
        store = Neo4jGraphStore(uri="bolt://localhost:9999", password="")
        assert store.is_connected() is False

    def test_neo4j_session_cypher_mock(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        store = Neo4jGraphStore()
        store._driver = mock_driver

        # Test initialize_schema runs constraints
        store.initialize_schema()
        assert mock_session.run.call_count >= 4


# ── Store Factory & Ingestion Pipeline Tests ──────────────────────────

class TestStoreFactoryAndIngestion:
    def setup_method(self):
        reset_graph_store()

    def teardown_method(self):
        reset_graph_store()

    def test_factory_returns_networkx_by_default(self):
        store = get_graph_store(backend="networkx")
        assert isinstance(store, NetworkXGraphStore)
        assert store.get_stats()["total_nodes"] == 529

    def test_factory_auto_mode_falls_back_when_neo4j_absent(self):
        store = get_graph_store(backend="auto")
        assert isinstance(store, NetworkXGraphStore)
        assert store.get_stats()["total_nodes"] == 529

    def test_factory_neo4j_raises_when_unreachable(self):
        with pytest.raises(ConnectionError):
            get_graph_store(backend="neo4j")

    def test_end_to_end_ingestion_pipeline(self):
        result = ingest_graph_pipeline(backend="networkx", validate_first=True)
        assert result["status"] == "success"
        assert result["backend"] == "networkx"
        assert result["nodes_ingested"] == 529
        assert result["edges_ingested"] == 591

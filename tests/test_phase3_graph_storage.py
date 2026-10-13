"""
SmartInterview — Phase 3 Tests: Knowledge Graph Storage, Lifecycle & Resilience

Comprehensive test suite verifying:
  1. Fresh installation initialization from canonical source (data/processed).
  2. Schema verification & readiness guarantee before graph retrieval begins.
  3. Repeated ingestion idempotency without duplicate nodes or edges.
  4. Non-silent overwrite protection & backup creation.
  5. Atomic ingestion and exception-safe invalid data rejection.
  6. Service-unavailable / connection error handling for Neo4j.
  7. Graceful fallback in 'auto' mode without data loss.
  8. Environment variable credentials management.
"""

import os
import sys
import json
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.graph_store import (
    BaseGraphStore,
    NetworkXGraphStore,
    Neo4jGraphStore,
    GraphStorageError,
    GraphConnectionError,
    GraphValidationError,
    get_graph_store,
    ensure_graph_initialized,
    reset_graph_store,
)
from app.rag.graph_builder import _output_path, build_graph
from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE


@pytest.fixture(autouse=True)
def clean_store_singleton():
    """Ensure every test starts and ends with a clean singleton state."""
    reset_graph_store()
    yield
    reset_graph_store()


@pytest.fixture(scope="module")
def canonical_graph_data():
    path = _output_path()
    assert os.path.exists(path), f"Canonical graph data missing at {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 1. Initialization & Readiness Guarantees ───────────────────────────

class TestGraphInitializationAndReadiness:
    def test_ensure_graph_initialized_verifies_schema_and_counts(self):
        store = ensure_graph_initialized(backend="networkx")
        stats = store.get_stats()
        assert stats["backend"] == "networkx"
        assert stats["total_nodes"] == 529
        assert stats["total_edges"] == 591
        assert stats["node_types"]["Domain"] == 8
        assert stats["node_types"]["Concept"] == 50
        assert stats["node_types"]["KnowledgeChunk"] == 402

    def test_fresh_install_initialization_from_canonical_processed(self, tmp_path):
        """
        Simulate a fresh installation where graph_data.json does not exist.
        The storage loader should rebuild deterministically from data/processed.
        """
        isolated_graph_file = str(tmp_path / "fresh_graph_data.json")
        assert not os.path.exists(isolated_graph_file)

        store = get_graph_store(backend="networkx", graph_data_path=isolated_graph_file)
        assert os.path.exists(isolated_graph_file)
        stats = store.get_stats()
        assert stats["total_nodes"] == 529
        assert stats["total_edges"] >= 540


# ── 2. Ingestion Idempotency ───────────────────────────────────────────

class TestIngestionIdempotence:
    def test_repeated_networkx_ingestion_is_idempotent(self, canonical_graph_data):
        store = NetworkXGraphStore()
        store.initialize_schema()

        # Ingest once
        stats1 = store.ingest_graph(canonical_graph_data)
        assert stats1["nodes_ingested"] == 529
        assert stats1["edges_ingested"] == 591

        # Ingest again
        stats2 = store.ingest_graph(canonical_graph_data)
        assert stats2["nodes_ingested"] == 529
        assert stats2["edges_ingested"] == 591

        # Check total counts remained identical
        stats = store.get_stats()
        assert stats["total_nodes"] == 529
        assert stats["total_edges"] == 591
        assert len(store.get_concepts_by_domain("dbms")) == 6
        assert len(store.get_chunks_for_concept("dbms_acid-properties")) == 8


# ── 3. Data Protection & Non-Silent Overwrite ──────────────────────────

class TestDataProtectionAndPersistence:
    def test_graph_builder_preserves_backup_on_rebuild(self, tmp_path):
        target = str(tmp_path / "test_graph.json")
        # Build first version
        build_graph(dry_run=True, output_path=target)
        assert os.path.exists(target)

        # Modify first version so we can verify backup content
        with open(target, "r", encoding="utf-8") as f:
            v1_data = json.load(f)
        v1_data["sentinel_marker"] = "version_1"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(v1_data, f)

        # Build second version
        build_graph(dry_run=True, output_path=target, allow_overwrite=True)
        backup_file = f"{target}.bak"
        assert os.path.exists(backup_file), "Backup file was not created"

        with open(backup_file, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        assert backup_data.get("sentinel_marker") == "version_1"

    def test_graph_builder_rejects_overwrite_when_disallowed(self, tmp_path):
        target = str(tmp_path / "test_graph_protected.json")
        build_graph(dry_run=True, output_path=target)

        with pytest.raises(FileExistsError):
            build_graph(dry_run=True, output_path=target, allow_overwrite=False)


# ── 4. Invalid Data & Exception Safety ─────────────────────────────────

class TestInvalidDataAndExceptionSafety:
    def test_ingest_non_dict_raises_validation_error(self):
        store = NetworkXGraphStore()
        with pytest.raises(GraphValidationError):
            store.ingest_graph(["not", "a", "dict"])

    def test_ingest_missing_keys_raises_validation_error(self):
        store = NetworkXGraphStore()
        with pytest.raises(GraphValidationError):
            store.ingest_graph({"nodes": []})  # missing 'edges'

    def test_atomic_rollback_on_malformed_node(self, canonical_graph_data):
        store = NetworkXGraphStore()
        store.ingest_graph(canonical_graph_data)
        initial_stats = store.get_stats()
        assert initial_stats["total_nodes"] == 529

        # Corrupt one node in payload
        bad_payload = {
            "nodes": [{"missing_id_key": "bad"}],
            "edges": [],
        }

        with pytest.raises(GraphValidationError):
            store.ingest_graph(bad_payload)

        # Existing valid graph is untouched
        post_stats = store.get_stats()
        assert post_stats["total_nodes"] == 529
        assert post_stats["total_edges"] == 591

    def test_corrupted_json_file_raises_storage_error(self, tmp_path):
        corrupt_file = str(tmp_path / "corrupt_graph.json")
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json content ...")

        with pytest.raises(GraphStorageError):
            get_graph_store(backend="networkx", graph_data_path=corrupt_file)


# ── 5. Backend Resilience & Service Unavailable ───────────────────────

class TestBackendResilienceAndFallback:
    def test_explicit_neo4j_raises_graph_connection_error_when_offline(self):
        with pytest.raises(GraphConnectionError):
            get_graph_store(backend="neo4j")

    def test_auto_backend_gracefully_falls_back_without_data_loss(self):
        """
        When Neo4j is offline, auto mode falls back to NetworkX
        and retains all 529 nodes and 591 edges.
        """
        store = get_graph_store(backend="auto")
        assert isinstance(store, NetworkXGraphStore)
        stats = store.get_stats()
        assert stats["backend"] == "networkx"
        assert stats["total_nodes"] == 529
        assert stats["total_edges"] == 591

    def test_provenance_attributes_preserved_in_edge_traversal(self, canonical_graph_data):
        store = NetworkXGraphStore()
        store.ingest_graph(canonical_graph_data)

        # Test prerequisite traversal preserves provenance fields
        prereqs = store.get_prerequisites("dbms_acid-properties")
        assert len(prereqs) > 0
        edge_data = prereqs[0]["edge"]
        assert "confidence" in edge_data
        assert "derivation" in edge_data
        assert "validation_status" in edge_data
        assert edge_data["validation_status"] in ("VALIDATED", "validated")


# ── 6. Environment Credentials Check ───────────────────────────────────

class TestConfigurationIntegrity:
    def test_neo4j_credentials_match_env_config(self):
        store = Neo4jGraphStore()
        assert store._uri == NEO4J_URI
        assert store._user == NEO4J_USER
        assert store._password == NEO4J_PASSWORD
        assert store._database == NEO4J_DATABASE

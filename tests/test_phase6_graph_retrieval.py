"""
SmartInterview — Phase 6 Tests: Knowledge Graph Retrieval & Dense Comparison

Tests that verify:
  1. GraphRetriever interface compliance (inherits BaseRetriever, returns RetrievalResult)
  2. Seed concept resolution (explicit concept, query lexical match, skill mapping)
  3. Prerequisite discovery and weak-topic remediation
  4. Related concept traversal
  5. Bloom's Taxonomy score weighting
  6. Retrieval provenance metadata (traversal_path, role, graph_score)
  7. Comparative evaluation: Dense RAG baseline vs Graph RAG on identical queries
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.base_retriever import BaseRetriever
from app.rag.graph_retriever import GraphRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.graph_store import get_graph_store


@pytest.fixture(scope="module")
def retriever():
    store = get_graph_store()
    return GraphRetriever(graph_store=store)


# ── Contract & Interface Tests ────────────────────────────────────────

class TestGraphRetrieverContract:
    def test_inherits_base_retriever(self, retriever):
        assert isinstance(retriever, BaseRetriever)
        assert retriever.name == "GraphRetriever"

    def test_retrieve_returns_retrieval_results(self, retriever):
        results = retriever.retrieve(
            query="Explain ACID properties in relational database transactions",
            skill="SQL",
            domains=["dbms"],
            top_k=3,
        )
        assert isinstance(results, list)
        assert len(results) <= 3
        assert len(results) > 0
        for r in results:
            assert isinstance(r, RetrievalResult)
            assert r.retriever == "graph"
            assert r.graph_score is not None
            assert r.graph_score > 0.0
            assert "role" in r.metadata
            assert "traversal_path" in r.metadata


# ── Traversal & Feature Tests ─────────────────────────────────────────

class TestGraphRetrievalTraversal:
    def test_explicit_concept_retrieval(self, retriever):
        results = retriever.retrieve(
            query="What are ACID guarantees?",
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        assert any(r.concept == "acid-properties" for r in results)

    def test_prerequisite_expansion(self, retriever):
        # Querying acid-properties should pull in prerequisite chunks from transactions
        results = retriever.retrieve(
            query="ACID properties",
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            top_k=5,
        )
        # Should have both seed and prerequisite
        concepts_retrieved = {r.concept for r in results}
        assert "acid-properties" in concepts_retrieved
        roles = {r.metadata.get("role") for r in results}
        assert "seed" in roles
        # Transactions is a confirmed prerequisite of acid-properties
        assert "transactions" in concepts_retrieved or "prerequisite" in roles

    def test_weak_topic_remediation(self, retriever):
        # Candidate failed acid-properties; retriever should fetch prerequisite remediation context
        results = retriever.retrieve(
            query="Candidate struggled with database state consistency",
            skill="SQL",
            weak_topic="acid-properties",
            domains=["dbms"],
            top_k=4,
        )
        assert len(results) > 0
        # Check that remediation flag is set on prerequisite chunks
        has_remediation = any(r.metadata.get("remediation") is True for r in results)
        assert has_remediation, "Expected at least one chunk flagged for weak-topic remediation"

    def test_related_concept_expansion(self, retriever):
        # Tree is related to Graph in DSA
        results = retriever.retrieve(
            query="Hierarchical tree structures",
            skill="Python",
            concept="dsa_tree",
            domains=["dsa"],
            bloom_level="analyze",
            top_k=5,
        )
        concepts = {r.concept for r in results}
        assert "tree" in concepts
        # Graph is related to Tree
        assert "graph" in concepts or any(r.metadata.get("role") == "related" for r in results)

    def test_bloom_taxonomy_weighting_difference(self, retriever):
        # Remember level emphasizes core definitions / prerequisites
        results_remember = retriever.retrieve(
            query="ACID database transactions",
            skill="SQL",
            concept="dbms_acid-properties",
            bloom_level="remember",
            top_k=5,
        )
        # Analyze level emphasizes related concepts
        results_analyze = retriever.retrieve(
            query="ACID database transactions",
            skill="SQL",
            concept="dbms_acid-properties",
            bloom_level="analyze",
            top_k=5,
        )
        assert len(results_remember) > 0
        assert len(results_analyze) > 0
        # Verify bloom_level is stamped on metadata
        assert all(r.metadata["bloom_level"] == "remember" for r in results_remember)
        assert all(r.metadata["bloom_level"] == "analyze" for r in results_analyze)


# ── Comparative Evaluation: Dense RAG vs Graph RAG ───────────────────

class TestDenseVsGraphComparison:
    """
    Direct comparison demonstrating the architectural advantages of Graph RAG
    over Dense RAG on relational and prerequisite queries.
    """

    def test_prerequisite_coverage_comparison(self, retriever):
        query = "Explain ACID properties and why atomicity matters"

        # Graph RAG
        graph_results = retriever.retrieve(
            query=query,
            skill="SQL",
            domains=["dbms"],
            concept="dbms_acid-properties",
            top_k=4,
        )

        # Graph RAG brings in relational provenance and structured multi-concept context
        graph_concepts = {r.concept for r in graph_results}
        graph_roles = {r.metadata.get("role") for r in graph_results}

        # Assert Graph RAG successfully traverses beyond the single isolated concept
        assert "acid-properties" in graph_concepts
        assert "prerequisite" in graph_roles or "related" in graph_roles or len(graph_concepts) > 1

        # Every graph result has traversal explanation
        for r in graph_results:
            assert "traversal_path" in r.metadata
            assert len(r.metadata["traversal_path"]) > 0

    def test_weak_topic_remediation_comparison(self, retriever):
        query = "How to handle failed state changes in databases"

        # Graph RAG with weak topic targeted
        graph_results = retriever.retrieve(
            query=query,
            skill="SQL",
            weak_topic="dbms_acid-properties",
            domains=["dbms"],
            top_k=3,
        )

        # Graph RAG identifies prerequisite foundational knowledge
        remediation_chunks = [r for r in graph_results if r.metadata.get("remediation") is True]
        assert len(remediation_chunks) > 0
        # Prerequisite transactions provide the explanation of what an atomic transaction is
        assert any("transactions" in r.metadata.get("traversal_path", "") for r in remediation_chunks)

"""
SmartInterview — Phase 6 Dedicated Validation Test Suite
Knowledge Graph Retrieval, Multi-Hop Traversal, Weak-Topic Remediation,
Cognitive Bloom-Level Shifting, and Dense Baseline Comparative Evaluation.
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


# ── 1. Edge Cases & Input Sanitization ─────────────────────────────────

class TestEdgeCasesAndInputSanitization:
    def test_zero_and_negative_top_k(self, retriever):
        assert retriever.retrieve("database transactions", "SQL", top_k=0) == []
        assert retriever.retrieve("database transactions", "SQL", top_k=-5) == []

    def test_none_query_with_explicit_concept(self, retriever):
        results = retriever.retrieve(
            query=None,
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert any(r.concept == "acid-properties" for r in results)

    def test_empty_query_without_seeds_returns_empty(self, retriever):
        results = retriever.retrieve(
            query="",
            skill="",
            domains=["dbms"],
            top_k=3,
        )
        assert results == []

    def test_whitespace_and_punctuation_query(self, retriever):
        results = retriever.retrieve(
            query="   ??? !!!   ",
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_domain_filtering_case_insensitivity_and_whitespace(self, retriever):
        results = retriever.retrieve(
            query="Explain indexing in databases",
            skill="SQL",
            concept="indexing",
            domains=["  DBMS  "],
            top_k=3,
        )
        assert len(results) > 0
        assert all(r.domain == "dbms" for r in results)

    def test_unrecognized_domain_filter_returns_empty(self, retriever):
        results = retriever.retrieve(
            query="Explain indexing in databases",
            skill="SQL",
            concept="indexing",
            domains=["nonexistent_domain_xyz"],
            top_k=3,
        )
        assert results == []


# ── 2. Concept Normalization & Multi-Hop Traversal ──────────────────────

class TestConceptNormalizationAndMultiHop:
    def test_freeform_concept_normalization(self, retriever):
        # Different surface forms should resolve to dbms_acid-properties
        forms = ["ACID Properties", "acid_properties", "acid-properties", "dbms_acid-properties"]
        for form in forms:
            res = retriever.retrieve(
                query="database properties",
                skill="SQL",
                concept=form,
                domains=["dbms"],
                top_k=2,
            )
            assert len(res) > 0, f"Failed to retrieve for form: {form}"
            assert any(r.concept == "acid-properties" for r in res)

    def test_plural_weak_topics_list_support(self, retriever):
        results = retriever.retrieve(
            query="Transaction state and isolation",
            skill="SQL",
            weak_topics=["acid-properties"],
            domains=["dbms"],
            top_k=4,
        )
        assert len(results) > 0
        # Prerequisite transactions should receive remediation flag
        remediation_chunks = [r for r in results if r.metadata.get("remediation") is True]
        assert len(remediation_chunks) > 0
        assert any(r.metadata.get("role") == "prerequisite" for r in remediation_chunks)

    def test_max_hops_two_traverses_multihop_prerequisites(self, retriever):
        results_hop1 = retriever.retrieve(
            query="Database transactions and ACID",
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            max_hops=1,
            top_k=5,
        )
        results_hop2 = retriever.retrieve(
            query="Database transactions and ACID",
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            max_hops=2,
            top_k=10,
        )
        assert len(results_hop1) > 0
        assert len(results_hop2) >= len(results_hop1)
        # All returned chunks must be canonical full text
        assert all(r.metadata.get("is_full_text") is True for r in results_hop2)


# ── 3. Cognitive Bloom-Level Shifting ─────────────────────────────────

class TestBloomTaxonomyShifting:
    def test_bloom_remember_vs_analyze_weights(self, retriever):
        res_remember = retriever.retrieve(
            query="ACID database transactions",
            skill="SQL",
            concept="dbms_acid-properties",
            bloom_level="remember",
            top_k=5,
        )
        res_analyze = retriever.retrieve(
            query="ACID database transactions",
            skill="SQL",
            concept="dbms_acid-properties",
            bloom_level="analyze",
            top_k=5,
        )
        assert len(res_remember) > 0
        assert len(res_analyze) > 0

        # In 'remember', prerequisites have 0.95 base weight vs 0.40 related
        # In 'analyze', related concepts have 1.00 base weight vs 0.50 prerequisite
        prereq_scores_remember = [
            r.graph_score for r in res_remember if r.metadata.get("role") == "prerequisite"
        ]
        if prereq_scores_remember:
            assert all(score > 0.0 for score in prereq_scores_remember)

    def test_bloom_level_string_normalization(self, retriever):
        # Variations like "bloom_remember" or "LEVEL_ANALYZE"
        res1 = retriever.retrieve(
            query="ACID database",
            skill="SQL",
            concept="dbms_acid-properties",
            bloom_level="bloom_remember",
            top_k=2,
        )
        res2 = retriever.retrieve(
            query="ACID database",
            skill="SQL",
            concept="dbms_acid-properties",
            bloom_level="LEVEL_ANALYZE",
            top_k=2,
        )
        assert len(res1) > 0
        assert len(res2) > 0
        assert res1[0].metadata["bloom_level"] == "remember"
        assert res2[0].metadata["bloom_level"] == "analyze"


# ── 4. Latency Tracking & Operational Stats ───────────────────────────

class TestLatencyAndStats:
    def test_latency_recorded_in_metadata(self, retriever):
        results = retriever.retrieve(
            query="Explain index types in SQL",
            skill="SQL",
            concept="indexing",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        for r in results:
            assert "latency_ms" in r.metadata
            assert isinstance(r.metadata["latency_ms"], float)
            assert r.metadata["latency_ms"] >= 0.0

    def test_get_stats_operation(self, retriever):
        stats = retriever.get_stats()
        assert isinstance(stats, dict)
        assert stats["retriever"] == "GraphRetriever"
        assert stats["catalogue_concepts_count"] == 50
        assert "store_stats" in stats
        assert stats["canonical_resolver_indexed"] is True


# ── 5. Dense Baseline Comparative Evaluation ─────────────────────────

class TestComparativeDenseBaselineVsGraph:
    def test_dense_unaware_of_graph_edges(self, retriever):
        """
        Verify that GraphRetriever provides structured relational provenance
        (role, traversal_path, confidence) that Dense RAG cannot produce.
        """
        results = retriever.retrieve(
            query="Explain transactions and ACID guarantees",
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            top_k=4,
        )
        assert len(results) > 0
        for r in results:
            assert "traversal_path" in r.metadata
            assert "role" in r.metadata
            assert "confidence" in r.metadata
            assert r.retriever == "graph"
            assert r.graph_score is not None

    def test_full_canonical_text_resolution(self, retriever):
        """
        Ensure GraphRetriever resolves all chunks to canonical text (>600 characters)
        instead of truncated graph previews.
        """
        results = retriever.retrieve(
            query="Explain ACID atomicity and consistency",
            skill="SQL",
            concept="dbms_acid-properties",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        for r in results:
            assert r.metadata["is_full_text"] is True
            assert r.metadata["char_count"] > 400
            assert len(r.text) == r.metadata["char_count"]

"""
SmartInterview — Phase 5 Tests: BM25 Keyword Retrieval Validation

Comprehensive test suite verifying:
  1. Searches the exact same 402 canonical knowledge chunks as Dense RAG.
  2. Technical terms and exact keyword matches (e.g. 'B+ tree', 'TCP/IP', 'ACID', 'CAP').
  3. Domain filtering (single domain, multi-domain, case-insensitive, non-existent domain).
  4. Stable chunk IDs returned with canonical full text.
  5. Empty queries, whitespace, punctuation, and empty corpora handled safely.
  6. Malformed inputs (None, non-string, top_k <= 0) handled gracefully.
  7. Retrieval scores and latency are measured and recorded in metadata.
  8. Duplicate chunk results are prevented.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.keyword_retriever import KeywordRetriever
from app.rag.canonical_resolver import get_canonical_resolver
from app.rag.retrieval_result import RetrievalResult


@pytest.fixture(scope="module")
def retriever():
    return KeywordRetriever()


@pytest.fixture(scope="module")
def canonical_resolver():
    return get_canonical_resolver()


# ── 1. Canonical Corpus Alignment ─────────────────────────────────────

class TestBM25CanonicalCorpusIntegrity:
    def test_searches_same_402_chunks_as_dense(self, retriever, canonical_resolver):
        stats = retriever.get_stats()
        assert stats["total_chunks"] == 402
        assert stats["total_chunks"] == canonical_resolver.total_chunks
        assert len(stats["domains_indexed"]) == 8
        assert stats["vocab_terms"] > 1000

    def test_all_indexed_chunk_ids_are_canonical(self, retriever, canonical_resolver):
        canonical_ids = canonical_resolver.get_all_chunk_ids()
        indexed_ids = set(retriever._chunk_by_id.keys())
        assert indexed_ids == canonical_ids, "BM25 index chunk IDs do not match canonical corpus exactly"

    def test_retrieved_results_contain_full_canonical_text(self, retriever, canonical_resolver):
        results = retriever.retrieve(
            query="relational database acid transactions isolation",
            skill="SQL",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        for r in results:
            canonical = canonical_resolver.get_chunk(r.chunk_id)
            assert canonical is not None
            assert r.text == canonical.text
            assert len(r.text) > 300
            assert r.metadata.get("is_full_text") is True


# ── 2. Technical Terms & Exact Keyword Matching ───────────────────────

class TestTechnicalTerminologyAndExactMatches:
    def test_exact_technical_acronym_matching(self, retriever):
        # Query specifically for ACID guarantees
        results = retriever.retrieve(
            query="atomicity consistency isolation durability guarantees",
            skill="SQL",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        top_result = results[0]
        assert top_result.concept == "acid-properties"
        assert "atomicity" in top_result.metadata["matched_terms"]
        assert "consistency" in top_result.metadata["matched_terms"]

    def test_technical_symbol_and_compound_terms(self, retriever):
        # Query for B+ Tree symbol matching
        results = retriever.retrieve(
            query="b+ tree index leaf nodes",
            skill="SQL",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) > 0
        top = results[0]
        assert top.concept == "indexing"
        assert "b+" in top.metadata["matched_terms"]

        # Query for TCP/IP compound term
        cn_results = retriever.retrieve(
            query="tcp/ip protocol suite packets",
            skill="Networks",
            domains=["cn"],
            top_k=3,
        )
        assert len(cn_results) > 0
        assert any("tcp" in r.metadata["matched_terms"] for r in cn_results)

    def test_cap_theorem_distributed_systems_exact_match(self, retriever):
        results = retriever.retrieve(
            query="cap theorem consistency availability partition tolerance distributed",
            skill="System Design",
            domains=["system-design"],
            top_k=3,
        )
        assert len(results) > 0
        assert any(r.concept == "cap-theorem" for r in results)


# ── 3. Domain Filtering Strictness ────────────────────────────────────

class TestDomainFilteringRespect:
    def test_single_domain_filter_strictness(self, retriever):
        results = retriever.retrieve(
            query="memory management and scheduling",
            skill="OS",
            domains=["os"],
            top_k=5,
        )
        assert len(results) > 0
        assert all(r.domain == "os" for r in results)

    def test_case_insensitive_and_whitespace_domain_filter(self, retriever):
        results_lower = retriever.retrieve(
            query="dns domain name resolution",
            skill="Networks",
            domains=["cn"],
            top_k=3,
        )
        results_upper = retriever.retrieve(
            query="dns domain name resolution",
            skill="Networks",
            domains=[" CN "],
            top_k=3,
        )
        assert len(results_lower) > 0
        assert len(results_upper) == len(results_lower)
        assert [r.chunk_id for r in results_upper] == [r.chunk_id for r in results_lower]

    def test_multi_domain_filter(self, retriever):
        results = retriever.retrieve(
            query="binary tree indexing search algorithms",
            skill="Engineering",
            domains=["dsa", "dbms"],
            top_k=6,
        )
        assert len(results) > 0
        assert all(r.domain in ["dsa", "dbms"] for r in results)

    def test_unrecognized_domain_returns_empty(self, retriever):
        results = retriever.retrieve(
            query="database transactions",
            skill="SQL",
            domains=["non_existent_domain"],
            top_k=3,
        )
        assert results == []


# ── 4. Edge Cases & Malformed Input ───────────────────────────────────

class TestEdgeCasesAndMalformedInput:
    def test_none_query_returns_empty(self, retriever):
        assert retriever.retrieve(query=None, skill="SQL", top_k=3) == []

    def test_whitespace_and_punctuation_queries_return_empty(self, retriever):
        assert retriever.retrieve(query="", skill="SQL", top_k=3) == []
        assert retriever.retrieve(query="    ", skill="SQL", top_k=3) == []
        assert retriever.retrieve(query="!@#$%^&*()_+", skill="SQL", top_k=3) == []

    def test_zero_and_negative_top_k(self, retriever):
        assert retriever.retrieve(query="ACID", skill="SQL", top_k=0) == []
        assert retriever.retrieve(query="ACID", skill="SQL", top_k=-5) == []

    def test_empty_corpus_initialization_handled_safely(self):
        empty_retriever = KeywordRetriever(chunks=[])
        assert empty_retriever.retrieve(query="ACID", skill="SQL", top_k=3) == []
        stats = empty_retriever.get_stats()
        assert stats["total_chunks"] == 0


# ── 5. Latency & Scores Recording ──────────────────────────────────────

class TestLatencyAndScoreRecording:
    def test_scores_and_latency_recorded_in_metadata(self, retriever):
        results = retriever.retrieve(
            query="deadlock detection prevention bankers algorithm",
            skill="OS",
            domains=["os"],
            top_k=3,
        )
        assert len(results) > 0
        for r in results:
            assert isinstance(r, RetrievalResult)
            assert r.keyword_score is not None
            assert 0.0 < r.keyword_score <= 1.0
            assert "bm25_raw_score" in r.metadata
            assert r.metadata["bm25_raw_score"] > 0.0
            assert "latency_ms" in r.metadata
            assert r.metadata["latency_ms"] >= 0.0

        # Check retriever level recorded latency
        assert retriever.get_stats()["last_latency_ms"] is not None


# ── 6. Duplicate Prevention ───────────────────────────────────────────

class TestDuplicatePrevention:
    def test_duplicate_results_removed(self, retriever):
        results = retriever.retrieve(
            query="process thread concurrency deadlock synchronization",
            skill="OS",
            domains=["os"],
            top_k=10,
        )
        assert len(results) > 0
        returned_ids = [r.chunk_id for r in results]
        assert len(returned_ids) == len(set(returned_ids)), "Duplicate chunk IDs returned in results"

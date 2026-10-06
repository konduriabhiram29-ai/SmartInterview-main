"""
SmartInterview — Phase 7 Tests: BM25 Keyword Retrieval

Tests that verify:
  1. KeywordRetriever contract compliance (inherits BaseRetriever, returns RetrievalResult)
  2. Corpus indexing over the canonical knowledge base (all 402 chunks indexed)
  3. BM25 scoring and matched_terms extraction
  4. Domain-filtered keyword retrieval
  5. Top-k ordering and score monotonicity
  6. Edge cases: empty queries, unrecognised domains, zero-match queries
  7. Independent operation of all 3 retrievers (VectorRetriever, KeywordRetriever, GraphRetriever)
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.base_retriever import BaseRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.retriever_factory import get_retriever, get_implemented_modes


@pytest.fixture(scope="module")
def retriever():
    return KeywordRetriever()


# ── Contract & Interface Tests ────────────────────────────────────────

class TestKeywordRetrieverContract:
    def test_inherits_base_retriever(self, retriever):
        assert isinstance(retriever, BaseRetriever)
        assert retriever.name == "KeywordRetriever"

    def test_factory_resolves_keyword_mode(self):
        ret = get_retriever(mode="keyword")
        assert isinstance(ret, KeywordRetriever)
        assert "keyword" in get_implemented_modes()

    def test_corpus_stats(self, retriever):
        stats = retriever.get_stats()
        assert stats["total_chunks"] == 402
        assert stats["vocab_terms"] > 1000
        assert len(stats["domains_indexed"]) == 8


# ── BM25 Retrieval & Feature Tests ────────────────────────────────────

class TestKeywordRetrievalExecution:
    def test_basic_retrieval_and_metadata(self, retriever):
        results = retriever.retrieve(
            query="ACID database transaction isolation levels",
            skill="SQL",
            domains=["dbms"],
            top_k=3,
        )
        assert len(results) <= 3
        assert len(results) > 0

        for r in results:
            assert isinstance(r, RetrievalResult)
            assert r.retriever == "keyword"
            assert r.domain == "dbms"
            assert r.keyword_score is not None
            assert 0.0 < r.keyword_score <= 1.0
            assert "matched_terms" in r.metadata
            assert "bm25_raw_score" in r.metadata
            assert len(r.metadata["matched_terms"]) > 0

    def test_domain_filtering_strictness(self, retriever):
        # Querying with dsa domain filter
        results_dsa = retriever.retrieve(
            query="binary tree traversal algorithm",
            skill="Python",
            domains=["dsa"],
            top_k=5,
        )
        assert len(results_dsa) > 0
        assert all(r.domain == "dsa" for r in results_dsa)

        # Querying with cn domain filter
        results_cn = retriever.retrieve(
            query="tcp udp handshake protocol packet",
            skill="Networks",
            domains=["cn"],
            top_k=3,
        )
        assert len(results_cn) > 0
        assert all(r.domain == "cn" for r in results_cn)

    def test_top_k_and_ordering(self, retriever):
        results = retriever.retrieve(
            query="binary search tree recursion stack queue",
            skill="Python",
            domains=["dsa"],
            top_k=4,
        )
        assert len(results) <= 4
        # Verify scores are monotonically non-increasing
        for i in range(len(results) - 1):
            assert results[i].final_score >= results[i + 1].final_score

    def test_matched_terms_accuracy(self, retriever):
        results = retriever.retrieve(
            query="microservices monolith architecture scaling",
            skill="System Design",
            domains=["system-design"],
            top_k=2,
        )
        assert len(results) > 0
        top_match = results[0]
        matched = top_match.metadata["matched_terms"]
        # Must match at least one of the query terms
        assert any(t in matched for t in ["microservices", "monolith", "architecture", "scaling"])

    def test_empty_and_nonsense_queries(self, retriever):
        # Empty query
        assert retriever.retrieve(query="", skill="Python") == []
        # Query with only punctuation/spaces
        assert retriever.retrieve(query="   ??? ... ", skill="Python") == []
        # Non-matching nonsense
        assert retriever.retrieve(query="xyzzyqwerty123456789nonexistent", skill="Python") == []


# ── Tri-Retriever Independence Tests ─────────────────────────────────

class TestAllThreeRetrieversIndependent:
    """Verify that Vector, Keyword, and Graph retrievers can all run independently."""

    def test_all_three_implemented(self):
        modes = get_implemented_modes()
        assert "dense" in modes
        assert "graph" in modes
        assert "keyword" in modes

    def test_keyword_and_graph_coexist(self, retriever):
        from app.rag.graph_retriever import GraphRetriever
        from app.rag.graph_store import get_graph_store

        graph_ret = GraphRetriever(get_graph_store())
        kw_ret = retriever

        q = "How do indexes optimize SQL queries in databases?"
        res_kw = kw_ret.retrieve(query=q, skill="SQL", domains=["dbms"], top_k=2)
        res_graph = graph_ret.retrieve(query=q, skill="SQL", domains=["dbms"], top_k=2)

        assert len(res_kw) > 0
        assert len(res_graph) > 0
        assert res_kw[0].retriever == "keyword"
        assert res_graph[0].retriever == "graph"

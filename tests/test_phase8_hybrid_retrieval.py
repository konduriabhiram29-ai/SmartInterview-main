"""
SmartInterview — Phase 8 Tests: Hybrid Retrieval

Tests that verify:
  1. HybridRetriever contract compliance (subclasses BaseRetriever, name, stats).
  2. Factory integration (mode="hybrid" in get_implemented_modes(), resolves to HybridRetriever).
  3. Score normalizations across disparate scales (vector cosine distance, BM25, graph).
  4. Weighted linear combination fusion logic & mathematical correctness.
  5. Reciprocal Rank Fusion (RRF) logic & mathematical correctness.
  6. Deduplication and multi-source provenance metadata (sources, ranks, normalized scores, explanations).
  7. Graceful degradation: handles retriever exceptions and zero-result legs with dynamic weight re-normalization.
  8. Integration with real Keyword and Graph retrievers over the canonical SmartInterview KB.
  9. Baseline Dense RAG remains 100% operational and default.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.graph_retriever import GraphRetriever
from app.rag.graph_store import get_graph_store
from app.rag.retriever_factory import get_retriever, get_implemented_modes


# ── Fixtures & Mock Helpers ───────────────────────────────────────────

class MockSimpleRetriever(BaseRetriever):
    """Mock retriever returning predetermined RetrievalResult objects."""
    def __init__(self, name: str, results: list[RetrievalResult], should_fail: bool = False):
        self._name = name
        self._results = results
        self._should_fail = should_fail

    @property
    def name(self) -> str:
        return self._name

    def retrieve(self, query: str, skill: str, domains=None, top_k=3, **kwargs):
        if self._should_fail:
            raise RuntimeError(f"Simulated failure in {self._name}")
        return self._results[:top_k]


def _make_result(chunk_id: str, concept: str, domain: str = "dbms", text: str = "Sample", **kwargs) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=text,
        domain=domain,
        concept=concept,
        **kwargs,
    )


# ── 1. Contract & Interface Tests ─────────────────────────────────────

class TestHybridRetrieverContract:
    def test_inherits_base_retriever(self):
        ret = HybridRetriever()
        assert isinstance(ret, BaseRetriever)
        assert ret.name == "HybridRetriever"

    def test_factory_resolves_hybrid_mode(self):
        ret = get_retriever(mode="hybrid")
        assert isinstance(ret, HybridRetriever)
        assert "hybrid" in get_implemented_modes()

    def test_get_stats(self):
        ret = HybridRetriever(
            fusion_method="weighted",
            weights={"vector": 0.5, "keyword": 0.2, "graph": 0.3},
            rrf_k=60,
            fetch_k=8,
        )
        stats = ret.get_stats()
        assert stats["retriever"] == "HybridRetriever"
        assert stats["fusion_method"] == "weighted"
        assert stats["weights"]["vector"] == 0.5
        assert stats["rrf_k"] == 60
        assert stats["fetch_k"] == 8


# ── 2. Score Normalization Tests ──────────────────────────────────────

class TestScoreNormalization:
    def test_vector_normalization_max_mode(self):
        # Distance: 0.1 (sim 0.9), 0.4 (sim 0.6)
        r1 = _make_result("c1", "Concept1", vector_score=0.1)
        r2 = _make_result("c2", "Concept2", vector_score=0.4)
        norm = HybridRetriever.normalize_vector_scores([r1, r2], mode="max")
        # Max sim is 0.9 -> 1.0; 0.6 -> 0.6/0.9 = 0.6667
        assert pytest.approx(norm["c1"], 0.001) == 1.0
        assert pytest.approx(norm["c2"], 0.001) == 0.6667

    def test_vector_normalization_clamping(self):
        # Distance > 1.0 clamped to similarity 0.0
        r1 = _make_result("c1", "Concept1", vector_score=1.5)
        r2 = _make_result("c2", "Concept2", vector_score=0.2)
        norm = HybridRetriever.normalize_vector_scores([r1, r2], mode="max")
        assert norm["c1"] == 0.0
        assert norm["c2"] == 1.0

    def test_keyword_normalization(self):
        r1 = _make_result("c1", "Concept1", keyword_score=10.0)
        r2 = _make_result("c2", "Concept2", keyword_score=5.0)
        norm = HybridRetriever.normalize_keyword_scores([r1, r2], mode="max")
        assert norm["c1"] == 1.0
        assert norm["c2"] == 0.5

    def test_graph_normalization(self):
        r1 = _make_result("c1", "Concept1", graph_score=0.8)
        r2 = _make_result("c2", "Concept2", graph_score=0.4)
        norm = HybridRetriever.normalize_graph_scores([r1, r2], mode="max")
        assert norm["c1"] == 1.0
        assert norm["c2"] == 0.5

    def test_empty_lists_return_empty_dict(self):
        assert HybridRetriever.normalize_vector_scores([]) == {}
        assert HybridRetriever.normalize_keyword_scores([]) == {}
        assert HybridRetriever.normalize_graph_scores([]) == {}


# ── 3. Weighted Linear Fusion Tests ───────────────────────────────────

class TestWeightedFusionLogic:
    def test_weighted_fusion_deduplication_and_math(self):
        # Chunk 1: in Vector (dist=0.1 -> sim=0.9) and Graph (score=0.8)
        # Chunk 2: in Keyword only (bm25=12.0)
        # Chunk 3: in Vector only (dist=0.4 -> sim=0.6)
        vec_res = [
            _make_result("c1", "ACID", vector_score=0.1),
            _make_result("c3", "Transactions", vector_score=0.4),
        ]
        kw_res = [
            _make_result("c2", "Isolation", keyword_score=12.0),
        ]
        gr_res = [
            _make_result("c1", "ACID", graph_score=0.8),
        ]

        vec_mock = MockSimpleRetriever("Vector", vec_res)
        kw_mock = MockSimpleRetriever("Keyword", kw_res)
        gr_mock = MockSimpleRetriever("Graph", gr_res)

        weights = {"vector": 0.50, "keyword": 0.30, "graph": 0.20}
        retriever = HybridRetriever(
            vector_retriever=vec_mock,
            keyword_retriever=kw_mock,
            graph_retriever=gr_mock,
            fusion_method="weighted",
            weights=weights,
        )

        results = retriever.retrieve("query", "SQL", top_k=5)

        # 3 unique chunks
        assert len(results) == 3
        c1 = next(r for r in results if r.chunk_id == "c1")
        c2 = next(r for r in results if r.chunk_id == "c2")
        c3 = next(r for r in results if r.chunk_id == "c3")

        # c1 has vector (norm 1.0) and graph (norm 1.0)
        # expected score = 0.50 * 1.0 + 0.30 * 0.0 + 0.20 * 1.0 = 0.70
        assert pytest.approx(c1.final_score, 0.01) == 0.70
        assert set(c1.metadata["sources"]) == {"vector", "graph"}

        # c2 has keyword (norm 1.0)
        # expected score = 0.50 * 0.0 + 0.30 * 1.0 + 0.20 * 0.0 = 0.30
        assert pytest.approx(c2.final_score, 0.01) == 0.30
        assert c2.metadata["sources"] == ["keyword"]

        # c3 has vector (norm 0.6/0.9 = 0.6667)
        # expected score = 0.50 * 0.6667 = 0.3333
        assert pytest.approx(c3.final_score, 0.01) == 0.3333
        assert c3.metadata["sources"] == ["vector"]

        # Order should be c1 (0.70) > c3 (0.3333) > c2 (0.30)
        assert [r.chunk_id for r in results] == ["c1", "c3", "c2"]


# ── 4. Reciprocal Rank Fusion (RRF) Tests ─────────────────────────────

class TestReciprocalRankFusion:
    def test_rrf_scoring(self):
        # Chunk 1: rank 1 in Vector, rank 2 in Keyword
        # Chunk 2: rank 1 in Keyword
        # Chunk 3: rank 2 in Vector
        k = 60
        vec_res = [
            _make_result("c1", "Concept1", vector_score=0.1),
            _make_result("c3", "Concept3", vector_score=0.2),
        ]
        kw_res = [
            _make_result("c2", "Concept2", keyword_score=10.0),
            _make_result("c1", "Concept1", keyword_score=8.0),
        ]

        vec_mock = MockSimpleRetriever("Vector", vec_res)
        kw_mock = MockSimpleRetriever("Keyword", kw_res)

        # Equal weights (0.5, 0.5)
        retriever = HybridRetriever(
            vector_retriever=vec_mock,
            keyword_retriever=kw_mock,
            graph_retriever=None,
            fusion_method="rrf",
            weights={"vector": 0.5, "keyword": 0.5},
            rrf_k=k,
        )

        results = retriever.retrieve("query", "skill", top_k=3)

        c1 = next(r for r in results if r.chunk_id == "c1")
        c2 = next(r for r in results if r.chunk_id == "c2")
        c3 = next(r for r in results if r.chunk_id == "c3")

        # c1 RRF = 0.5 / (60 + 1) + 0.5 / (60 + 2) = 0.5/61 + 0.5/62 = 0.0081967 + 0.0080645 = 0.016261
        # c2 RRF = 0.5 / (60 + 1) = 0.5/61 = 0.008197
        # c3 RRF = 0.5 / (60 + 2) = 0.5/62 = 0.008065
        assert pytest.approx(c1.final_score, 0.0001) == (0.5/61 + 0.5/62)
        assert pytest.approx(c2.final_score, 0.0001) == (0.5/61)
        assert pytest.approx(c3.final_score, 0.0001) == (0.5/62)

        # c1 should be rank 1 overall
        assert results[0].chunk_id == "c1"


# ── 5. Metadata Attribution & Explainability ──────────────────────────

class TestMetadataAttribution:
    def test_metadata_provenance(self):
        vec_res = [_make_result("c1", "Concept1", vector_score=0.15)]
        kw_res = [_make_result("c1", "Concept1", keyword_score=9.5, metadata={"matched_terms": ["index", "b-tree"]})]
        gr_res = [_make_result("c1", "Concept1", graph_score=0.88, metadata={"graph_traversal": {"hop": 1}})]

        retriever = HybridRetriever(
            vector_retriever=MockSimpleRetriever("Vector", vec_res),
            keyword_retriever=MockSimpleRetriever("Keyword", kw_res),
            graph_retriever=MockSimpleRetriever("Graph", gr_res),
        )

        results = retriever.retrieve("query", "skill", top_k=1)
        assert len(results) == 1
        res = results[0]

        assert res.retriever == "hybrid"
        assert set(res.metadata["sources"]) == {"vector", "keyword", "graph"}
        assert res.metadata["ranks"]["vector"] == 1
        assert res.metadata["ranks"]["keyword"] == 1
        assert res.metadata["ranks"]["graph"] == 1
        assert res.metadata["matched_terms"] == ["index", "b-tree"]
        assert res.metadata["graph_traversal"] == {"hop": 1}
        assert "Retrieved by graph, keyword, vector" in res.metadata["explanation"]


# ── 6. Error Resiliency & Graceful Degradation ────────────────────────

class TestGracefulDegradation:
    def test_handles_failing_retriever(self):
        # Vector retriever throws an unexpected exception
        vec_failing = MockSimpleRetriever("Vector", [], should_fail=True)
        kw_ok = MockSimpleRetriever("Keyword", [_make_result("c1", "Concept1", keyword_score=5.0)])

        retriever = HybridRetriever(
            vector_retriever=vec_failing,
            keyword_retriever=kw_ok,
            weights={"vector": 0.5, "keyword": 0.5},
        )

        # Must not raise; must re-normalize weights to keyword (weight 1.0)
        results = retriever.retrieve("query", "skill", top_k=2)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"
        assert results[0].metadata["sources"] == ["keyword"]
        assert results[0].metadata["fusion_weights"] == {"keyword": 1.0}

    def test_handles_empty_candidates_from_all_retrievers(self):
        retriever = HybridRetriever(
            vector_retriever=MockSimpleRetriever("Vector", []),
            keyword_retriever=MockSimpleRetriever("Keyword", []),
            graph_retriever=MockSimpleRetriever("Graph", []),
        )
        results = retriever.retrieve("empty", "skill", top_k=3)
        assert results == []


# ── 7. Real Hybrid Integration (Keyword + Graph) ──────────────────────

class TestRealHybridIntegration:
    def test_real_keyword_and_graph_fusion(self):
        kw_retriever = KeywordRetriever()
        gr_retriever = GraphRetriever(graph_store=get_graph_store())

        hybrid = HybridRetriever(
            vector_retriever=None,
            keyword_retriever=kw_retriever,
            graph_retriever=gr_retriever,
            weights={"keyword": 0.5, "graph": 0.5},
        )

        results = hybrid.retrieve(
            query="ACID database transactions atomicity consistency isolation durability",
            skill="SQL",
            domains=["dbms"],
            top_k=4,
        )

        assert len(results) > 0
        assert len(results) <= 4
        # Every result should be a valid RetrievalResult with hybrid provenance
        for r in results:
            assert isinstance(r, RetrievalResult)
            assert r.retriever == "hybrid"
            assert r.domain == "dbms"
            assert r.final_score > 0.0
            assert len(r.metadata["sources"]) >= 1


# ── 8. Baseline Protection ────────────────────────────────────────────

class TestDenseBaselineProtection:
    def test_dense_mode_remains_available(self):
        assert "dense" in get_implemented_modes()
        # Ensure requesting dense mode without required singletons gives clear ValueError
        with pytest.raises(ValueError) as excinfo:
            get_retriever(mode="dense")
        assert "VectorRetriever requires embedding_model" in str(excinfo.value)

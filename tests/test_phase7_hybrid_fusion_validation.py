"""
SmartInterview — Phase 7 Dedicated Validation Test Suite
Retrieval Modes, Mode Switching, Hybrid Fusion (Weighted Linear Combination & RRF),
Multi-Source Provenance Attribution, and Mathematical Correctness.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.graph_retriever import GraphRetriever
from app.rag.graph_store import get_graph_store
from app.rag.retriever_factory import get_retriever, get_implemented_modes


# ── Mock Sub-Retriever Helper ──────────────────────────────────────────

class MockRetriever(BaseRetriever):
    def __init__(self, name: str, results: list[RetrievalResult], should_fail: bool = False):
        self._name = name
        self._results = results
        self._should_fail = should_fail

    @property
    def name(self) -> str:
        return self._name

    def retrieve(self, query: str, skill: str, domains=None, top_k=3, **kwargs):
        if self._should_fail:
            raise RuntimeError(f"Simulated fault in {self._name}")
        return self._results[:top_k]


def _create_chunk(chunk_id: str, concept: str, domain: str = "dbms", **kwargs) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=f"Full text for {chunk_id} covering {concept}",
        domain=domain,
        concept=concept,
        **kwargs,
    )


# ── 1. Retrieval Modes & Factory Verification ──────────────────────────

class TestRetrievalModesAndFactory:
    def test_all_modes_present_in_factory(self):
        modes = get_implemented_modes()
        assert "dense" in modes
        assert "keyword" in modes
        assert "graph" in modes
        assert "hybrid" in modes

    def test_factory_resolves_all_modes_case_insensitively(self):
        assert isinstance(get_retriever(mode="KEYWORD"), KeywordRetriever)
        assert isinstance(get_retriever(mode="Graph"), GraphRetriever)
        assert isinstance(get_retriever(mode="  hybrid  "), HybridRetriever)

    def test_unrecognized_mode_falls_back_safely(self):
        # When unrecognised mode is passed without vector components, ValueError is raised by VectorRetriever fallback
        with pytest.raises(ValueError, match="VectorRetriever requires"):
            get_retriever(mode="unsupported_quantum_mode")


# ── 2. Hybrid Score Normalization Extremes ─────────────────────────────

class TestScoreNormalizationExtremes:
    def test_empty_candidate_lists(self):
        assert HybridRetriever.normalize_vector_scores([]) == {}
        assert HybridRetriever.normalize_keyword_scores([]) == {}
        assert HybridRetriever.normalize_graph_scores([]) == {}

    def test_identical_scores_minmax(self):
        r1 = _create_chunk("c1", "Concept1", keyword_score=5.0)
        r2 = _create_chunk("c2", "Concept2", keyword_score=5.0)
        norm = HybridRetriever.normalize_keyword_scores([r1, r2], mode="minmax")
        # Identical non-zero scores should normalize to 1.0
        assert norm["c1"] == 1.0
        assert norm["c2"] == 1.0

    def test_clamping_negative_and_out_of_bound_scores(self):
        r1 = _create_chunk("c1", "Concept1", vector_score=-0.5)  # impossible negative distance
        r2 = _create_chunk("c2", "Concept2", vector_score=1.5)   # distance > 1.0
        norm = HybridRetriever.normalize_vector_scores([r1, r2], mode="max")
        assert norm["c1"] >= 0.0
        assert norm["c2"] == 0.0


# ── 3. Weighted Linear Combination Mathematical Rigor ─────────────────

class TestWeightedLinearFusionMath:
    def test_exact_weighted_calculation(self):
        # 2 chunks across Vector and Keyword
        v_res = [
            _create_chunk("chunk_1", "ConceptA", vector_score=0.2),  # sim 0.8
            _create_chunk("chunk_2", "ConceptB", vector_score=0.6),  # sim 0.4
        ]
        k_res = [
            _create_chunk("chunk_2", "ConceptB", keyword_score=10.0), # max 10.0 -> 1.0
            _create_chunk("chunk_1", "ConceptA", keyword_score=5.0),  # 5.0 -> 0.5
        ]

        vec_mock = MockRetriever("VectorRetriever", v_res)
        kw_mock = MockRetriever("KeywordRetriever", k_res)

        hybrid = HybridRetriever(
            vector_retriever=vec_mock,
            keyword_retriever=kw_mock,
            graph_retriever=None,
            fusion_method="weighted",
            weights={"vector": 0.6, "keyword": 0.4},
        )

        results = hybrid.retrieve("query", "skill", top_k=2)
        assert len(results) == 2

        # chunk_1: vec_norm = 1.0 (since 0.8 is max), kw_norm = 0.5
        # score = 0.6*1.0 + 0.4*0.5 = 0.6 + 0.2 = 0.80
        # chunk_2: vec_norm = 0.4/0.8 = 0.5, kw_norm = 1.0
        # score = 0.6*0.5 + 0.4*1.0 = 0.3 + 0.4 = 0.70
        res_by_id = {r.chunk_id: r for r in results}
        assert pytest.approx(res_by_id["chunk_1"].final_score, 0.001) == 0.80
        assert pytest.approx(res_by_id["chunk_2"].final_score, 0.001) == 0.70
        assert results[0].chunk_id == "chunk_1"

    def test_dynamic_weight_renormalization_on_absent_leg(self):
        # If vector leg returns nothing, keyword weights must re-normalize to 1.0
        k_res = [_create_chunk("chunk_k", "ConceptK", keyword_score=8.0)]
        kw_mock = MockRetriever("KeywordRetriever", k_res)

        hybrid = HybridRetriever(
            vector_retriever=None,
            keyword_retriever=kw_mock,
            graph_retriever=None,
            fusion_method="weighted",
            weights={"vector": 0.7, "keyword": 0.3},
        )

        results = hybrid.retrieve("query", "skill", top_k=1)
        assert len(results) == 1
        # Weight should be re-normalized from 0.3 to 1.0 -> final score = 1.0
        assert pytest.approx(results[0].final_score, 0.001) == 1.0
        assert results[0].metadata["fusion_weights"] == {"keyword": 1.0}


# ── 4. Reciprocal Rank Fusion (RRF) Verification ───────────────────────

class TestReciprocalRankFusionMath:
    def test_rrf_formula_with_custom_k(self):
        # chunk_A: vector rank 1, keyword rank 2
        # chunk_B: vector rank 2, keyword rank 1
        v_res = [_create_chunk("A", "C1"), _create_chunk("B", "C2")]
        k_res = [_create_chunk("B", "C2"), _create_chunk("A", "C1")]

        vec_mock = MockRetriever("VectorRetriever", v_res)
        kw_mock = MockRetriever("KeywordRetriever", k_res)

        hybrid = HybridRetriever(
            vector_retriever=vec_mock,
            keyword_retriever=kw_mock,
            fusion_method="rrf",
            rrf_k=60,
            weights={"vector": 0.5, "keyword": 0.5},
        )

        results = hybrid.retrieve("query", "skill", top_k=2)
        assert len(results) == 2

        # A: 0.5 * (1/61) + 0.5 * (1/62) = 0.0081967 + 0.0080645 = 0.0162612
        # B: 0.5 * (1/62) + 0.5 * (1/61) = 0.0162612 (identical due to symmetric ranks)
        assert pytest.approx(results[0].final_score, 0.0001) == results[1].final_score


# ── 5. Multi-Source Provenance & Metadata Attribution ─────────────────

class TestProvenanceAndGraphRetention:
    def test_graph_provenance_retained_across_fusion(self):
        v_res = [_create_chunk("dbms_acid-properties_001", "acid-properties")]
        g_res = [
            RetrievalResult(
                chunk_id="dbms_acid-properties_001",
                text="ACID properties explain transactional guarantees.",
                domain="dbms",
                concept="acid-properties",
                graph_score=0.92,
                metadata={
                    "concept_id": "dbms_acid-properties",
                    "role": "seed",
                    "remediation": False,
                    "traversal_path": "anchor(dbms_acid-properties)",
                    "confidence": 1.0,
                    "bloom_level": "understand",
                },
            )
        ]

        vec_mock = MockRetriever("VectorRetriever", v_res)
        graph_mock = MockRetriever("GraphRetriever", g_res)

        hybrid = HybridRetriever(
            vector_retriever=vec_mock,
            keyword_retriever=None,
            graph_retriever=graph_mock,
        )

        results = hybrid.retrieve("ACID", "SQL", top_k=1)
        assert len(results) == 1
        res = results[0]

        # Multi-source attribution
        assert set(res.metadata["sources"]) == {"vector", "graph"}
        # Graph provenance preserved
        assert res.metadata["traversal_path"] == "anchor(dbms_acid-properties)"
        assert res.metadata["role"] == "seed"
        assert res.metadata["concept_id"] == "dbms_acid-properties"
        # Canonical full text guaranteed
        assert res.metadata.get("is_full_text") is True
        assert len(res.text) > 400


# ── 6. Edge Cases & Resilience ────────────────────────────────────────

class TestEdgeCasesAndResilience:
    def test_top_k_zero_and_negative(self):
        hybrid = HybridRetriever()
        assert hybrid.retrieve("query", "skill", top_k=0) == []
        assert hybrid.retrieve("query", "skill", top_k=-3) == []

    def test_none_query_handled_safely(self):
        hybrid = HybridRetriever(
            vector_retriever=MockRetriever("V", [_create_chunk("c1", "C1")]),
        )
        results = hybrid.retrieve(None, "skill", top_k=1)
        assert len(results) == 1

    def test_latency_ms_stamped_on_results(self):
        hybrid = HybridRetriever(
            vector_retriever=MockRetriever("V", [_create_chunk("c1", "C1")]),
        )
        results = hybrid.retrieve("test", "skill", top_k=1)
        assert len(results) == 1
        assert "latency_ms" in results[0].metadata
        assert results[0].metadata["latency_ms"] >= 0.0

    def test_real_tri_hybrid_integration_over_canonical_kb(self):
        """Test true live tri-hybrid integration using real Keyword and Graph retrievers."""
        store = get_graph_store()
        kw = KeywordRetriever()
        gr = GraphRetriever(graph_store=store)

        hybrid = HybridRetriever(
            vector_retriever=None,
            keyword_retriever=kw,
            graph_retriever=gr,
            fusion_method="weighted",
            weights={"keyword": 0.4, "graph": 0.6},
        )

        results = hybrid.retrieve(
            query="ACID database transactions and isolation",
            skill="SQL",
            domains=["dbms"],
            top_k=3,
        )

        assert len(results) > 0
        assert all(r.retriever == "hybrid" for r in results)
        assert all(r.domain == "dbms" for r in results)
        assert all(r.metadata.get("is_full_text") is True for r in results)

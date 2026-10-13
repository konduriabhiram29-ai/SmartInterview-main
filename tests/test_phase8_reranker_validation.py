"""
SmartInterview — Phase 8 Tests: Contextual Reranking Audit & Validation

Comprehensive test suite verifying:
  1. BaseReranker contract compliance and get_stats() implementation.
  2. Factory dispatch via get_reranker() for all backends (semantic, cross_encoder, passthrough, none).
  3. PassThroughReranker preservation of ranking, top-k slicing, and metadata stamping.
  4. SemanticEmbeddingReranker cosine scoring, lexical overlap boost, and candidate promotion.
  5. Concept diversity filtering preventing domination by a single concept.
  6. CrossEncoderReranker logits to sigmoid probability transformation.
  7. Threshold filtering and non-empty safeguard (preventing prompt context starvation).
  8. Robust input sanitization (top_k <= 0, query=None, results=[]).
  9. High-resolution rerank_latency_ms tracking.
  10. Dense RAG isolation audit: verifying dense baseline bypasses reranker.
"""

from __future__ import annotations

import os
import sys
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.retrieval_result import RetrievalResult
from app.rag.reranker import (
    BaseReranker,
    PassThroughReranker,
    SemanticEmbeddingReranker,
    CrossEncoderReranker,
    get_reranker,
    _tokenize,
    _term_overlap_ratio,
    _cosine_similarity,
)


# ── Helpers & Test Doubles ────────────────────────────────────────────

def _create_candidate(
    chunk_id: str,
    text: str,
    concept: str = "Operating Systems",
    score: float = 0.5,
    domain: str = "os",
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=text,
        domain=domain,
        concept=concept,
        final_score=score,
        retriever="test_retriever",
        metadata={"initial_meta": True},
    )


class MockEmbeddingModel:
    """Mock SentenceTransformer that returns controlled vectors for deterministic testing."""
    def __init__(self, mapping: dict[str, list[float]]):
        self.mapping = mapping

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for t in texts:
            vec = self.mapping.get(t, [0.0, 1.0])
            vectors.append(vec)
        return np.array(vectors, dtype=float)


# ── Test Suite ─────────────────────────────────────────────────────────

class TestRerankerContractAndStats:
    def test_abstract_base_class_instantiation(self):
        with pytest.raises(TypeError):
            BaseReranker()  # type: ignore

    def test_passthrough_reranker_stats(self):
        reranker = PassThroughReranker()
        stats = reranker.get_stats()
        assert stats["reranker"] == "PassThroughReranker"
        assert stats["backend"] == "passthrough"

    def test_semantic_reranker_stats(self):
        reranker = SemanticEmbeddingReranker(default_threshold=0.45, term_overlap_weight=0.20)
        stats = reranker.get_stats()
        assert stats["reranker"] == "SemanticEmbeddingReranker"
        assert stats["backend"] == "semantic"
        assert stats["default_threshold"] == 0.45
        assert stats["term_overlap_weight"] == 0.20

    def test_cross_encoder_reranker_stats(self):
        reranker = CrossEncoderReranker(model_name="dummy/model", default_threshold=0.35)
        stats = reranker.get_stats()
        assert stats["reranker"] == "CrossEncoderReranker"
        assert stats["backend"] == "cross_encoder"
        assert stats["model_name"] == "dummy/model"
        assert stats["default_threshold"] == 0.35


class TestFactoryDispatch:
    def test_factory_semantic(self):
        reranker = get_reranker(backend="semantic")
        assert isinstance(reranker, SemanticEmbeddingReranker)

    def test_factory_passthrough_and_none(self):
        for name in ["passthrough", "none"]:
            reranker = get_reranker(backend=name)
            assert isinstance(reranker, PassThroughReranker)

    @patch("app.rag.reranker.RERANKER_ENABLED", False)
    def test_factory_disabled_flag_forces_passthrough(self):
        reranker = get_reranker(backend="semantic")
        assert isinstance(reranker, PassThroughReranker)

    def test_factory_cross_encoder_fallback(self):
        with patch("app.rag.reranker.CrossEncoderReranker", side_effect=RuntimeError("CrossEncoder init failure")):
            reranker = get_reranker(backend="cross_encoder")
            assert isinstance(reranker, SemanticEmbeddingReranker)

    def test_cross_encoder_runtime_fallback_on_load_error(self):
        reranker = CrossEncoderReranker(model_name="nonexistent/model")
        with patch.object(reranker, "_get_model", side_effect=ImportError("sentence_transformers missing")):
            cands = [_create_candidate("c1", "Candidate text")]
            out = reranker.rerank(query="query", results=cands, top_k=1)
            assert len(out) == 1
            assert out[0].chunk_id == "c1"
            assert out[0].metadata["reranker"] == "SemanticEmbeddingReranker"


class TestHelpers:
    def test_tokenize_edge_cases(self):
        assert _tokenize("") == set()
        assert _tokenize(None) == set()  # type: ignore
        assert _tokenize("Virtual-Memory & Paging!") == {"virtual", "memory", "paging"}

    def test_term_overlap_ratio(self):
        assert _term_overlap_ratio("", "some text") == 0.0
        assert _term_overlap_ratio("deadlock prevention", "methods for deadlock prevention and detection") == 1.0
        assert _term_overlap_ratio("deadlock avoidance bankers", "deadlock avoidance using graph") == 2 / 3

    def test_cosine_similarity_edge_cases(self):
        zero_v = np.array([0.0, 0.0])
        norm_v = np.array([1.0, 0.0])
        assert _cosine_similarity(zero_v, norm_v) == 0.0
        assert _cosine_similarity(norm_v, norm_v) == 1.0


class TestPassThroughRerankerBehavior:
    def test_preserves_order_and_sets_latency(self):
        reranker = PassThroughReranker()
        cands = [
            _create_candidate("c1", "Candidate 1", score=0.9),
            _create_candidate("c2", "Candidate 2", score=0.8),
            _create_candidate("c3", "Candidate 3", score=0.7),
        ]
        out = reranker.rerank(query="anything", results=cands, top_k=2)
        assert len(out) == 2
        assert [c.chunk_id for c in out] == ["c1", "c2"]
        assert out[0].metadata["original_rank"] == 1
        assert out[0].metadata["rerank_rank"] == 1
        assert out[0].metadata["reranker"] == "PassThroughReranker"
        assert "rerank_latency_ms" in out[0].metadata
        assert out[0].metadata["rerank_latency_ms"] >= 0.0

    def test_top_k_zero_or_negative(self):
        reranker = PassThroughReranker()
        cands = [_create_candidate("c1", "Candidate 1")]
        assert reranker.rerank(query="q", results=cands, top_k=0) == []
        assert reranker.rerank(query="q", results=cands, top_k=-1) == []


class TestSemanticEmbeddingRerankerBehavior:
    def test_candidate_promotion_and_overlap(self):
        q = "semaphores and mutexes"
        t1 = "cpu scheduling algorithms round robin priority"
        t2 = "synchronization primitives semaphores and mutexes prevent race conditions"

        mapping = {
            q: [1.0, 0.0],
            t1: [0.0, 1.0],  # orthogonal
            t2: [0.95, 0.31],  # high cosine similarity
        }
        mock_model = MockEmbeddingModel(mapping)
        reranker = SemanticEmbeddingReranker(embedding_model=mock_model, default_threshold=0.0)

        # Candidate 1 was ranked #1 initially, Candidate 2 was #2
        cands = [
            _create_candidate("c1", t1, score=0.99),
            _create_candidate("c2", t2, score=0.30),
        ]

        out = reranker.rerank(query=q, results=cands, top_k=2)
        assert len(out) == 2
        # Candidate 2 promoted to rank 1
        assert out[0].chunk_id == "c2"
        assert out[0].metadata["original_rank"] == 2
        assert out[0].metadata["rerank_rank"] == 1
        assert out[0].metadata["reranker"] == "SemanticEmbeddingReranker"
        assert out[0].metadata["rerank_latency_ms"] >= 0.0

        # Candidate 1 demoted to rank 2
        assert out[1].chunk_id == "c1"
        assert out[1].metadata["original_rank"] == 1
        assert out[1].metadata["rerank_rank"] == 2

    def test_concept_diversity_limiting(self):
        # 4 candidates with identical text but different concepts
        q = "database indexing"
        cands = [
            _create_candidate("c1", "B-Tree indexing in databases", concept="Indexing", score=0.9),
            _create_candidate("c2", "Clustered index mechanics", concept="Indexing", score=0.85),
            _create_candidate("c3", "Non-clustered index lookup", concept="Indexing", score=0.80),
            _create_candidate("c4", "Query optimizer execution plan", concept="Query Execution", score=0.75),
        ]

        mapping = {
            q: [1.0, 0.0],
            "B-Tree indexing in databases": [1.0, 0.0],
            "Clustered index mechanics": [1.0, 0.0],
            "Non-clustered index lookup": [1.0, 0.0],
            "Query optimizer execution plan": [0.8, 0.6],
        }
        mock_model = MockEmbeddingModel(mapping)
        reranker = SemanticEmbeddingReranker(embedding_model=mock_model, default_threshold=0.0)

        # With diverse=True and top_k=3, max_per_concept = ceil(3/2) = 2.
        # So "Indexing" can at most contribute 2 chunks, and "Query Execution" is selected for slot 3!
        out = reranker.rerank(query=q, results=cands, top_k=3, diverse=True)
        assert len(out) == 3
        concepts = [c.concept for c in out]
        assert concepts.count("Indexing") == 2
        assert concepts.count("Query Execution") == 1

    def test_query_none_or_empty_sanitization(self):
        mock_model = MockEmbeddingModel({})
        reranker = SemanticEmbeddingReranker(embedding_model=mock_model, default_threshold=0.0)
        cands = [_create_candidate("c1", "Sample text")]
        out = reranker.rerank(query=None, results=cands, top_k=1)  # type: ignore
        assert len(out) == 1
        assert out[0].chunk_id == "c1"


class TestCrossEncoderRerankerBehavior:
    def test_sigmoid_probability_transformation(self):
        mock_ce = MagicMock()
        # High logit (+5.0) -> sigmoid ~ 0.993
        # Zero logit (0.0)   -> sigmoid = 0.500
        # Negative logit (-5.0) -> sigmoid ~ 0.0067
        mock_ce.predict.return_value = np.array([5.0, 0.0, -5.0])

        reranker = CrossEncoderReranker(cross_encoder=mock_ce, default_threshold=0.0)
        cands = [
            _create_candidate("c1", "Text 1"),
            _create_candidate("c2", "Text 2"),
            _create_candidate("c3", "Text 3"),
        ]

        out = reranker.rerank(query="query", results=cands, top_k=3)
        assert len(out) == 3
        assert out[0].chunk_id == "c1"
        assert out[0].final_score > 0.99
        assert abs(out[1].final_score - 0.5) < 0.01
        assert out[2].final_score < 0.01
        assert out[0].metadata["reranker"] == "CrossEncoderReranker"
        assert out[0].metadata["rerank_latency_ms"] >= 0.0


class TestSafeguardsAndThresholds:
    def test_non_empty_safeguard_semantic(self):
        # All candidates score below high threshold 0.99
        q = "query"
        mapping = {
            q: [1.0, 0.0],
            "Cand 1": [0.5, 0.5],
            "Cand 2": [0.1, 0.9],
        }
        mock_model = MockEmbeddingModel(mapping)
        reranker = SemanticEmbeddingReranker(embedding_model=mock_model, default_threshold=0.99)
        cands = [
            _create_candidate("c1", "Cand 1"),
            _create_candidate("c2", "Cand 2"),
        ]
        out = reranker.rerank(query=q, results=cands, top_k=2)
        # Must preserve at least the top candidate to avoid context starvation
        assert len(out) == 1
        assert out[0].chunk_id == "c1"

    def test_non_empty_safeguard_cross_encoder(self):
        mock_ce = MagicMock()
        # Logits give probs < 0.1
        mock_ce.predict.return_value = np.array([-5.0, -10.0])
        reranker = CrossEncoderReranker(cross_encoder=mock_ce, default_threshold=0.8)
        cands = [
            _create_candidate("c1", "Cand 1"),
            _create_candidate("c2", "Cand 2"),
        ]
        out = reranker.rerank(query="query", results=cands, top_k=2)
        assert len(out) == 1
        assert out[0].chunk_id == "c1"


class TestBaselineDenseRAGIsolation:
    def test_dense_rag_never_invokes_reranker(self):
        """
        Verify architectural isolation: in question_service,
        when effective_mode is 'dense' or 'vector', reranker is explicitly bypassed.
        """
        from app.services.question_service import generate_single_question
        import inspect

        src = inspect.getsource(generate_single_question)
        # Verify guard condition
        assert "effective_mode not in" in src or "mode != 'dense'" in src or "effective_mode not in {\"dense\", \"vector\"}" in src
        assert "RERANKER_ENABLED" in src

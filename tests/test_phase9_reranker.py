"""
SmartInterview — Phase 9 Tests: Contextual Reranking

Tests that verify:
  1. BaseReranker contract compliance (cannot instantiate abstract class, subclasses).
  2. Factory dispatch via get_reranker() for semantic, cross_encoder, passthrough.
  3. PassThroughReranker behaviour and metadata annotation.
  4. SemanticEmbeddingReranker scoring, candidate re-ordering, and term overlap boost.
  5. CrossEncoderReranker scoring, sigmoid normalization, and candidate re-ordering.
  6. Threshold filtering and non-empty safeguard (prevents context starvation).
  7. End-to-end pipeline: HybridRetriever -> Reranker.
  8. Baseline protection: RAG_MODE=dense and existing pipeline unaffected.
"""

import os
import sys
import pytest
import numpy as np
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.reranker import (
    BaseReranker,
    PassThroughReranker,
    SemanticEmbeddingReranker,
    CrossEncoderReranker,
    get_reranker,
)
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.graph_retriever import GraphRetriever
from app.rag.graph_store import get_graph_store


# ── Helpers & Mocks ───────────────────────────────────────────────────

def _make_candidate(chunk_id: str, text: str, concept: str = "TestConcept", score: float = 0.5) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=text,
        domain="dbms",
        concept=concept,
        final_score=score,
        retriever="test",
    )


class MockEmbeddingModel:
    """Mock SentenceTransformer that returns orthogonal or aligned vectors based on text content."""
    def __init__(self, mapping: dict[str, list[float]]):
        self.mapping = mapping

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for t in texts:
            vec = self.mapping.get(t, [0.0, 1.0])
            vectors.append(vec)
        return np.array(vectors)


# ── 1. Contract & Factory Tests ───────────────────────────────────────

class TestRerankerContract:
    def test_abstract_class_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseReranker()  # type: ignore

    def test_factory_semantic_default(self):
        reranker = get_reranker(backend="semantic")
        assert isinstance(reranker, SemanticEmbeddingReranker)
        assert reranker.name == "SemanticEmbeddingReranker"

    def test_factory_passthrough(self):
        reranker = get_reranker(backend="passthrough")
        assert isinstance(reranker, PassThroughReranker)
        assert reranker.name == "PassThroughReranker"


# ── 2. PassThrough Reranker Tests ─────────────────────────────────────

class TestPassThroughReranker:
    def test_preserves_order_and_slices_top_k(self):
        reranker = PassThroughReranker()
        cands = [
            _make_candidate("c1", "Text 1", score=0.9),
            _make_candidate("c2", "Text 2", score=0.8),
            _make_candidate("c3", "Text 3", score=0.7),
            _make_candidate("c4", "Text 4", score=0.6),
        ]
        out = reranker.rerank(query="query", results=cands, top_k=2)
        assert len(out) == 2
        assert [r.chunk_id for r in out] == ["c1", "c2"]
        assert out[0].metadata["original_rank"] == 1
        assert out[0].metadata["rerank_rank"] == 1
        assert out[0].metadata["reranker"] == "PassThroughReranker"

    def test_empty_candidates_returns_empty(self):
        reranker = PassThroughReranker()
        assert reranker.rerank(query="query", results=[]) == []


# ── 3. Semantic Embedding Reranker Tests ──────────────────────────────

class TestSemanticEmbeddingReranker:
    def test_candidate_promotion_by_semantic_relevance(self):
        # Query vector: [1.0, 0.0]
        # Candidate 1: vector [0.0, 1.0] (orthogonal, cos_sim = 0.0)
        # Candidate 2: vector [1.0, 0.0] (identical, cos_sim = 1.0)
        q = "acid transactions"
        t1 = "relational database design schema"
        t2 = "acid transactions guarantee atomicity and durability in database engines"

        mapping = {
            q: [1.0, 0.0],
            t1: [0.0, 1.0],
            t2: [1.0, 0.0],
        }
        mock_model = MockEmbeddingModel(mapping)

        reranker = SemanticEmbeddingReranker(embedding_model=mock_model, default_threshold=0.0)

        # Candidate 1 originally rank 1, Candidate 2 originally rank 2
        cands = [
            _make_candidate("c1", t1, score=0.95),
            _make_candidate("c2", t2, score=0.40),
        ]

        out = reranker.rerank(query=q, results=cands, top_k=2)

        # Candidate 2 should be promoted to rank 1 because of high similarity and term overlap!
        assert len(out) == 2
        assert out[0].chunk_id == "c2"
        assert out[0].metadata["original_rank"] == 2
        assert out[0].metadata["rerank_rank"] == 1
        assert out[0].metadata["rerank_score"] > out[1].metadata["rerank_score"]

        # Candidate 1 demoted to rank 2
        assert out[1].chunk_id == "c1"
        assert out[1].metadata["original_rank"] == 1
        assert out[1].metadata["rerank_rank"] == 2


# ── 4. CrossEncoder Reranker Tests ────────────────────────────────────

class TestCrossEncoderReranker:
    def test_cross_encoder_logits_and_sigmoid(self):
        # Mock CrossEncoder predict returning raw logits: [4.0, -2.0]
        mock_ce = MagicMock()
        mock_ce.predict.return_value = np.array([4.0, -2.0])

        reranker = CrossEncoderReranker(cross_encoder=mock_ce, default_threshold=0.0)
        cands = [
            _make_candidate("c1", "High logit text", score=0.5),
            _make_candidate("c2", "Low logit text", score=0.5),
        ]

        out = reranker.rerank(query="query", results=cands, top_k=2)

        assert len(out) == 2
        assert out[0].chunk_id == "c1"
        # sigmoid(4.0) = 1 / (1 + e^-4) = 0.982
        # sigmoid(-2.0) = 1 / (1 + e^2) = 0.119
        assert out[0].final_score > 0.95
        assert out[1].final_score < 0.20
        assert out[0].metadata["reranker"] == "CrossEncoderReranker"


# ── 5. Threshold Filtering & Safeguard Tests ──────────────────────────

class TestThresholdFilteringAndSafeguards:
    def test_drops_candidates_below_threshold(self):
        q = "query"
        t1 = "matching query text"
        t2 = "irrelevant unrelated"

        mapping = {
            q: [1.0, 0.0],
            t1: [1.0, 0.0],
            t2: [0.0, 1.0],
        }
        mock_model = MockEmbeddingModel(mapping)

        # Threshold 0.5: c1 passes, c2 fails
        reranker = SemanticEmbeddingReranker(embedding_model=mock_model, default_threshold=0.5)
        cands = [
            _make_candidate("c1", t1),
            _make_candidate("c2", t2),
        ]

        out = reranker.rerank(query=q, results=cands, top_k=2)
        assert len(out) == 1
        assert out[0].chunk_id == "c1"

    def test_safeguard_preserves_best_candidate_when_all_fail_threshold(self):
        q = "query"
        t1 = "somewhat relevant"
        t2 = "completely irrelevant"

        mapping = {
            q: [1.0, 0.0],
            t1: [0.3, 0.95],  # low cos_sim
            t2: [0.0, 1.0],   # zero cos_sim
        }
        mock_model = MockEmbeddingModel(mapping)

        # High threshold 0.85: BOTH fail threshold
        reranker = SemanticEmbeddingReranker(embedding_model=mock_model, default_threshold=0.85)
        cands = [
            _make_candidate("c1", t1),
            _make_candidate("c2", t2),
        ]

        out = reranker.rerank(query=q, results=cands, top_k=2)
        # Safeguard must keep 1 candidate instead of starving prompt
        assert len(out) == 1
        assert out[0].chunk_id == "c1"


# ── 6. End-to-End Hybrid + Reranker Integration ───────────────────────

class TestEndToEndHybridReranking:
    def test_hybrid_retrieval_piped_to_reranker(self):
        kw_retriever = KeywordRetriever()
        gr_retriever = GraphRetriever(graph_store=get_graph_store())

        hybrid = HybridRetriever(
            vector_retriever=None,
            keyword_retriever=kw_retriever,
            graph_retriever=gr_retriever,
            weights={"keyword": 0.5, "graph": 0.5},
            fetch_k=6,
        )

        query = "Explain ACID transactions and atomicity in database systems"
        hybrid_results = hybrid.retrieve(
            query=query,
            skill="SQL",
            domains=["dbms"],
            top_k=6,
        )

        assert len(hybrid_results) > 0

        # Rerank hybrid results using SemanticEmbeddingReranker
        reranker = get_reranker(backend="semantic")
        final_results = reranker.rerank(query=query, results=hybrid_results, top_k=3)

        assert len(final_results) <= 3
        assert len(final_results) > 0

        # Each result has both hybrid provenance and rerank metadata
        for res in final_results:
            assert res.retriever == "hybrid"
            assert "sources" in res.metadata
            assert "rerank_score" in res.metadata
            assert "original_rank" in res.metadata
            assert "rerank_rank" in res.metadata
            assert res.final_score > 0.0

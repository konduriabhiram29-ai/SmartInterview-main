"""
SmartInterview — Reranker (Phase 9)

Implements contextual reranking over retrieved candidate chunks (from Hybrid,
Dense, Keyword, or Graph retrieval) prior to prompt construction:
  1. BaseReranker: Abstract interface defining the reranking contract.
  2. SemanticEmbeddingReranker: Direct cross-similarity using SentenceTransformer
     (all-MiniLM-L6-v2) + lexical term overlap boost. Fast, zero new downloads.
  3. CrossEncoderReranker: Full joint cross-attention scoring using
     sentence_transformers.CrossEncoder (e.g. cross-encoder/ms-marco-MiniLM-L-6-v2).
  4. PassThroughReranker: Lightweight no-op reranker when reranking is disabled.
  5. get_reranker(): Factory dispatch with auto-fallback and configuration.

Features:
  - Strict top-k candidate reduction.
  - Configurable minimum relevance threshold filtering.
  - Non-empty safeguard: If all candidates fall below threshold, at least the
    best candidate is preserved to prevent context starvation.
  - Rich metadata tracking (original_rank, rerank_score, rerank_rank, reranker).
"""

from __future__ import annotations

import re
import math
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any

import numpy as np

from app.rag.retrieval_result import RetrievalResult
from app.config import (
    RERANKER_ENABLED,
    RERANKER_BACKEND,
    RERANKER_MODEL,
    RERANKER_MIN_SCORE,
    RERANKER_TOP_K,
)

logger = logging.getLogger(__name__)


# ── Term Overlap & Cosine Similarity Helpers ──────────────────────────

def _tokenize(text: str) -> set[str]:
    """Extract lowercase alphanumeric tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _term_overlap_ratio(query: str, text: str) -> float:
    """Compute query token recall in candidate text."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    t_tokens = _tokenize(text[:2000])
    common = q_tokens.intersection(t_tokens)
    return len(common) / len(q_tokens)


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two numpy vectors."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


# ── Abstract Base Reranker ────────────────────────────────────────────

class BaseReranker(ABC):
    """
    Abstract contract for candidate rerankers.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 3,
        threshold: Optional[float] = None,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Rerank and filter candidates against the given query.

        Parameters
        ----------
        query     : The target query / question topic context.
        results   : List of candidate RetrievalResult instances from earlier retrieval.
        top_k     : Maximum number of reranked candidates to return.
        threshold : Minimum score threshold. If None, uses default.
        **kwargs  : Extra backend-specific parameters.

        Returns
        -------
        List[RetrievalResult] sorted by reranked score descending.
        """
        pass

    @property
    def name(self) -> str:
        """Human-readable class name."""
        return self.__class__.__name__


# ── 1. Pass-Through Reranker ──────────────────────────────────────────

class PassThroughReranker(BaseReranker):
    """
    No-op reranker used when reranking is disabled or bypassed.
    Preserves original ranking, slicing to top_k.
    """

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 3,
        threshold: Optional[float] = None,
        **kwargs,
    ) -> List[RetrievalResult]:
        if not results:
            return []
        out = results[:top_k]
        for idx, res in enumerate(out, 1):
            res.metadata["original_rank"] = idx
            res.metadata["rerank_rank"] = idx
            res.metadata["reranker"] = self.name
        return out


# ── 2. Semantic Embedding Reranker ────────────────────────────────────

class SemanticEmbeddingReranker(BaseReranker):
    """
    Reranks candidates by computing direct query-to-chunk semantic cosine
    similarity using the existing SentenceTransformer singleton, reinforced
    by exact query term recall.
    """

    def __init__(
        self,
        embedding_model=None,
        default_threshold: float = RERANKER_MIN_SCORE,
        term_overlap_weight: float = 0.15,
    ):
        self._embedding_model = embedding_model
        self.default_threshold = default_threshold
        self.term_overlap_weight = term_overlap_weight

    def _get_model(self):
        if self._embedding_model is None:
            try:
                from app.services.question_service import get_embedding_model
                self._embedding_model = get_embedding_model()
            except Exception:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedding_model

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 3,
        threshold: Optional[float] = None,
        **kwargs,
    ) -> List[RetrievalResult]:
        if not results:
            return []

        min_score = threshold if threshold is not None else self.default_threshold
        model = self._get_model()

        # Encode query and all chunk texts
        q_vec = model.encode([query])[0]
        chunk_texts = [r.text for r in results]
        c_vecs = model.encode(chunk_texts)

        scored: List[Tuple[float, int, RetrievalResult]] = []
        for orig_idx, (r, c_vec) in enumerate(zip(results, c_vecs), 1):
            cos_sim = max(0.0, _cosine_similarity(q_vec, c_vec))
            overlap = _term_overlap_ratio(query, r.text)
            # Composite rerank score in [0.0, 1.0]
            composite = (1.0 - self.term_overlap_weight) * cos_sim + self.term_overlap_weight * overlap
            scored.append((composite, orig_idx, r))

        # Sort descending by composite score
        scored.sort(key=lambda item: item[0], reverse=True)

        # Apply threshold filtering with non-empty safeguard
        passed = [item for item in scored if item[0] >= min_score]
        if not passed and scored:
            # Safeguard: preserve the best candidate
            logger.debug(
                "[SemanticReranker] All candidates scored below threshold %s; preserving top candidate.",
                min_score,
            )
            passed = [scored[0]]

        # Concept diversity: avoid crowding out prerequisites/related concepts
        max_per_concept = kwargs.get("max_per_concept", max(1, math.ceil(top_k / 2))) if kwargs.get("diverse", True) else top_k
        concept_counts: Dict[str, int] = {}
        selected_items: List[Tuple[float, int, RetrievalResult]] = []

        for item in passed:
            c_name = item[2].concept
            if concept_counts.get(c_name, 0) < max_per_concept:
                selected_items.append(item)
                concept_counts[c_name] = concept_counts.get(c_name, 0) + 1
            if len(selected_items) >= top_k:
                break

        # Fallback if diverse selection yielded fewer than top_k
        if len(selected_items) < top_k and len(passed) > len(selected_items):
            for item in passed:
                if item not in selected_items:
                    selected_items.append(item)
                if len(selected_items) >= top_k:
                    break

        final_candidates: List[RetrievalResult] = []
        for rank_idx, (score, orig_idx, candidate) in enumerate(selected_items[:top_k], 1):
            candidate.final_score = round(score, 6)
            candidate.metadata["rerank_score"] = round(score, 6)
            candidate.metadata["original_rank"] = orig_idx
            candidate.metadata["rerank_rank"] = rank_idx
            candidate.metadata["reranker"] = self.name
            final_candidates.append(candidate)

        return final_candidates


# ── 3. Cross-Encoder Reranker ─────────────────────────────────────────

class CrossEncoderReranker(BaseReranker):
    """
    Reranks candidates using a joint cross-attention CrossEncoder model
    (e.g. cross-encoder/ms-marco-MiniLM-L-6-v2).
    """

    def __init__(
        self,
        model_name: str = RERANKER_MODEL,
        cross_encoder=None,
        default_threshold: float = RERANKER_MIN_SCORE,
    ):
        self.model_name = model_name
        self._cross_encoder = cross_encoder
        self.default_threshold = default_threshold

    def _get_model(self):
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder
            self._cross_encoder = CrossEncoder(self.model_name)
        return self._cross_encoder

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 3,
        threshold: Optional[float] = None,
        **kwargs,
    ) -> List[RetrievalResult]:
        if not results:
            return []

        min_score = threshold if threshold is not None else self.default_threshold
        encoder = self._get_model()

        # Build cross-attention pairs: (query, candidate_text)
        pairs = [[query, r.text] for r in results]
        raw_scores = encoder.predict(pairs)

        # CrossEncoder logits can be any real number; apply sigmoid for [0, 1] probability
        scored: List[Tuple[float, int, RetrievalResult]] = []
        for orig_idx, (r, raw_s) in enumerate(zip(results, raw_scores), 1):
            val = float(raw_s)
            prob = 1.0 / (1.0 + math.exp(-val)) if -50 < val < 50 else (1.0 if val >= 50 else 0.0)
            scored.append((prob, orig_idx, r))

        # Sort descending
        scored.sort(key=lambda item: item[0], reverse=True)

        # Filter by threshold with non-empty safeguard
        passed = [item for item in scored if item[0] >= min_score]
        if not passed and scored:
            passed = [scored[0]]

        final_candidates: List[RetrievalResult] = []
        for rank_idx, (score, orig_idx, candidate) in enumerate(passed[:top_k], 1):
            candidate.final_score = round(score, 6)
            candidate.metadata["rerank_score"] = round(score, 6)
            candidate.metadata["original_rank"] = orig_idx
            candidate.metadata["rerank_rank"] = rank_idx
            candidate.metadata["reranker"] = self.name
            final_candidates.append(candidate)

        return final_candidates


# ── Reranker Factory ──────────────────────────────────────────────────

def get_reranker(
    backend: Optional[str] = None,
    embedding_model=None,
    model_name: Optional[str] = None,
    threshold: Optional[float] = None,
) -> BaseReranker:
    """
    Factory function returning the configured BaseReranker instance.

    Parameters
    ----------
    backend         : "semantic", "cross_encoder", "none", or None (reads from config).
    embedding_model : Optional SentenceTransformer singleton for "semantic" backend.
    model_name      : Optional HuggingFace model name for "cross_encoder" backend.
    threshold       : Optional default threshold score.

    Returns
    -------
    BaseReranker instance.
    """
    if not RERANKER_ENABLED:
        logger.debug("[RerankerFactory] RERANKER_ENABLED=False. Using PassThroughReranker.")
        return PassThroughReranker()

    effective_backend = (backend or RERANKER_BACKEND or "semantic").lower().strip()
    min_score = threshold if threshold is not None else RERANKER_MIN_SCORE

    if effective_backend in {"none", "passthrough"}:
        return PassThroughReranker()

    if effective_backend == "cross_encoder":
        try:
            return CrossEncoderReranker(
                model_name=model_name or RERANKER_MODEL,
                default_threshold=min_score,
            )
        except Exception as exc:
            logger.warning(
                "[RerankerFactory] Failed to initialize CrossEncoderReranker (%s). Falling back to SemanticEmbeddingReranker.",
                exc,
            )
            return SemanticEmbeddingReranker(
                embedding_model=embedding_model,
                default_threshold=min_score,
            )

    # Default: "semantic"
    return SemanticEmbeddingReranker(
        embedding_model=embedding_model,
        default_threshold=min_score,
    )

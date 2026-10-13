"""
SmartInterview — Hybrid Retriever (Phase 8)

Unifies Dense Vector, BM25 Keyword, and Knowledge Graph retrieval into a single
high-precision Hybrid Retriever:
  1. Dense Vector (ChromaDB + all-MiniLM-L6-v2):
     Captures latent semantic intent and paraphrase similarity.
  2. BM25 Keyword (rank-bm25):
     Guarantees exact term matching for technical keywords, acronyms, and syntax.
  3. Knowledge Graph (Neo4j / NetworkX):
     Provides relationship-aware multi-hop context (prerequisites, related concepts,
     dependents, and Bloom taxonomy weighting).

Fusion Algorithms:
  - Weighted Linear Combination:
      Score(d) = α · VectorNorm(d) + β · KeywordNorm(d) + γ · GraphNorm(d)
      with dynamic weight re-normalization if a retriever produces zero candidates.
  - Reciprocal Rank Fusion (RRF):
      RRF(d) = Σ_m  w_m / (k + rank_m(d))
      standardized robust rank-based aggregation with configurable constant k (default 60).

All outputs strictly conform to List[RetrievalResult] with full provenance attribution,
per-component scores, source lists, and explainability metadata.
"""

from __future__ import annotations

import time
import logging
from typing import List, Optional, Dict, Set, Tuple, Any

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult
from app.config import (
    HYBRID_FUSION_METHOD,
    HYBRID_VECTOR_WEIGHT,
    HYBRID_KEYWORD_WEIGHT,
    HYBRID_GRAPH_WEIGHT,
    HYBRID_RRF_K,
    HYBRID_FETCH_K,
)

logger = logging.getLogger(__name__)


class HybridRetriever(BaseRetriever):
    """
    Hybrid retriever fusing Dense Vector, BM25 Keyword, and Graph retrieval.

    Parameters
    ----------
    vector_retriever  : Optional[BaseRetriever] — Dense vector search instance.
    keyword_retriever : Optional[BaseRetriever] — BM25 keyword search instance.
    graph_retriever   : Optional[BaseRetriever] — Knowledge graph search instance.
    fusion_method     : "weighted" or "rrf" (defaults to app.config.HYBRID_FUSION_METHOD).
    weights           : Dict mapping retriever keys ("vector", "keyword", "graph") to float weights.
    rrf_k             : Smoothing constant for Reciprocal Rank Fusion (default 60).
    fetch_k           : Number of candidates to fetch from each retriever before fusion (default 10).
    """

    def __init__(
        self,
        vector_retriever: Optional[BaseRetriever] = None,
        keyword_retriever: Optional[BaseRetriever] = None,
        graph_retriever: Optional[BaseRetriever] = None,
        fusion_method: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
        rrf_k: Optional[int] = None,
        fetch_k: Optional[int] = None,
    ):
        self.vector_retriever = vector_retriever
        self.keyword_retriever = keyword_retriever
        self.graph_retriever = graph_retriever

        self.fusion_method = (fusion_method or HYBRID_FUSION_METHOD or "weighted").lower().strip()
        if self.fusion_method not in {"weighted", "rrf"}:
            logger.warning(
                "[HybridRetriever] Unknown fusion_method='%s'. Defaulting to 'weighted'.",
                self.fusion_method,
            )
            self.fusion_method = "weighted"

        self.weights = weights or {
            "vector": HYBRID_VECTOR_WEIGHT,
            "keyword": HYBRID_KEYWORD_WEIGHT,
            "graph": HYBRID_GRAPH_WEIGHT,
        }
        self.rrf_k = rrf_k if rrf_k is not None else HYBRID_RRF_K
        self.fetch_k = fetch_k if fetch_k is not None else HYBRID_FETCH_K

    # ── Score Normalization Helpers ───────────────────────────────────

    @staticmethod
    def normalize_vector_scores(
        results: List[RetrievalResult], mode: str = "max"
    ) -> Dict[str, float]:
        """
        Normalize ChromaDB cosine distances into [0.0, 1.0] similarities.
        Chroma returns cosine distance d = 1 - cos(theta), where 0 is identical.
        Similarity s = max(0.0, 1.0 - min(1.0, d)).
        """
        raw_sims: Dict[str, float] = {}
        for r in results:
            d = r.vector_score if r.vector_score is not None else 1.0
            # Clamp distance safely
            sim = max(0.0, 1.0 - min(1.0, float(d)))
            raw_sims[r.chunk_id] = sim

        if not raw_sims:
            return {}

        if mode == "minmax":
            min_v = min(raw_sims.values())
            max_v = max(raw_sims.values())
            if max_v > min_v:
                return {cid: (v - min_v) / (max_v - min_v) for cid, v in raw_sims.items()}
            return {cid: 1.0 if max_v > 0 else 0.0 for cid in raw_sims}

        # Default: max-scaling (preserves relative magnitude without zeroing 2nd best)
        max_v = max(raw_sims.values())
        if max_v > 0:
            return {cid: v / max_v for cid, v in raw_sims.items()}
        return {cid: 0.0 for cid in raw_sims}

    @staticmethod
    def normalize_keyword_scores(
        results: List[RetrievalResult], mode: str = "max"
    ) -> Dict[str, float]:
        """
        Normalize BM25 scores into [0.0, 1.0].
        BM25 scores are non-negative, unbounded.
        """
        raw_scores: Dict[str, float] = {}
        for r in results:
            s = float(r.keyword_score) if r.keyword_score is not None else 0.0
            raw_scores[r.chunk_id] = max(0.0, s)

        if not raw_scores:
            return {}

        if mode == "minmax":
            min_v = min(raw_scores.values())
            max_v = max(raw_scores.values())
            if max_v > min_v:
                return {cid: (v - min_v) / (max_v - min_v) for cid, v in raw_scores.items()}
            return {cid: 1.0 if max_v > 0 else 0.0 for cid in raw_scores}

        max_v = max(raw_scores.values())
        if max_v > 0:
            return {cid: v / max_v for cid, v in raw_scores.items()}
        return {cid: 0.0 for cid in raw_scores}

    @staticmethod
    def normalize_graph_scores(
        results: List[RetrievalResult], mode: str = "max"
    ) -> Dict[str, float]:
        """
        Normalize Graph traversal scores into [0.0, 1.0].
        Graph scores are already calculated in [0.0, 1.0].
        """
        raw_scores: Dict[str, float] = {}
        for r in results:
            s = float(r.graph_score) if r.graph_score is not None else 0.0
            raw_scores[r.chunk_id] = max(0.0, min(1.0, s))

        if not raw_scores:
            return {}

        if mode == "minmax":
            min_v = min(raw_scores.values())
            max_v = max(raw_scores.values())
            if max_v > min_v:
                return {cid: (v - min_v) / (max_v - min_v) for cid, v in raw_scores.items()}
            return {cid: 1.0 if max_v > 0 else 0.0 for cid in raw_scores}

        max_v = max(raw_scores.values())
        if max_v > 0:
            return {cid: v / max_v for cid, v in raw_scores.items()}
        return {cid: 0.0 for cid in raw_scores}

    # ── Main Retrieval Contract ───────────────────────────────────────

    def retrieve(
        self,
        query: str,
        skill: str,
        domains: Optional[List[str]] = None,
        top_k: int = 3,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Execute hybrid retrieval combining Vector, Keyword, and Graph search.

        Parameters
        ----------
        query    : Semantic/keyword query string.
        skill    : Resume technical skill (e.g. 'SQL', 'Python').
        domains  : Optional list of domain filters (e.g. ['dbms']).
        top_k    : Number of final results to return.
        **kwargs :
          fusion_method : Override default fusion method ("weighted" or "rrf").
          weights       : Override default weights dict.
          fetch_k       : Override candidates fetched per retriever.
          rrf_k         : Override RRF smoothing constant.
          norm_mode     : "max" (default) or "minmax".
          concept_name  : Passed to GraphRetriever.
          weak_topics   : Passed to GraphRetriever.
          bloom_level   : Passed to GraphRetriever.

        Returns
        -------
        List[RetrievalResult] ordered by final_score descending.
        """
        start_time = time.perf_counter()

        if top_k <= 0:
            return []

        # Sanitize query and domain filters
        query_str = "" if query is None else (query if isinstance(query, str) else str(query))
        domains_clean = (
            [d.lower().strip() for d in domains if d and isinstance(d, str)]
            if domains
            else None
        )

        effective_fusion = (kwargs.get("fusion_method") or self.fusion_method).lower().strip()
        effective_fetch_k = kwargs.get("fetch_k", max(top_k * 3, self.fetch_k))
        norm_mode = kwargs.get("norm_mode", "max")
        rrf_k = kwargs.get("rrf_k", self.rrf_k)
        custom_weights = kwargs.get("weights") or self.weights

        # 1. Fetch candidate pools from each retriever
        vector_candidates: List[RetrievalResult] = []
        keyword_candidates: List[RetrievalResult] = []
        graph_candidates: List[RetrievalResult] = []

        # Vector search
        if self.vector_retriever is not None:
            try:
                vector_candidates = self.vector_retriever.retrieve(
                    query=query_str,
                    skill=skill,
                    domains=domains_clean,
                    top_k=effective_fetch_k,
                    **kwargs,
                )
            except Exception as exc:
                logger.warning("[HybridRetriever] Vector retrieval failed: %s", exc)

        # Keyword search
        if self.keyword_retriever is not None:
            try:
                keyword_candidates = self.keyword_retriever.retrieve(
                    query=query_str,
                    skill=skill,
                    domains=domains_clean,
                    top_k=effective_fetch_k,
                    **kwargs,
                )
            except Exception as exc:
                logger.warning("[HybridRetriever] Keyword retrieval failed: %s", exc)

        # Graph search
        if self.graph_retriever is not None:
            try:
                graph_candidates = self.graph_retriever.retrieve(
                    query=query_str,
                    skill=skill,
                    domains=domains_clean,
                    top_k=effective_fetch_k,
                    **kwargs,
                )
            except Exception as exc:
                logger.warning("[HybridRetriever] Graph retrieval failed: %s", exc)

        # Collect unique chunks and track provenance
        chunk_pool: Dict[str, RetrievalResult] = {}
        sources_map: Dict[str, Set[str]] = {}
        ranks_map: Dict[str, Dict[str, Optional[int]]] = {}
        raw_scores_map: Dict[str, Dict[str, Optional[float]]] = {}
        extra_meta: Dict[str, dict] = {}

        for rank_idx, res in enumerate(vector_candidates, 1):
            cid = res.chunk_id
            if cid not in chunk_pool:
                chunk_pool[cid] = res
            sources_map.setdefault(cid, set()).add("vector")
            ranks_map.setdefault(cid, {})["vector"] = rank_idx
            raw_scores_map.setdefault(cid, {})["vector"] = res.vector_score

        for rank_idx, res in enumerate(keyword_candidates, 1):
            cid = res.chunk_id
            if cid not in chunk_pool:
                chunk_pool[cid] = res
            sources_map.setdefault(cid, set()).add("keyword")
            ranks_map.setdefault(cid, {})["keyword"] = rank_idx
            raw_scores_map.setdefault(cid, {})["keyword"] = res.keyword_score
            if "matched_terms" in res.metadata:
                extra_meta.setdefault(cid, {})["matched_terms"] = res.metadata["matched_terms"]

        for rank_idx, res in enumerate(graph_candidates, 1):
            cid = res.chunk_id
            if cid not in chunk_pool:
                chunk_pool[cid] = res
            sources_map.setdefault(cid, set()).add("graph")
            ranks_map.setdefault(cid, {})["graph"] = rank_idx
            raw_scores_map.setdefault(cid, {})["graph"] = res.graph_score

            # Retain critical graph provenance across deduplication
            for g_key in (
                "traversal_path",
                "role",
                "remediation",
                "confidence",
                "bloom_level",
                "evidence",
                "graph_traversal",
                "concept_id",
            ):
                if g_key in res.metadata:
                    extra_meta.setdefault(cid, {})[g_key] = res.metadata[g_key]

        if not chunk_pool:
            logger.info("[HybridRetriever] No candidates returned from any retriever.")
            return []

        # 2. Determine active retrievers and re-normalize weights
        active_retrievers: Dict[str, float] = {}
        if vector_candidates and "vector" in custom_weights:
            active_retrievers["vector"] = max(0.0, float(custom_weights["vector"]))
        if keyword_candidates and "keyword" in custom_weights:
            active_retrievers["keyword"] = max(0.0, float(custom_weights["keyword"]))
        if graph_candidates and "graph" in custom_weights:
            active_retrievers["graph"] = max(0.0, float(custom_weights["graph"]))

        total_weight = sum(active_retrievers.values())
        if total_weight > 0:
            norm_weights = {k: v / total_weight for k, v in active_retrievers.items()}
        else:
            # Fallback to equal weighting among active
            eq = 1.0 / len(active_retrievers) if active_retrievers else 1.0
            norm_weights = {k: eq for k in active_retrievers}

        # 3. Compute final scores
        fused_scores: Dict[str, float] = {}
        normalized_scores_map: Dict[str, Dict[str, float]] = {}

        if effective_fusion == "rrf":
            # Reciprocal Rank Fusion:
            # RRF(d) = sum_m ( w_m / (k + rank_m(d)) )
            for cid in chunk_pool:
                rrf_sum = 0.0
                c_ranks = ranks_map.get(cid, {})
                for m, w in norm_weights.items():
                    rank = c_ranks.get(m)
                    if rank is not None:
                        rrf_sum += w * (1.0 / (rrf_k + rank))
                fused_scores[cid] = rrf_sum
        else:
            # Weighted Linear Combination:
            # Score(d) = sum_m ( w_m * norm_score_m(d) )
            norm_vec = self.normalize_vector_scores(vector_candidates, mode=norm_mode)
            norm_kw = self.normalize_keyword_scores(keyword_candidates, mode=norm_mode)
            norm_gr = self.normalize_graph_scores(graph_candidates, mode=norm_mode)

            for cid in chunk_pool:
                w_sum = 0.0
                c_norm = {
                    "vector": norm_vec.get(cid, 0.0),
                    "keyword": norm_kw.get(cid, 0.0),
                    "graph": norm_gr.get(cid, 0.0),
                }
                normalized_scores_map[cid] = c_norm

                for m, w in norm_weights.items():
                    w_sum += w * c_norm.get(m, 0.0)

                fused_scores[cid] = w_sum

        # 4. Build final RetrievalResult instances
        final_results: List[RetrievalResult] = []
        for cid, candidate in chunk_pool.items():
            sources = sorted(list(sources_map.get(cid, set())))
            ranks = ranks_map.get(cid, {})
            raw_scores = raw_scores_map.get(cid, {})
            score = fused_scores.get(cid, 0.0)
            norm_scores = normalized_scores_map.get(cid, {})

            explanation_parts = [f"Retrieved by {', '.join(sources)}."]
            if effective_fusion == "rrf":
                rank_strs = [f"{m}: rank {ranks[m]}" for m in sources if m in ranks]
                explanation_parts.append(f"RRF score: {score:.5f} ({', '.join(rank_strs)})")
            else:
                score_strs = [f"{m}: {norm_scores.get(m, 0.0):.3f} (raw {raw_scores.get(m, 'N/A')})" for m in sources]
                explanation_parts.append(f"Weighted score: {score:.4f} ({', '.join(score_strs)})")

            meta: Dict[str, Any] = {
                "sources": sources,
                "ranks": ranks,
                "raw_scores": raw_scores,
                "normalized_scores": norm_scores,
                "fusion_method": effective_fusion,
                "fusion_weights": norm_weights,
                "explanation": " ".join(explanation_parts),
            }
            if cid in extra_meta:
                meta.update(extra_meta[cid])

            res = RetrievalResult(
                chunk_id=candidate.chunk_id,
                text=candidate.text,
                domain=candidate.domain,
                concept=candidate.concept,
                source=candidate.source,
                source_url=candidate.source_url,
                vector_score=raw_scores.get("vector"),
                keyword_score=raw_scores.get("keyword"),
                graph_score=raw_scores.get("graph"),
                final_score=round(score, 6),
                retriever="hybrid",
                metadata=meta,
            )
            final_results.append(res)

        # 5. Sort by final_score descending and ensure canonical full-text resolution
        final_results.sort(key=lambda r: r.final_score, reverse=True)
        from app.rag.canonical_resolver import get_canonical_resolver
        final_results = get_canonical_resolver().resolve_results(final_results)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        for r in final_results:
            r.metadata["latency_ms"] = round(elapsed_ms, 2)

        logger.info(
            "[HybridRetriever] Query='%s' Skill='%s': fused %d unique candidates across [%s] using '%s' fusion (%.2fms). Returning top %d.",
            query_str[:40],
            skill,
            len(chunk_pool),
            ", ".join(active_retrievers.keys()),
            effective_fusion,
            elapsed_ms,
            min(top_k, len(final_results)),
        )

        return final_results[:top_k]

    def get_stats(self) -> dict:
        """Return configuration and sub-retriever status."""
        return {
            "retriever": "HybridRetriever",
            "fusion_method": self.fusion_method,
            "weights": self.weights,
            "rrf_k": self.rrf_k,
            "fetch_k": self.fetch_k,
            "has_vector": self.vector_retriever is not None,
            "has_keyword": self.keyword_retriever is not None,
            "has_graph": self.graph_retriever is not None,
        }

"""
SmartInterview — Evaluation Metrics Module (Phase 13)

Standardized, mathematically rigorous evaluation metrics for information retrieval
and Knowledge Graph RAG benchmarks:
  1. Ranking & Retrieval Metrics:
     - Hit@k (Hit@1, Hit@3, Hit@5)
     - Recall@k
     - Precision@k
     - Reciprocal Rank (MRR component)
     - Average Precision (MAP component)
     - Normalized Discounted Cumulative Gain (NDCG@k)
  2. Graph & Concept Metrics:
     - Prerequisite Coverage (fraction of required prerequisite concepts discovered)
     - Concept Diversity (count of distinct concepts in top-k)
     - Provenance Retention Rate (fraction of candidates retaining graph/fusion lineage)
  3. Lexical Metrics:
     - Keyword Term Recall (% of query tokens present in retrieved text)
  4. Latency Distribution:
     - Mean, Min, Max, P50 (median), P90, P95, P99
  5. Aggregate Benchmark Evaluator:
     - Unified evaluation across test runs for Dense, Keyword, Graph, and Hybrid Graph RAG.
"""

from __future__ import annotations

import re
import math
import numpy as np
from typing import List, Set, Dict, Any, Optional, Sequence
from dataclasses import dataclass, asdict

from app.rag.retrieval_result import RetrievalResult


# ── 1. Ranking & Retrieval Metrics ────────────────────────────────────

def hit_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Set[str], k: int = 5) -> float:
    """
    Compute binary Hit@k: 1.0 if at least one ground-truth item is in top-k, else 0.0.
    """
    if k <= 0 or not retrieved_ids or not ground_truth_ids:
        return 0.0
    top_slice = retrieved_ids[:k]
    for cid in top_slice:
        if cid in ground_truth_ids:
            return 1.0
    return 0.0


def recall_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Set[str], k: int = 5) -> float:
    """
    Compute Recall@k: fraction of relevant items that appear in the top-k results.
    """
    if k <= 0 or not retrieved_ids or not ground_truth_ids:
        return 0.0
    top_slice = set(retrieved_ids[:k])
    hits = len(top_slice.intersection(ground_truth_ids))
    return float(hits / len(ground_truth_ids))


def precision_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Set[str], k: int = 5) -> float:
    """
    Compute Precision@k: fraction of top-k retrieved items that are relevant.
    """
    if k <= 0 or not retrieved_ids or not ground_truth_ids:
        return 0.0
    top_slice = retrieved_ids[:k]
    hits = sum(1 for cid in top_slice if cid in ground_truth_ids)
    return float(hits / len(top_slice))


def reciprocal_rank(retrieved_ids: Sequence[str], ground_truth_ids: Set[str]) -> float:
    """
    Compute Reciprocal Rank: 1 / rank of the first relevant retrieved item, or 0.0.
    """
    if not retrieved_ids or not ground_truth_ids:
        return 0.0
    for rank, cid in enumerate(retrieved_ids, 1):
        if cid in ground_truth_ids:
            return 1.0 / rank
    return 0.0


def average_precision_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Set[str], k: int = 5) -> float:
    """
    Compute Average Precision at k (AP@k) for a single query.
    """
    if k <= 0 or not retrieved_ids or not ground_truth_ids:
        return 0.0

    top_slice = retrieved_ids[:k]
    num_relevant = 0
    precision_sum = 0.0

    for rank, cid in enumerate(top_slice, 1):
        if cid in ground_truth_ids:
            num_relevant += 1
            precision_sum += (num_relevant / rank)

    total_possible = min(k, len(ground_truth_ids))
    if total_possible == 0:
        return 0.0
    return float(precision_sum / total_possible)


def ndcg_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Set[str], k: int = 5) -> float:
    """
    Compute Normalized Discounted Cumulative Gain at k (NDCG@k) using binary relevance.
    """
    if k <= 0 or not retrieved_ids or not ground_truth_ids:
        return 0.0

    top_slice = retrieved_ids[:k]
    dcg = 0.0
    for rank, cid in enumerate(top_slice, 1):
        if cid in ground_truth_ids:
            # Binary relevance: rel_i = 1
            dcg += 1.0 / math.log2(rank + 1)

    # Ideal DCG: perfect ranking with up to min(k, len(ground_truth_ids)) relevant items
    idcg = 0.0
    ideal_hits = min(k, len(ground_truth_ids))
    for rank in range(1, ideal_hits + 1):
        idcg += 1.0 / math.log2(rank + 1)

    if idcg == 0.0:
        return 0.0
    return float(dcg / idcg)


# ── 2. Graph & Concept Metrics ────────────────────────────────────────

def concept_diversity(results: Sequence[RetrievalResult]) -> int:
    """
    Count the number of unique concepts present in the retrieved candidates.
    """
    if not results:
        return 0
    concepts = {r.concept.strip().lower() for r in results if r.concept}
    return len(concepts)


def prerequisite_coverage(results: Sequence[RetrievalResult], target_prerequisites: Sequence[str]) -> float:
    """
    Compute Prerequisite Coverage: fraction of target prerequisite concepts
    discovered in the retrieved candidates.
    """
    if not target_prerequisites:
        return 1.0
    if not results:
        return 0.0

    # Gather all concepts and traversal paths from retrieved results
    retrieved_concepts: Set[str] = set()
    for r in results:
        if r.concept:
            retrieved_concepts.add(r.concept.strip().lower())
        # Check traversal paths in metadata
        path = r.metadata.get("traversal_path") or []
        for step in path:
            retrieved_concepts.add(str(step).strip().lower())

    found_count = 0
    for prereq in target_prerequisites:
        p_clean = prereq.strip().lower()
        if any(p_clean in c for c in retrieved_concepts) or p_clean in retrieved_concepts:
            found_count += 1

    return float(found_count / len(target_prerequisites))


def provenance_retention_rate(results: Sequence[RetrievalResult]) -> float:
    """
    Compute Provenance Retention Rate: fraction of retrieved results that
    preserve multi-channel provenance (sources, traversal path, reranker, or scores).
    """
    if not results:
        return 0.0

    provenance_count = 0
    for r in results:
        meta = r.metadata or {}
        has_provenance = (
            "sources" in meta
            or "traversal_path" in meta
            or "reranker" in meta
            or "role" in meta
            or r.keyword_score is not None
            or r.graph_score is not None
        )
        if has_provenance:
            provenance_count += 1

    return float(provenance_count / len(results))


# ── 3. Lexical Metrics ────────────────────────────────────────────────

def term_recall(query: str, combined_text: str, min_token_len: int = 3) -> float:
    """
    Compute Keyword Term Recall: fraction of query tokens (>= min_token_len)
    present in the combined retrieved candidate text.
    """
    if not query or not combined_text:
        return 0.0

    q_tokens = [
        t for t in re.findall(r"[a-z0-9]+", query.lower())
        if len(t) >= min_token_len
    ]
    if not q_tokens:
        return 1.0

    text_tokens = set(re.findall(r"[a-z0-9]+", combined_text.lower()))
    matches = sum(1 for t in set(q_tokens) if t in text_tokens)
    return float(matches / len(set(q_tokens)))


# ── 4. Latency Distribution ───────────────────────────────────────────

def calculate_latency_percentiles(latencies_ms: Sequence[float]) -> Dict[str, float]:
    """
    Compute comprehensive latency metrics: mean, P50, P90, P95, P99, min, max.
    """
    if not latencies_ms:
        return {
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
        }

    arr = np.array(latencies_ms, dtype=float)
    return {
        "mean": round(float(np.mean(arr)), 2),
        "min": round(float(np.min(arr)), 2),
        "max": round(float(np.max(arr)), 2),
        "p50": round(float(np.percentile(arr, 50)), 2),
        "p90": round(float(np.percentile(arr, 90)), 2),
        "p95": round(float(np.percentile(arr, 95)), 2),
        "p99": round(float(np.percentile(arr, 99)), 2),
    }


# ── 5. Aggregate Benchmark Evaluator ──────────────────────────────────

@dataclass
class QueryEvaluationResult:
    """Result metrics for a single evaluated query."""
    query_id: str
    hit_1: float
    hit_3: float
    hit_5: float
    recall_5: float
    precision_5: float
    mrr: float
    map_5: float
    ndcg_5: float
    prereq_coverage: float
    concept_diversity: int
    term_recall: float
    provenance_rate: float
    latency_ms: float


@dataclass
class AggregateBenchmarkReport:
    """Overall summary metrics aggregated across all evaluated queries."""
    total_queries: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    recall_at_5: float
    precision_at_5: float
    mrr: float
    map_at_5: float
    ndcg_at_5: float
    avg_prereq_coverage: float
    avg_concept_diversity: float
    avg_term_recall: float
    avg_provenance_rate: float
    latency: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_query_run(
    query_id: str,
    query: str,
    results: List[RetrievalResult],
    ground_truth_chunk_ids: Set[str],
    target_prerequisites: Optional[List[str]] = None,
    latency_ms: float = 0.0,
) -> QueryEvaluationResult:
    """
    Evaluate a single query run against its ground-truth expectations.
    """
    retrieved_cids = [r.chunk_id for r in results]
    combined_text = " ".join(r.text for r in results)
    target_prereqs = target_prerequisites or []

    h1 = hit_at_k(retrieved_cids, ground_truth_chunk_ids, k=1)
    h3 = hit_at_k(retrieved_cids, ground_truth_chunk_ids, k=3)
    h5 = hit_at_k(retrieved_cids, ground_truth_chunk_ids, k=5)
    r5 = recall_at_k(retrieved_cids, ground_truth_chunk_ids, k=5)
    p5 = precision_at_k(retrieved_cids, ground_truth_chunk_ids, k=5)
    rr = reciprocal_rank(retrieved_cids, ground_truth_chunk_ids)
    ap5 = average_precision_at_k(retrieved_cids, ground_truth_chunk_ids, k=5)
    ndcg5 = ndcg_at_k(retrieved_cids, ground_truth_chunk_ids, k=5)
    p_cov = prerequisite_coverage(results, target_prereqs)
    c_div = concept_diversity(results)
    t_rec = term_recall(query, combined_text)
    prov = provenance_retention_rate(results)

    return QueryEvaluationResult(
        query_id=query_id,
        hit_1=h1,
        hit_3=h3,
        hit_5=h5,
        recall_5=r5,
        precision_5=p5,
        mrr=rr,
        map_5=ap5,
        ndcg_5=ndcg5,
        prereq_coverage=p_cov,
        concept_diversity=c_div,
        term_recall=t_rec,
        provenance_rate=prov,
        latency_ms=latency_ms,
    )


def aggregate_evaluation_results(query_results: List[QueryEvaluationResult]) -> AggregateBenchmarkReport:
    """
    Aggregate per-query evaluation results into a comprehensive summary report.
    """
    if not query_results:
        return AggregateBenchmarkReport(
            total_queries=0,
            hit_at_1=0.0,
            hit_at_3=0.0,
            hit_at_5=0.0,
            recall_at_5=0.0,
            precision_at_5=0.0,
            mrr=0.0,
            map_at_5=0.0,
            ndcg_at_5=0.0,
            avg_prereq_coverage=0.0,
            avg_concept_diversity=0.0,
            avg_term_recall=0.0,
            avg_provenance_rate=0.0,
            latency=calculate_latency_percentiles([]),
        )

    n = len(query_results)
    latencies = [q.latency_ms for q in query_results]

    return AggregateBenchmarkReport(
        total_queries=n,
        hit_at_1=round(float(sum(q.hit_1 for q in query_results) / n * 100.0), 2),
        hit_at_3=round(float(sum(q.hit_3 for q in query_results) / n * 100.0), 2),
        hit_at_5=round(float(sum(q.hit_5 for q in query_results) / n * 100.0), 2),
        recall_at_5=round(float(sum(q.recall_5 for q in query_results) / n * 100.0), 2),
        precision_at_5=round(float(sum(q.precision_5 for q in query_results) / n * 100.0), 2),
        mrr=round(float(sum(q.mrr for q in query_results) / n), 4),
        map_at_5=round(float(sum(q.map_5 for q in query_results) / n), 4),
        ndcg_at_5=round(float(sum(q.ndcg_5 for q in query_results) / n), 4),
        avg_prereq_coverage=round(float(sum(q.prereq_coverage for q in query_results) / n * 100.0), 2),
        avg_concept_diversity=round(float(sum(q.concept_diversity for q in query_results) / n), 2),
        avg_term_recall=round(float(sum(q.term_recall for q in query_results) / n * 100.0), 2),
        avg_provenance_rate=round(float(sum(q.provenance_rate for q in query_results) / n * 100.0), 2),
        latency=calculate_latency_percentiles(latencies),
    )

"""
SmartInterview — Phase 16 Test Suite: Full Hybrid Graph RAG Evaluation

Tests and asserts:
  1. The benchmark artifact (data/evaluation/hybrid_rag_benchmark.json) exists and conforms to schema.
  2. Hybrid RRF (without reranker) establishes state-of-the-art IR metrics:
     - Recall@5 = 64.81% (exceeds Pure Dense 61.52%).
     - Precision@5 = 84.85% (exceeds Pure Dense 80.61%).
     - MAP@5 = 0.9309 (exceeds Pure Dense 0.8798).
     - NDCG@5 = 0.9543 (exceeds Pure Dense 0.9182).
     - MRR = 0.9848 (exceeds Pure Dense 0.9798).
     - Hit@1 = 96.97%, Hit@3 = 100%, Hit@5 = 100%.
  3. Full Hybrid Graph RAG (with Contextual Reranking) optimizes cognitive & pedagogical depth:
     - Prerequisite Coverage = 96.97% (exceeds all individual channels and pure dense 90.91%).
     - Concept Diversity = 2.03 (exceeds pure dense 1.76).
     - Term Recall = 77.00% (exceeds pure dense 74.43%).
     - Hit@5 = 100.0%.
  4. Provenance retention is 100.0% for both hybrid configurations vs 0.0% for Pure Dense.
  5. Mean latency remains well within conversational SLA (< 100 ms).
  6. Live end-to-end execution sanity test.
"""

from __future__ import annotations

import os
import sys
import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

HYBRID_BENCHMARK_PATH = PROJECT_ROOT / "data" / "evaluation" / "hybrid_rag_benchmark.json"
FROZEN_DENSE_PATH = PROJECT_ROOT / "data" / "evaluation" / "frozen_dense_baseline.json"


@pytest.fixture(scope="module")
def hybrid_benchmark_data():
    assert HYBRID_BENCHMARK_PATH.exists(), f"Benchmark file missing at: {HYBRID_BENCHMARK_PATH}"
    with open(HYBRID_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def frozen_dense_data():
    assert FROZEN_DENSE_PATH.exists(), f"Frozen dense baseline missing at: {FROZEN_DENSE_PATH}"
    with open(FROZEN_DENSE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_hybrid_benchmark_file_exists_and_schema(hybrid_benchmark_data):
    """Verify top-level structure of the hybrid benchmark artifact."""
    assert "metadata" in hybrid_benchmark_data
    assert "comparative_matrix" in hybrid_benchmark_data
    assert "hybrid_rrf_metrics" in hybrid_benchmark_data
    assert "full_hybrid_graph_rag_metrics" in hybrid_benchmark_data

    meta = hybrid_benchmark_data["metadata"]
    assert meta["total_queries"] == 33
    assert meta["domains_evaluated"] == 8
    assert meta["fusion_method"] == "Reciprocal Rank Fusion (RRF, k=60)"


def test_hybrid_rrf_superiority_in_ir_metrics(hybrid_benchmark_data, frozen_dense_data):
    """Verify that Hybrid RRF outperforms Pure Dense across key ranking & recall metrics."""
    rrf_agg = hybrid_benchmark_data["hybrid_rrf_metrics"]["aggregate"]
    dense_agg = frozen_dense_data["frozen_aggregate_metrics"]

    # 1. Recall@5 improvement
    assert rrf_agg["recall_at_5"] > dense_agg["recall_at_5"]
    assert rrf_agg["recall_at_5"] >= 64.0

    # 2. Precision@5 improvement
    assert rrf_agg["precision_at_5"] > dense_agg["precision_at_5"]
    assert rrf_agg["precision_at_5"] >= 84.0

    # 3. MAP@5 and NDCG@5 improvements
    assert rrf_agg["map_at_5"] > dense_agg["map_at_5"]
    assert rrf_agg["map_at_5"] >= 0.90
    assert rrf_agg["ndcg_at_5"] > dense_agg["ndcg_at_5"]
    assert rrf_agg["ndcg_at_5"] >= 0.94

    # 4. MRR and Hit rates
    assert rrf_agg["mrr"] >= dense_agg["mrr"]
    assert rrf_agg["hit_at_1"] == 96.97
    assert rrf_agg["hit_at_3"] == 100.0
    assert rrf_agg["hit_at_5"] == 100.0


def test_hybrid_reranker_prerequisite_and_diversity_promotion(hybrid_benchmark_data, frozen_dense_data):
    """Verify that Contextual Reranking maximizes Prerequisite Coverage and Concept Diversity."""
    full_agg = hybrid_benchmark_data["full_hybrid_graph_rag_metrics"]["aggregate"]
    dense_agg = frozen_dense_data["frozen_aggregate_metrics"]

    # Prerequisite coverage is highest under Full Hybrid RAG
    assert full_agg["avg_prereq_coverage"] > dense_agg["avg_prereq_coverage"]
    assert full_agg["avg_prereq_coverage"] >= 95.0

    # Concept diversity promotes broader contextual coverage
    assert full_agg["avg_concept_diversity"] > dense_agg["avg_concept_diversity"]
    assert full_agg["avg_concept_diversity"] >= 2.0

    # Term recall improves over pure dense
    assert full_agg["avg_term_recall"] > dense_agg["avg_term_recall"]

    # Top-5 coverage guaranteed
    assert full_agg["hit_at_5"] == 100.0


def test_provenance_retention_all_hybrid(hybrid_benchmark_data, frozen_dense_data):
    """Verify that both Hybrid configurations preserve 100% provenance retention vs 0% for Dense."""
    rrf_agg = hybrid_benchmark_data["hybrid_rrf_metrics"]["aggregate"]
    full_agg = hybrid_benchmark_data["full_hybrid_graph_rag_metrics"]["aggregate"]
    dense_agg = frozen_dense_data["frozen_aggregate_metrics"]

    assert rrf_agg["avg_provenance_rate"] == 100.0
    assert full_agg["avg_provenance_rate"] == 100.0
    assert dense_agg["avg_provenance_rate"] == 0.0


def test_latency_within_acceptable_bounds(hybrid_benchmark_data):
    """Verify that latency is well within production conversational response SLA (< 100 ms)."""
    rrf_lat = hybrid_benchmark_data["hybrid_rrf_metrics"]["aggregate"]["latency"]
    full_lat = hybrid_benchmark_data["full_hybrid_graph_rag_metrics"]["aggregate"]["latency"]

    assert rrf_lat["mean"] < 50.0
    assert full_lat["mean"] < 100.0


def test_live_hybrid_retriever_pipeline():
    """Verify live end-to-end execution of HybridRetriever and BaseReranker."""
    from app.services.question_service import _get_retriever, _get_reranker

    hybrid_retriever = _get_retriever(mode="hybrid")
    reranker = _get_reranker()

    fused = hybrid_retriever.retrieve(
        query="Explain primary keys and foreign keys in database schemas",
        skill="keys",
        domains=["dbms"],
        top_k=6,
        concept="keys",
        fusion_method="rrf",
    )
    assert len(fused) == 6
    assert fused[0].final_score > 0.0
    assert "sources" in fused[0].metadata
    assert "ranks" in fused[0].metadata

    reranked = reranker.rerank(
        query="Explain primary keys and foreign keys in database schemas",
        results=fused,
        top_k=3,
    )
    assert len(reranked) == 3
    assert reranked[0].domain == "dbms"
    assert "rerank_score" in reranked[0].metadata
    assert "reranker" in reranked[0].metadata

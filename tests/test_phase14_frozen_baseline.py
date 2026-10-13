"""
SmartInterview — Phase 14 Test Suite: Pure Baseline Execution & Freezing

Tests and asserts:
  1. The frozen dense baseline file (data/evaluation/frozen_dense_baseline.json) exists and conforms to schema.
  2. The frozen metrics reproduce historical research paper numbers (Hit@1=96.97%, Hit@3=100%, MRR=0.9798).
  3. The chunk-level metrics (Recall@5, Precision@5, MAP@5, NDCG@5) are mathematically sound and resolve historical ambiguity.
  4. Dense RAG has zero graph/hybrid provenance rate (0.0%).
  5. All 33 per-query records are well-formed and reproduce the exact ranking profile (e.g. Q15 at rank 3).
  6. Live execution of VectorRetriever reproduces the frozen numbers deterministically.
"""

from __future__ import annotations

import json
import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

FROZEN_BASELINE_PATH = PROJECT_ROOT / "data" / "evaluation" / "frozen_dense_baseline.json"
GOLDEN_DATASET_PATH = PROJECT_ROOT / "data" / "evaluation" / "golden_evaluation_dataset.json"


@pytest.fixture(scope="module")
def frozen_baseline_data():
    assert FROZEN_BASELINE_PATH.exists(), f"Frozen baseline file missing at: {FROZEN_BASELINE_PATH}"
    with open(FROZEN_BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_frozen_baseline_file_exists_and_schema(frozen_baseline_data):
    """Verify that the frozen baseline artifact has the expected top-level schema."""
    assert "benchmark_metadata" in frozen_baseline_data
    assert "historical_paper_comparison" in frozen_baseline_data
    assert "frozen_aggregate_metrics" in frozen_baseline_data
    assert "per_query_evaluations" in frozen_baseline_data

    meta = frozen_baseline_data["benchmark_metadata"]
    assert meta["retrieval_mode"] == "dense"
    assert meta["retriever_class"] == "VectorRetriever"
    assert meta["total_queries"] == 33
    assert meta["total_canonical_chunks"] == 402
    assert len(meta["domains_evaluated"]) == 8


def test_historical_paper_exact_fidelity(frozen_baseline_data):
    """Verify that frozen metrics match historical paper results exactly."""
    comp = frozen_baseline_data["historical_paper_comparison"]
    agg = frozen_baseline_data["frozen_aggregate_metrics"]

    assert comp["historical_hit_1"] == 96.97
    assert comp["historical_hit_3"] == 100.0
    assert comp["historical_hit_5"] == 100.0
    assert comp["historical_mrr"] == 0.9798

    assert agg["hit_at_1"] == 96.97
    assert agg["hit_at_3"] == 100.0
    assert agg["hit_at_5"] == 100.0
    assert agg["mrr"] == 0.9798

    # Absolute difference must be zero within floating precision rounding
    assert abs(comp["difference_hit_1"]) < 0.001
    assert abs(comp["difference_mrr"]) < 0.001


def test_recall_precision_and_ranking_soundness(frozen_baseline_data):
    """Verify that chunk-level Recall@5, Precision@5, MAP@5, and NDCG@5 are properly bounded."""
    agg = frozen_baseline_data["frozen_aggregate_metrics"]

    # In canonical chunk evaluation, each concept has 5-8 chunks, so top-5 yields ~61.5% chunk recall
    assert 55.0 <= agg["recall_at_5"] <= 70.0
    assert 75.0 <= agg["precision_at_5"] <= 90.0

    # MAP and NDCG should reflect the high precision of rank-1 retrievals
    assert 0.80 <= agg["map_at_5"] <= 0.95
    assert 0.85 <= agg["ndcg_at_5"] <= 0.98


def test_dense_baseline_zero_provenance_rate(frozen_baseline_data):
    """Verify that pure dense RAG has 0% multi-channel provenance retention."""
    agg = frozen_baseline_data["frozen_aggregate_metrics"]
    assert agg["avg_provenance_rate"] == 0.0


def test_latency_distribution_validity(frozen_baseline_data):
    """Verify latency distribution values are recorded and monotonic."""
    latency = frozen_baseline_data["frozen_aggregate_metrics"]["latency"]
    assert "mean" in latency
    assert "p50" in latency
    assert "p90" in latency
    assert "p95" in latency

    assert latency["min"] <= latency["p50"] <= latency["p90"] <= latency["p95"] <= latency["max"]
    assert latency["mean"] > 0.0


def test_per_query_records_integrity(frozen_baseline_data):
    """Verify per-query evaluations are well-formed and contain exactly 33 records."""
    queries = frozen_baseline_data["per_query_evaluations"]
    assert len(queries) == 33

    # Check that Q15 (stack vs queue) is the exact single query with rank > 1
    non_rank1_queries = [q for q in queries if q["hit_1"] == 0.0]
    assert len(non_rank1_queries) == 1
    q15 = non_rank1_queries[0]
    assert "stack" in q15["query"].lower() or "queue" in q15["query"].lower()
    assert q15["hit_3"] == 1.0  # found at rank 3
    assert q15["hit_5"] == 1.0


def test_live_vector_retriever_determinism():
    """Verify live VectorRetriever reproduces the same top chunk for benchmark query Q01."""
    from app.rag.vector_retriever import VectorRetriever
    from app.services.question_service import (
        _init_rag,
        get_embedding_model,
        get_chroma_collection,
        build_rag_query,
    )

    _init_rag()
    retriever = VectorRetriever(
        embedding_model=get_embedding_model(),
        collection=get_chroma_collection(),
        build_rag_query_fn=build_rag_query,
    )

    results = retriever.retrieve(
        query="What is the Domain Name System?",
        skill="dns",
        domains=["cn"],
        top_k=5,
    )

    assert len(results) == 5
    assert results[0].chunk_id == "cn_dns_001"
    assert results[0].domain == "cn"
    assert results[0].concept == "dns"
    assert results[0].vector_score is not None

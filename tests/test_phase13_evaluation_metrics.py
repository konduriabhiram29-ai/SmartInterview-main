"""
SmartInterview — Phase 13 Tests: Evaluation Methodology & Metrics Implementation

Comprehensive unit test suite verifying:
  1. Ranking & Retrieval Metrics:
     - hit_at_k (Hit@1, Hit@3, Hit@5)
     - recall_at_k
     - precision_at_k
     - reciprocal_rank (MRR)
     - average_precision_at_k (MAP)
     - ndcg_at_k (NDCG)
  2. Graph & Concept Metrics:
     - concept_diversity
     - prerequisite_coverage
     - provenance_retention_rate
  3. Lexical Metrics:
     - term_recall
  4. Latency Distribution:
     - calculate_latency_percentiles (mean, min, max, P50, P90, P95, P99)
  5. End-to-End Aggregation:
     - evaluate_query_run & aggregate_evaluation_results
  6. Boundary conditions:
     - Empty inputs, zero ground truth, non-positive k.
"""

from __future__ import annotations

import os
import sys
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.retrieval_result import RetrievalResult
from app.rag.evaluation_metrics import (
    hit_at_k,
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
    average_precision_at_k,
    ndcg_at_k,
    concept_diversity,
    prerequisite_coverage,
    provenance_retention_rate,
    term_recall,
    calculate_latency_percentiles,
    evaluate_query_run,
    aggregate_evaluation_results,
    QueryEvaluationResult,
    AggregateBenchmarkReport,
)


# ── 1. Ranking & Retrieval Metric Tests ────────────────────────────────

class TestRetrievalMetrics:
    def test_hit_at_k(self):
        retrieved = ["c1", "c2", "c3", "c4", "c5"]
        gt = {"c3"}

        assert hit_at_k(retrieved, gt, k=1) == 0.0
        assert hit_at_k(retrieved, gt, k=2) == 0.0
        assert hit_at_k(retrieved, gt, k=3) == 1.0
        assert hit_at_k(retrieved, gt, k=5) == 1.0

        # Boundary checks
        assert hit_at_k(retrieved, set(), k=5) == 0.0
        assert hit_at_k([], gt, k=5) == 0.0
        assert hit_at_k(retrieved, gt, k=0) == 0.0
        assert hit_at_k(retrieved, gt, k=-1) == 0.0

    def test_recall_and_precision_at_k(self):
        retrieved = ["c1", "c2", "c3", "c4", "c5"]
        gt = {"c1", "c3", "c7"}  # 3 total relevant items

        # Top 3 slice: ["c1", "c2", "c3"] -> 2 hits
        assert recall_at_k(retrieved, gt, k=3) == 2 / 3
        assert precision_at_k(retrieved, gt, k=3) == 2 / 3

        # Top 5 slice: ["c1", "c2", "c3", "c4", "c5"] -> 2 hits
        assert recall_at_k(retrieved, gt, k=5) == 2 / 3
        assert precision_at_k(retrieved, gt, k=5) == 2 / 5

    def test_reciprocal_rank(self):
        assert reciprocal_rank(["c1", "c2", "c3"], {"c1"}) == 1.0
        assert reciprocal_rank(["c1", "c2", "c3"], {"c2"}) == 0.5
        assert reciprocal_rank(["c1", "c2", "c3"], {"c3"}) == 1.0 / 3.0
        assert reciprocal_rank(["c1", "c2", "c3"], {"c9"}) == 0.0
        assert reciprocal_rank([], {"c1"}) == 0.0

    def test_average_precision_at_k(self):
        # Retrieved: [hit, miss, hit, miss, miss]
        retrieved = ["c1", "c2", "c3", "c4", "c5"]
        gt = {"c1", "c3"}

        # At rank 1: precision = 1/1 = 1.0
        # At rank 3: precision = 2/3 = 0.6667
        # Total relevant = 2
        # AP = (1.0 + 0.6667) / 2 = 0.8333
        ap = average_precision_at_k(retrieved, gt, k=5)
        assert abs(ap - 0.8333) < 0.001

    def test_ndcg_at_k(self):
        # Perfect ranking: relevant items first
        perfect_retrieved = ["c1", "c2", "c3"]
        gt = {"c1", "c2"}
        assert ndcg_at_k(perfect_retrieved, gt, k=3) == 1.0

        # Sub-optimal ranking: relevant item at rank 2
        sub_retrieved = ["miss", "c1", "miss"]
        ndcg = ndcg_at_k(sub_retrieved, {"c1"}, k=3)
        # DCG = 1 / log2(3) = 0.6309
        # IDCG = 1 / log2(2) = 1.0
        # NDCG = 0.6309
        assert abs(ndcg - (1.0 / math.log2(3))) < 0.001

        # Zero relevance
        assert ndcg_at_k(["m1", "m2"], gt, k=2) == 0.0


# ── 2. Graph & Concept Metrics Tests ──────────────────────────────────

class TestGraphAndConceptMetrics:
    def test_concept_diversity(self):
        results = [
            RetrievalResult("c1", "text", "dbms", "Indexing", 0.9, "vector"),
            RetrievalResult("c2", "text", "dbms", "Indexing", 0.8, "vector"),
            RetrievalResult("c3", "text", "dbms", "Transactions", 0.7, "vector"),
        ]
        assert concept_diversity(results) == 2
        assert concept_diversity([]) == 0

    def test_prerequisite_coverage(self):
        results = [
            RetrievalResult(
                "c1", "text", "dbms", "Transactions", 0.9, "graph",
                metadata={"traversal_path": ["Transactions", "ACID Properties"]},
            ),
            RetrievalResult(
                "c2", "text", "dbms", "Locks", 0.8, "graph",
                metadata={"traversal_path": ["Locks", "Concurrency"]},
            ),
        ]

        # Target prerequisites: ["ACID Properties", "Concurrency"] -> both covered!
        target = ["ACID Properties", "Concurrency"]
        assert prerequisite_coverage(results, target) == 1.0

        # Target: ["ACID Properties", "Missing Prereq"] -> 1/2 = 0.5
        assert prerequisite_coverage(results, ["ACID Properties", "Missing Prereq"]) == 0.5

        # Empty target prereqs -> 1.0
        assert prerequisite_coverage(results, []) == 1.0

    def test_provenance_retention_rate(self):
        results = [
            RetrievalResult("c1", "t", "d", "c", 0.9, "hybrid", metadata={"sources": ["vector", "graph"]}),
            RetrievalResult("c2", "t", "d", "c", 0.8, "vector", metadata={}),  # No provenance
        ]
        assert provenance_retention_rate(results) == 0.5
        assert provenance_retention_rate([]) == 0.0


# ── 3. Lexical Metrics Tests ──────────────────────────────────────────

class TestLexicalMetrics:
    def test_term_recall(self):
        query = "database normalization BCNF anomalies"
        text = "Database normalization decomposes relations to eliminate anomalies and reach BCNF."
        assert term_recall(query, text) == 1.0

        partial_query = "database indexing query execution plan"
        partial_text = "Database indexing improves query performance."
        rec = term_recall(partial_query, partial_text)
        assert 0.0 < rec < 1.0

        assert term_recall("", text) == 0.0
        assert term_recall(query, "") == 0.0


# ── 4. Latency Distribution Tests ─────────────────────────────────────

class TestLatencyDistribution:
    def test_calculate_latency_percentiles(self):
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        stats = calculate_latency_percentiles(latencies)

        assert stats["mean"] == 55.0
        assert stats["min"] == 10.0
        assert stats["max"] == 100.0
        assert stats["p50"] == 55.0
        assert stats["p90"] == 91.0
        assert stats["p99"] == 99.1

    def test_empty_latencies_safe(self):
        stats = calculate_latency_percentiles([])
        assert stats["mean"] == 0.0
        assert stats["p50"] == 0.0


# ── 5. End-to-End Aggregation Tests ───────────────────────────────────

class TestEndToEndAggregation:
    def test_evaluate_query_run_and_aggregate(self):
        cands1 = [
            RetrievalResult("c1", "acid transactions atomicity", "dbms", "ACID", 0.9, "hybrid", metadata={"sources": ["vector"]}),
            RetrievalResult("c2", "transactions commit rollback", "dbms", "Transactions", 0.8, "hybrid", metadata={"role": "prerequisite"}),
        ]
        res1 = evaluate_query_run(
            query_id="Q01",
            query="ACID transactions atomicity",
            results=cands1,
            ground_truth_chunk_ids={"c1"},
            target_prerequisites=["Transactions"],
            latency_ms=15.5,
        )

        assert res1.hit_1 == 1.0
        assert res1.mrr == 1.0
        assert res1.prereq_coverage == 1.0
        assert res1.concept_diversity == 2

        cands2 = [
            RetrievalResult("c3", "irrelevant text", "os", "Processes", 0.5, "vector", metadata={}),
        ]
        res2 = evaluate_query_run(
            query_id="Q02",
            query="Virtual memory paging",
            results=cands2,
            ground_truth_chunk_ids={"c99"},
            target_prerequisites=[],
            latency_ms=25.5,
        )

        report = aggregate_evaluation_results([res1, res2])
        assert report.total_queries == 2
        assert report.hit_at_1 == 50.0
        assert report.mrr == 0.5
        assert report.latency["p50"] == 20.5
        assert report.to_dict()["total_queries"] == 2

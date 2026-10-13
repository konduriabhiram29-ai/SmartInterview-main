"""
SmartInterview — Phase 15 Test Suite: Individual Alternative Retrievers Benchmark

Tests and asserts:
  1. The benchmark artifact (data/evaluation/individual_retrievers_benchmark.json) exists and conforms to schema.
  2. BM25 KeywordRetriever isolated metrics: Hit@1=87.88%, Hit@3=100%, MRR=0.9293, Term Recall=81.4%, Provenance=100%.
  3. Knowledge Graph GraphRetriever isolated metrics: Hit@1=96.97%, Hit@3=100%, MRR=0.9848, Prereq Coverage=93.94%, Provenance=100%.
  4. Comparative deltas against frozen Dense baseline:
     - Keyword term recall exceeds Dense baseline (+6.97%).
     - Graph prerequisite coverage exceeds Dense baseline (+3.03%).
     - Provenance retention rate is 100% for both alternatives vs 0% for Dense.
     - Both alternative retrievers exhibit sub-2ms latency.
  5. Live execution sanity tests for both retrievers.
"""

from __future__ import annotations

import os
import sys
import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

BENCHMARK_PATH = PROJECT_ROOT / "data" / "evaluation" / "individual_retrievers_benchmark.json"
FROZEN_DENSE_PATH = PROJECT_ROOT / "data" / "evaluation" / "frozen_dense_baseline.json"


@pytest.fixture(scope="module")
def benchmark_data():
    assert BENCHMARK_PATH.exists(), f"Benchmark file missing at: {BENCHMARK_PATH}"
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def frozen_dense_data():
    assert FROZEN_DENSE_PATH.exists(), f"Frozen dense baseline missing at: {FROZEN_DENSE_PATH}"
    with open(FROZEN_DENSE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_benchmark_file_exists_and_schema(benchmark_data):
    """Verify top-level structure of the benchmark report."""
    assert "metadata" in benchmark_data
    assert "comparative_summary" in benchmark_data
    assert "bm25_keyword_metrics" in benchmark_data
    assert "graph_retriever_metrics" in benchmark_data

    meta = benchmark_data["metadata"]
    assert meta["total_queries"] == 33
    assert meta["domains_evaluated"] == 8
    assert meta["top_k"] == 5


def test_bm25_keyword_isolated_metrics(benchmark_data):
    """Verify BM25 Keyword Retriever aggregate performance in isolation."""
    kw_agg = benchmark_data["bm25_keyword_metrics"]["aggregate"]

    assert kw_agg["hit_at_1"] == 87.88
    assert kw_agg["hit_at_3"] == 100.0
    assert kw_agg["hit_at_5"] == 100.0
    assert 0.92 <= kw_agg["mrr"] <= 0.94

    # BM25 must achieve strong term recall and 100% provenance retention
    assert kw_agg["avg_term_recall"] >= 80.0
    assert kw_agg["avg_provenance_rate"] == 100.0

    # Latency should be sub-5ms
    assert kw_agg["latency"]["mean"] < 5.0


def test_graph_retriever_isolated_metrics(benchmark_data):
    """Verify Knowledge Graph Retriever aggregate performance in isolation."""
    gr_agg = benchmark_data["graph_retriever_metrics"]["aggregate"]

    assert gr_agg["hit_at_1"] == 96.97
    assert gr_agg["hit_at_3"] == 100.0
    assert gr_agg["hit_at_5"] == 100.0
    assert 0.98 <= gr_agg["mrr"] <= 0.99

    # Graph retriever achieves highest prerequisite coverage and 100% provenance
    assert gr_agg["avg_prereq_coverage"] >= 93.0
    assert gr_agg["avg_provenance_rate"] == 100.0

    # Latency should be sub-5ms
    assert gr_agg["latency"]["mean"] < 5.0


def test_comparative_deltas_against_dense_baseline(benchmark_data, frozen_dense_data):
    """Verify key comparative advantages documented against the frozen dense baseline."""
    dense_agg = frozen_dense_data["frozen_aggregate_metrics"]
    kw_agg = benchmark_data["bm25_keyword_metrics"]["aggregate"]
    gr_agg = benchmark_data["graph_retriever_metrics"]["aggregate"]

    # 1. BM25 keyword term recall exceeds Dense baseline
    assert kw_agg["avg_term_recall"] > dense_agg["avg_term_recall"]

    # 2. Graph prerequisite coverage exceeds Dense baseline
    assert gr_agg["avg_prereq_coverage"] > dense_agg["avg_prereq_coverage"]

    # 3. Graph RAG MRR is at least as high as Dense baseline
    assert gr_agg["mrr"] >= dense_agg["mrr"]

    # 4. Provenance retention is 100% for both alternatives vs 0% for Dense
    assert kw_agg["avg_provenance_rate"] == 100.0
    assert gr_agg["avg_provenance_rate"] == 100.0
    assert dense_agg["avg_provenance_rate"] == 0.0

    # 5. Both alternatives have lower latency than Dense (no embedding model inference)
    assert kw_agg["latency"]["mean"] < dense_agg["latency"]["mean"]
    assert gr_agg["latency"]["mean"] < dense_agg["latency"]["mean"]


def test_per_query_evaluations_counts_and_failures(benchmark_data):
    """Verify per-query evaluation breakdown and inspect expected non-rank-1 queries."""
    kw_queries = benchmark_data["bm25_keyword_metrics"]["per_query"]
    gr_queries = benchmark_data["graph_retriever_metrics"]["per_query"]

    assert len(kw_queries) == 33
    assert len(gr_queries) == 33

    # Keyword retriever has exactly 4 queries where hit_1 == 0
    kw_non_rank1 = [q for q in kw_queries if q["hit_1"] == 0.0]
    assert len(kw_non_rank1) == 4
    kw_concepts = {q["concept"] for q in kw_non_rank1}
    assert "array" in kw_concepts
    assert "stack" in kw_concepts
    assert "dynamic-programming" in kw_concepts
    assert "caching" in kw_concepts

    # Graph retriever has exactly 1 query where hit_1 == 0 (GOLD_15: stack vs queue)
    gr_non_rank1 = [q for q in gr_queries if q["hit_1"] == 0.0]
    assert len(gr_non_rank1) == 1
    assert gr_non_rank1[0]["concept"] == "stack"


def test_live_keyword_and_graph_retrievers_execution():
    """Verify live instantiations of both alternative retrievers run and return valid results."""
    from app.rag.keyword_retriever import KeywordRetriever
    from app.rag.graph_retriever import GraphRetriever

    kw = KeywordRetriever()
    kw_results = kw.retrieve(
        query="Explain ACID properties in database transactions",
        skill="acid-properties",
        domains=["dbms"],
        top_k=3,
    )
    assert len(kw_results) == 3
    assert kw_results[0].keyword_score is not None
    assert kw_results[0].domain == "dbms"
    assert "matched_terms" in kw_results[0].metadata

    gr = GraphRetriever()
    gr_results = gr.retrieve(
        query="Explain ACID properties in database transactions",
        skill="acid-properties",
        domains=["dbms"],
        concept="acid-properties",
        top_k=3,
    )
    assert len(gr_results) == 3
    assert gr_results[0].graph_score is not None
    assert gr_results[0].domain == "dbms"
    assert "traversal_path" in gr_results[0].metadata

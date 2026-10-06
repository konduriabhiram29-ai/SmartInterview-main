"""
SmartInterview — Phase 11 Tests: End-to-End Evaluation & Research Verification

Tests that verify:
  1. Benchmark pipeline executes successfully across all 4 RAG architectures.
  2. Multi-hop prerequisite discovery: Hybrid Graph RAG retrieves foundational
     prerequisites where pure Dense RAG exhibits single-concept crowding.
  3. Concept diversity protection prevents single-topic redundancy.
  4. Weak-topic remediation elevates foundational prerequisites in the top-k context.
  5. Quantitative metrics (prerequisite coverage, keyword recall, latency) are
     accurately computed and bounded.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from evaluate_rag_comparison import init_all_retrievers, compute_metrics, run_benchmark


@pytest.fixture(scope="module")
def benchmark_data():
    """Run the reproducible benchmark once for the test module."""
    return run_benchmark()


# ── 1. Benchmark Execution & Architecture Validation ──────────────────

class TestBenchmarkExecution:
    def test_all_scenarios_and_modes_present(self, benchmark_data):
        expected_scenarios = [
            "scenario_1_multihop",
            "scenario_2_keyword",
            "scenario_3_remediation",
            "scenario_4_bloom_analyze",
        ]
        expected_modes = ["Dense RAG", "Keyword RAG", "Graph RAG", "Hybrid Graph RAG"]

        for sc_id in expected_scenarios:
            assert sc_id in benchmark_data, f"Missing scenario: {sc_id}"
            modes = benchmark_data[sc_id]["modes"]
            for m in expected_modes:
                assert m in modes, f"Missing mode {m} in {sc_id}"
                metrics = modes[m]["metrics"]
                assert metrics["num_results"] > 0
                assert 0.0 <= metrics["keyword_recall"] <= 1.0
                assert 0.0 <= metrics["prereq_coverage"] <= 1.0
                assert metrics["latency_ms"] >= 0.0


# ── 2. Empirical Superiority of Hybrid Graph RAG ──────────────────────

class TestEmpiricalComparison:
    def test_multihop_prerequisite_superiority(self, benchmark_data):
        """
        Scenario 1 tests prerequisite discovery:
        Pure Dense RAG fails to retrieve 'Transactions' because all top-3 vector hits
        crowd on 'acid-properties'. Hybrid Graph RAG must retrieve 'Transactions'.
        """
        sc1 = benchmark_data["scenario_1_multihop"]["modes"]
        dense_cov = sc1["Dense RAG"]["metrics"]["prereq_coverage"]
        hybrid_cov = sc1["Hybrid Graph RAG"]["metrics"]["prereq_coverage"]

        # Dense RAG has 0% prerequisite coverage
        assert dense_cov == 0.0
        # Hybrid Graph RAG successfully discovers the prerequisite
        assert hybrid_cov == 1.0
        assert hybrid_cov > dense_cov

    def test_weak_topic_remediation_superiority(self, benchmark_data):
        """
        Scenario 3 tests weak-topic remediation:
        When a candidate has a gap in ACID properties, Hybrid Graph RAG must surface
        the foundational prerequisite ('Transactions') into the top-3 context.
        """
        sc3 = benchmark_data["scenario_3_remediation"]["modes"]
        dense_cov = sc3["Dense RAG"]["metrics"]["prereq_coverage"]
        hybrid_cov = sc3["Hybrid Graph RAG"]["metrics"]["prereq_coverage"]

        assert dense_cov == 0.0
        assert hybrid_cov == 1.0
        assert any(c.lower() == "transactions" for c in sc3["Hybrid Graph RAG"]["metrics"]["concepts"])

    def test_concept_diversity_preservation(self, benchmark_data):
        """
        Verify that Hybrid Graph RAG preserves multi-concept context rather than
        returning 3 paraphrases of the same single concept chunk.
        """
        sc1 = benchmark_data["scenario_1_multihop"]["modes"]
        hybrid_concepts = sc1["Hybrid Graph RAG"]["metrics"]["unique_concepts"]
        assert hybrid_concepts >= 2


# ── 3. Latency & Computational Overhead Checks ───────────────────────

class TestLatencyTradeoffs:
    def test_graph_and_keyword_latency_under_50ms(self, benchmark_data):
        """Graph and Keyword retrievers should be sub-50ms (typically sub-5ms)."""
        sc1 = benchmark_data["scenario_1_multihop"]["modes"]
        assert sc1["Keyword RAG"]["metrics"]["latency_ms"] < 50.0
        assert sc1["Graph RAG"]["metrics"]["latency_ms"] < 50.0

    def test_hybrid_latency_under_1000ms(self, benchmark_data):
        """Hybrid Graph RAG + reranking runs well within interactive SLA (< 1000ms)."""
        sc1 = benchmark_data["scenario_1_multihop"]["modes"]
        assert sc1["Hybrid Graph RAG"]["metrics"]["latency_ms"] < 1000.0

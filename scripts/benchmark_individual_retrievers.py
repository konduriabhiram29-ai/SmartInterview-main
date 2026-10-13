"""
SmartInterview — Benchmark Individual Alternative Retrievers (Phase 15)

Evaluates:
  1. BM25 KeywordRetriever in isolation.
  2. Knowledge Graph GraphRetriever in isolation.
Over the canonical benchmark: data/evaluation/golden_evaluation_dataset.json (33 queries, 402 chunks).

Computes standardized metrics:
  - Hit@1, Hit@3, Hit@5
  - Recall@5, Precision@5
  - MRR, MAP@5, NDCG@5
  - Prerequisite Coverage
  - Concept Diversity
  - Keyword Term Recall
  - Multi-Channel Provenance Retention Rate
  - Latency percentiles (Mean, Min, Max, P50, P90, P95, P99)

Saves results and comparative matrices to:
  data/evaluation/individual_retrievers_benchmark.json
"""

from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.rag.keyword_retriever import KeywordRetriever
from app.rag.graph_retriever import GraphRetriever
from app.rag.evaluation_metrics import (
    evaluate_query_run,
    aggregate_evaluation_results,
    QueryEvaluationResult,
)


def run_individual_retrievers_benchmark() -> Dict[str, Any]:
    print("=" * 75)
    print("SmartInterview — Individual Alternative Retrievers Benchmark (Phase 15)")
    print("=" * 75)

    golden_file = PROJECT_ROOT / "data" / "evaluation" / "golden_evaluation_dataset.json"
    with open(golden_file, "r", encoding="utf-8") as f:
        golden_dataset = json.load(f)

    frozen_baseline_file = PROJECT_ROOT / "data" / "evaluation" / "frozen_dense_baseline.json"
    with open(frozen_baseline_file, "r", encoding="utf-8") as f:
        dense_baseline_data = json.load(f)

    dense_agg = dense_baseline_data["frozen_aggregate_metrics"]

    # ─────────────────────────────────────────────────────────────────
    # 1. Benchmark BM25 Keyword Retriever in Isolation
    # ─────────────────────────────────────────────────────────────────
    print("\n[1/2] Initializing & Benchmarking BM25 Keyword Retriever...")
    kw_retriever = KeywordRetriever()

    # Warm-up pass
    _ = kw_retriever.retrieve(query="Warm up query", skill="dns", domains=["cn"], top_k=1)

    kw_query_evals: List[QueryEvaluationResult] = []
    kw_per_query_records: List[Dict[str, Any]] = []

    for item in golden_dataset:
        q_id = item["query_id"]
        q_text = item["query"]
        domain = item["domain"]
        concept = item["concept"]
        expected_chunk_ids = set(item.get("expected_chunk_ids", []))
        expected_prereqs = item.get("expected_prerequisites", [])

        start_time = time.perf_counter()
        results = kw_retriever.retrieve(
            query=q_text,
            skill=concept,
            domains=[domain],
            top_k=5,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        q_eval = evaluate_query_run(
            query_id=q_id,
            query=q_text,
            results=results,
            ground_truth_chunk_ids=expected_chunk_ids,
            target_prerequisites=expected_prereqs,
            latency_ms=latency_ms,
        )
        kw_query_evals.append(q_eval)

        retrieved_details = [
            {
                "rank": rank,
                "chunk_id": r.chunk_id,
                "domain": r.domain,
                "concept": r.concept,
                "keyword_score": r.keyword_score,
                "matched_terms": r.metadata.get("matched_terms", []),
                "is_ground_truth_match": r.chunk_id in expected_chunk_ids,
                "snippet": r.text[:120].strip() + "...",
            }
            for rank, r in enumerate(results, 1)
        ]

        kw_per_query_records.append({
            "query_id": q_id,
            "query": q_text,
            "domain": domain,
            "concept": concept,
            "latency_ms": round(latency_ms, 2),
            "hit_1": q_eval.hit_1,
            "hit_3": q_eval.hit_3,
            "hit_5": q_eval.hit_5,
            "recall_5": round(q_eval.recall_5, 4),
            "precision_5": round(q_eval.precision_5, 4),
            "mrr": round(q_eval.mrr, 4),
            "map_5": round(q_eval.map_5, 4),
            "ndcg_5": round(q_eval.ndcg_5, 4),
            "prereq_coverage": round(q_eval.prereq_coverage, 4),
            "concept_diversity": q_eval.concept_diversity,
            "term_recall": round(q_eval.term_recall, 4),
            "provenance_rate": round(q_eval.provenance_rate, 4),
            "retrieved_chunks": retrieved_details,
        })

    kw_aggregate_report = aggregate_evaluation_results(kw_query_evals)
    kw_agg = kw_aggregate_report.to_dict()

    # ─────────────────────────────────────────────────────────────────
    # 2. Benchmark Knowledge Graph Retriever in Isolation
    # ─────────────────────────────────────────────────────────────────
    print("[2/2] Initializing & Benchmarking Knowledge Graph Retriever...")
    gr_retriever = GraphRetriever()

    # Warm-up pass
    _ = gr_retriever.retrieve(query="Warm up query", skill="dns", domains=["cn"], top_k=1, concept="dns")

    gr_query_evals: List[QueryEvaluationResult] = []
    gr_per_query_records: List[Dict[str, Any]] = []

    for item in golden_dataset:
        q_id = item["query_id"]
        q_text = item["query"]
        domain = item["domain"]
        concept = item["concept"]
        bloom_level = item.get("bloom_level")
        expected_chunk_ids = set(item.get("expected_chunk_ids", []))
        expected_prereqs = item.get("expected_prerequisites", [])

        start_time = time.perf_counter()
        results = gr_retriever.retrieve(
            query=q_text,
            skill=concept,
            domains=[domain],
            top_k=5,
            concept=concept,
            bloom_level=bloom_level,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        q_eval = evaluate_query_run(
            query_id=q_id,
            query=q_text,
            results=results,
            ground_truth_chunk_ids=expected_chunk_ids,
            target_prerequisites=expected_prereqs,
            latency_ms=latency_ms,
        )
        gr_query_evals.append(q_eval)

        retrieved_details = [
            {
                "rank": rank,
                "chunk_id": r.chunk_id,
                "domain": r.domain,
                "concept": r.concept,
                "graph_score": r.graph_score,
                "traversal_path": r.metadata.get("traversal_path", []),
                "role": r.metadata.get("role", "concept"),
                "is_ground_truth_match": r.chunk_id in expected_chunk_ids,
                "snippet": r.text[:120].strip() + "...",
            }
            for rank, r in enumerate(results, 1)
        ]

        gr_per_query_records.append({
            "query_id": q_id,
            "query": q_text,
            "domain": domain,
            "concept": concept,
            "latency_ms": round(latency_ms, 2),
            "hit_1": q_eval.hit_1,
            "hit_3": q_eval.hit_3,
            "hit_5": q_eval.hit_5,
            "recall_5": round(q_eval.recall_5, 4),
            "precision_5": round(q_eval.precision_5, 4),
            "mrr": round(q_eval.mrr, 4),
            "map_5": round(q_eval.map_5, 4),
            "ndcg_5": round(q_eval.ndcg_5, 4),
            "prereq_coverage": round(q_eval.prereq_coverage, 4),
            "concept_diversity": q_eval.concept_diversity,
            "term_recall": round(q_eval.term_recall, 4),
            "provenance_rate": round(q_eval.provenance_rate, 4),
            "retrieved_chunks": retrieved_details,
        })

    gr_aggregate_report = aggregate_evaluation_results(gr_query_evals)
    gr_agg = gr_aggregate_report.to_dict()

    # ─────────────────────────────────────────────────────────────────
    # 3. Assemble Comparative Matrix & Output Artifact
    # ─────────────────────────────────────────────────────────────────
    comparative_summary = {
        "hit_at_1": {
            "dense": dense_agg["hit_at_1"],
            "keyword": kw_agg["hit_at_1"],
            "graph": gr_agg["hit_at_1"],
            "delta_keyword_vs_dense": round(kw_agg["hit_at_1"] - dense_agg["hit_at_1"], 2),
            "delta_graph_vs_dense": round(gr_agg["hit_at_1"] - dense_agg["hit_at_1"], 2),
        },
        "hit_at_3": {
            "dense": dense_agg["hit_at_3"],
            "keyword": kw_agg["hit_at_3"],
            "graph": gr_agg["hit_at_3"],
        },
        "hit_at_5": {
            "dense": dense_agg["hit_at_5"],
            "keyword": kw_agg["hit_at_5"],
            "graph": gr_agg["hit_at_5"],
        },
        "mrr": {
            "dense": dense_agg["mrr"],
            "keyword": kw_agg["mrr"],
            "graph": gr_agg["mrr"],
            "delta_keyword_vs_dense": round(kw_agg["mrr"] - dense_agg["mrr"], 4),
            "delta_graph_vs_dense": round(gr_agg["mrr"] - dense_agg["mrr"], 4),
        },
        "recall_at_5": {
            "dense": dense_agg["recall_at_5"],
            "keyword": kw_agg["recall_at_5"],
            "graph": gr_agg["recall_at_5"],
        },
        "precision_at_5": {
            "dense": dense_agg["precision_at_5"],
            "keyword": kw_agg["precision_at_5"],
            "graph": gr_agg["precision_at_5"],
        },
        "map_at_5": {
            "dense": dense_agg["map_at_5"],
            "keyword": kw_agg["map_at_5"],
            "graph": gr_agg["map_at_5"],
        },
        "ndcg_at_5": {
            "dense": dense_agg["ndcg_at_5"],
            "keyword": kw_agg["ndcg_at_5"],
            "graph": gr_agg["ndcg_at_5"],
        },
        "avg_prereq_coverage": {
            "dense": dense_agg["avg_prereq_coverage"],
            "keyword": kw_agg["avg_prereq_coverage"],
            "graph": gr_agg["avg_prereq_coverage"],
            "delta_graph_vs_dense": round(gr_agg["avg_prereq_coverage"] - dense_agg["avg_prereq_coverage"], 2),
        },
        "avg_concept_diversity": {
            "dense": dense_agg["avg_concept_diversity"],
            "keyword": kw_agg["avg_concept_diversity"],
            "graph": gr_agg["avg_concept_diversity"],
        },
        "avg_term_recall": {
            "dense": dense_agg["avg_term_recall"],
            "keyword": kw_agg["avg_term_recall"],
            "graph": gr_agg["avg_term_recall"],
            "delta_keyword_vs_dense": round(kw_agg["avg_term_recall"] - dense_agg["avg_term_recall"], 2),
        },
        "avg_provenance_rate": {
            "dense": dense_agg["avg_provenance_rate"],
            "keyword": kw_agg["avg_provenance_rate"],
            "graph": gr_agg["avg_provenance_rate"],
        },
        "mean_latency_ms": {
            "dense": dense_agg["latency"]["mean"],
            "keyword": kw_agg["latency"]["mean"],
            "graph": gr_agg["latency"]["mean"],
        },
        "p50_latency_ms": {
            "dense": dense_agg["latency"]["p50"],
            "keyword": kw_agg["latency"]["p50"],
            "graph": gr_agg["latency"]["p50"],
        },
        "p95_latency_ms": {
            "dense": dense_agg["latency"]["p95"],
            "keyword": kw_agg["latency"]["p95"],
            "graph": gr_agg["latency"]["p95"],
        },
    }

    benchmark_data = {
        "metadata": {
            "title": "SmartInterview Individual Alternative Retrievers Benchmark",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_queries": len(golden_dataset),
            "domains_evaluated": 8,
            "top_k": 5,
        },
        "comparative_summary": comparative_summary,
        "bm25_keyword_metrics": {
            "aggregate": kw_agg,
            "per_query": kw_per_query_records,
        },
        "graph_retriever_metrics": {
            "aggregate": gr_agg,
            "per_query": gr_per_query_records,
        },
    }

    out_file = PROJECT_ROOT / "data" / "evaluation" / "individual_retrievers_benchmark.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print(f"\nIndividual retrievers benchmark successfully written to: {out_file}")

    print("\n" + "=" * 75)
    print(f"{'Metric':<24} | {'Dense (Frozen)':<14} | {'BM25 Keyword':<14} | {'Graph RAG':<14}")
    print("-" * 75)
    print(f"{'Hit@1':<24} | {dense_agg['hit_at_1']:<14}% | {kw_agg['hit_at_1']:<14}% | {gr_agg['hit_at_1']:<14}%")
    print(f"{'Hit@3':<24} | {dense_agg['hit_at_3']:<14}% | {kw_agg['hit_at_3']:<14}% | {gr_agg['hit_at_3']:<14}%")
    print(f"{'Hit@5':<24} | {dense_agg['hit_at_5']:<14}% | {kw_agg['hit_at_5']:<14}% | {gr_agg['hit_at_5']:<14}%")
    print(f"{'MRR':<24} | {dense_agg['mrr']:<14}  | {kw_agg['mrr']:<14}  | {gr_agg['mrr']:<14} ")
    print(f"{'Recall@5':<24} | {dense_agg['recall_at_5']:<14}% | {kw_agg['recall_at_5']:<14}% | {gr_agg['recall_at_5']:<14}%")
    print(f"{'Precision@5':<24} | {dense_agg['precision_at_5']:<14}% | {kw_agg['precision_at_5']:<14}% | {gr_agg['precision_at_5']:<14}%")
    print(f"{'MAP@5':<24} | {dense_agg['map_at_5']:<14}  | {kw_agg['map_at_5']:<14}  | {gr_agg['map_at_5']:<14} ")
    print(f"{'NDCG@5':<24} | {dense_agg['ndcg_at_5']:<14}  | {kw_agg['ndcg_at_5']:<14}  | {gr_agg['ndcg_at_5']:<14} ")
    print(f"{'Prereq Coverage':<24} | {dense_agg['avg_prereq_coverage']:<14}% | {kw_agg['avg_prereq_coverage']:<14}% | {gr_agg['avg_prereq_coverage']:<14}%")
    print(f"{'Concept Diversity':<24} | {dense_agg['avg_concept_diversity']:<14}  | {kw_agg['avg_concept_diversity']:<14}  | {gr_agg['avg_concept_diversity']:<14} ")
    print(f"{'Term Recall':<24} | {dense_agg['avg_term_recall']:<14}% | {kw_agg['avg_term_recall']:<14}% | {gr_agg['avg_term_recall']:<14}%")
    print(f"{'Provenance Rate':<24} | {dense_agg['avg_provenance_rate']:<14}% | {kw_agg['avg_provenance_rate']:<14}% | {gr_agg['avg_provenance_rate']:<14}%")
    print(f"{'Mean Latency':<24} | {dense_agg['latency']['mean']:<11} ms | {kw_agg['latency']['mean']:<11} ms | {gr_agg['latency']['mean']:<11} ms")
    print(f"{'P50 Latency':<24} | {dense_agg['latency']['p50']:<11} ms | {kw_agg['latency']['p50']:<11} ms | {gr_agg['latency']['p50']:<11} ms")
    print(f"{'P95 Latency':<24} | {dense_agg['latency']['p95']:<11} ms | {kw_agg['latency']['p95']:<11} ms | {gr_agg['latency']['p95']:<11} ms")
    print("=" * 75)

    return benchmark_data


if __name__ == "__main__":
    run_individual_retrievers_benchmark()

"""
SmartInterview — Benchmark Hybrid Graph RAG (Phase 16)

Evaluates:
  1. Hybrid RAG with Reciprocal Rank Fusion (RRF) without reranking.
  2. Full Hybrid Graph RAG (RRF fusion + Contextual Cross-Encoder/Semantic Reranking).
Over the canonical benchmark: data/evaluation/golden_evaluation_dataset.json (33 queries, 402 chunks).

Computes standardized metrics across all 12 IR and cognitive dimensions:
  - Hit@1, Hit@3, Hit@5
  - Recall@5, Precision@5
  - MRR, MAP@5, NDCG@5
  - Prerequisite Coverage
  - Concept Diversity
  - Keyword Term Recall
  - Multi-Channel Provenance Retention Rate
  - Latency percentiles (Mean, Min, Max, P50, P90, P95, P99)

Constructs the comprehensive 4-way comparative evaluation matrix and saves to:
  data/evaluation/hybrid_rag_benchmark.json
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

from app.services.question_service import _get_retriever, _get_reranker
from app.rag.evaluation_metrics import (
    evaluate_query_run,
    aggregate_evaluation_results,
    QueryEvaluationResult,
)


def run_hybrid_rag_benchmark() -> Dict[str, Any]:
    print("=" * 80)
    print("SmartInterview — Full Hybrid Graph RAG Benchmark & Evaluation (Phase 16)")
    print("=" * 80)

    golden_file = PROJECT_ROOT / "data" / "evaluation" / "golden_evaluation_dataset.json"
    with open(golden_file, "r", encoding="utf-8") as f:
        golden_dataset = json.load(f)

    frozen_baseline_file = PROJECT_ROOT / "data" / "evaluation" / "frozen_dense_baseline.json"
    with open(frozen_baseline_file, "r", encoding="utf-8") as f:
        dense_data = json.load(f)

    individual_benchmark_file = PROJECT_ROOT / "data" / "evaluation" / "individual_retrievers_benchmark.json"
    with open(individual_benchmark_file, "r", encoding="utf-8") as f:
        indiv_data = json.load(f)

    dense_agg = dense_data["frozen_aggregate_metrics"]
    kw_agg = indiv_data["bm25_keyword_metrics"]["aggregate"]
    gr_agg = indiv_data["graph_retriever_metrics"]["aggregate"]

    print("\nInitializing HybridRetriever and BaseReranker...")
    hybrid_retriever = _get_retriever(mode="hybrid")
    reranker = _get_reranker()

    # Warm-up pass
    _ = hybrid_retriever.retrieve(
        query="Warmup query", skill="dns", domains=["cn"], top_k=5, concept="dns", fusion_method="rrf"
    )

    # ─────────────────────────────────────────────────────────────────
    # 1. Benchmark Hybrid RRF (Without Reranking)
    # ─────────────────────────────────────────────────────────────────
    print("\n[1/2] Benchmarking Hybrid RRF (Without Contextual Reranking)...")
    rrf_query_evals: List[QueryEvaluationResult] = []
    rrf_per_query_records: List[Dict[str, Any]] = []

    for item in golden_dataset:
        q_id = item["query_id"]
        q_text = item["query"]
        domain = item["domain"]
        concept = item["concept"]
        bloom_level = item.get("bloom_level")
        expected_chunk_ids = set(item.get("expected_chunk_ids", []))
        expected_prereqs = item.get("expected_prerequisites", [])

        start_time = time.perf_counter()
        results = hybrid_retriever.retrieve(
            query=q_text,
            skill=concept,
            domains=[domain],
            top_k=5,
            concept=concept,
            bloom_level=bloom_level,
            fusion_method="rrf",
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
        rrf_query_evals.append(q_eval)

        retrieved_details = [
            {
                "rank": rank,
                "chunk_id": r.chunk_id,
                "domain": r.domain,
                "concept": r.concept,
                "final_score": r.final_score,
                "sources": r.metadata.get("sources", []),
                "ranks": r.metadata.get("ranks", {}),
                "is_ground_truth_match": r.chunk_id in expected_chunk_ids,
                "snippet": r.text[:120].strip() + "...",
            }
            for rank, r in enumerate(results, 1)
        ]

        rrf_per_query_records.append({
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

    rrf_aggregate_report = aggregate_evaluation_results(rrf_query_evals)
    rrf_agg = rrf_aggregate_report.to_dict()

    # ─────────────────────────────────────────────────────────────────
    # 2. Benchmark Full Hybrid Graph RAG (With Contextual Reranking)
    # ─────────────────────────────────────────────────────────────────
    print("[2/2] Benchmarking Full Hybrid Graph RAG (RRF + Contextual Reranking)...")
    full_query_evals: List[QueryEvaluationResult] = []
    full_per_query_records: List[Dict[str, Any]] = []

    for item in golden_dataset:
        q_id = item["query_id"]
        q_text = item["query"]
        domain = item["domain"]
        concept = item["concept"]
        bloom_level = item.get("bloom_level")
        expected_chunk_ids = set(item.get("expected_chunk_ids", []))
        expected_prereqs = item.get("expected_prerequisites", [])

        start_time = time.perf_counter()
        fused_candidates = hybrid_retriever.retrieve(
            query=q_text,
            skill=concept,
            domains=[domain],
            top_k=10,
            concept=concept,
            bloom_level=bloom_level,
            fusion_method="rrf",
        )
        reranked_results = reranker.rerank(
            query=q_text,
            results=fused_candidates,
            top_k=5,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        q_eval = evaluate_query_run(
            query_id=q_id,
            query=q_text,
            results=reranked_results,
            ground_truth_chunk_ids=expected_chunk_ids,
            target_prerequisites=expected_prereqs,
            latency_ms=latency_ms,
        )
        full_query_evals.append(q_eval)

        retrieved_details = [
            {
                "rank": rank,
                "chunk_id": r.chunk_id,
                "domain": r.domain,
                "concept": r.concept,
                "final_score": r.final_score,
                "reranker_score": r.metadata.get("reranker_score"),
                "sources": r.metadata.get("sources", []),
                "is_ground_truth_match": r.chunk_id in expected_chunk_ids,
                "snippet": r.text[:120].strip() + "...",
            }
            for rank, r in enumerate(reranked_results, 1)
        ]

        full_per_query_records.append({
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

    full_aggregate_report = aggregate_evaluation_results(full_query_evals)
    full_agg = full_aggregate_report.to_dict()

    # ─────────────────────────────────────────────────────────────────
    # 3. Assemble Master 4-Way Comparison
    # ─────────────────────────────────────────────────────────────────
    comparative_matrix = {
        "hit_at_1": {
            "dense": dense_agg["hit_at_1"],
            "keyword": kw_agg["hit_at_1"],
            "graph": gr_agg["hit_at_1"],
            "hybrid_rrf": rrf_agg["hit_at_1"],
            "hybrid_reranked": full_agg["hit_at_1"],
        },
        "hit_at_3": {
            "dense": dense_agg["hit_at_3"],
            "keyword": kw_agg["hit_at_3"],
            "graph": gr_agg["hit_at_3"],
            "hybrid_rrf": rrf_agg["hit_at_3"],
            "hybrid_reranked": full_agg["hit_at_3"],
        },
        "hit_at_5": {
            "dense": dense_agg["hit_at_5"],
            "keyword": kw_agg["hit_at_5"],
            "graph": gr_agg["hit_at_5"],
            "hybrid_rrf": rrf_agg["hit_at_5"],
            "hybrid_reranked": full_agg["hit_at_5"],
        },
        "mrr": {
            "dense": dense_agg["mrr"],
            "keyword": kw_agg["mrr"],
            "graph": gr_agg["mrr"],
            "hybrid_rrf": rrf_agg["mrr"],
            "hybrid_reranked": full_agg["mrr"],
        },
        "recall_at_5": {
            "dense": dense_agg["recall_at_5"],
            "keyword": kw_agg["recall_at_5"],
            "graph": gr_agg["recall_at_5"],
            "hybrid_rrf": rrf_agg["recall_at_5"],
            "hybrid_reranked": full_agg["recall_at_5"],
        },
        "precision_at_5": {
            "dense": dense_agg["precision_at_5"],
            "keyword": kw_agg["precision_at_5"],
            "graph": gr_agg["precision_at_5"],
            "hybrid_rrf": rrf_agg["precision_at_5"],
            "hybrid_reranked": full_agg["precision_at_5"],
        },
        "map_at_5": {
            "dense": dense_agg["map_at_5"],
            "keyword": kw_agg["map_at_5"],
            "graph": gr_agg["map_at_5"],
            "hybrid_rrf": rrf_agg["map_at_5"],
            "hybrid_reranked": full_agg["map_at_5"],
        },
        "ndcg_at_5": {
            "dense": dense_agg["ndcg_at_5"],
            "keyword": kw_agg["ndcg_at_5"],
            "graph": gr_agg["ndcg_at_5"],
            "hybrid_rrf": rrf_agg["ndcg_at_5"],
            "hybrid_reranked": full_agg["ndcg_at_5"],
        },
        "prereq_coverage": {
            "dense": dense_agg["avg_prereq_coverage"],
            "keyword": kw_agg["avg_prereq_coverage"],
            "graph": gr_agg["avg_prereq_coverage"],
            "hybrid_rrf": rrf_agg["avg_prereq_coverage"],
            "hybrid_reranked": full_agg["avg_prereq_coverage"],
        },
        "concept_diversity": {
            "dense": dense_agg["avg_concept_diversity"],
            "keyword": kw_agg["avg_concept_diversity"],
            "graph": gr_agg["avg_concept_diversity"],
            "hybrid_rrf": rrf_agg["avg_concept_diversity"],
            "hybrid_reranked": full_agg["avg_concept_diversity"],
        },
        "term_recall": {
            "dense": dense_agg["avg_term_recall"],
            "keyword": kw_agg["avg_term_recall"],
            "graph": gr_agg["avg_term_recall"],
            "hybrid_rrf": rrf_agg["avg_term_recall"],
            "hybrid_reranked": full_agg["avg_term_recall"],
        },
        "provenance_rate": {
            "dense": dense_agg["avg_provenance_rate"],
            "keyword": kw_agg["avg_provenance_rate"],
            "graph": gr_agg["avg_provenance_rate"],
            "hybrid_rrf": rrf_agg["avg_provenance_rate"],
            "hybrid_reranked": full_agg["avg_provenance_rate"],
        },
        "mean_latency_ms": {
            "dense": dense_agg["latency"]["mean"],
            "keyword": kw_agg["latency"]["mean"],
            "graph": gr_agg["latency"]["mean"],
            "hybrid_rrf": rrf_agg["latency"]["mean"],
            "hybrid_reranked": full_agg["latency"]["mean"],
        },
    }

    report_payload = {
        "metadata": {
            "title": "SmartInterview Full Hybrid Graph RAG Benchmark",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_queries": len(golden_dataset),
            "domains_evaluated": 8,
            "fusion_method": "Reciprocal Rank Fusion (RRF, k=60)",
            "reranker": reranker.__class__.__name__,
        },
        "comparative_matrix": comparative_matrix,
        "hybrid_rrf_metrics": {
            "aggregate": rrf_agg,
            "per_query": rrf_per_query_records,
        },
        "full_hybrid_graph_rag_metrics": {
            "aggregate": full_agg,
            "per_query": full_per_query_records,
        },
    }

    out_file = PROJECT_ROOT / "data" / "evaluation" / "hybrid_rag_benchmark.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    print(f"\nHybrid Graph RAG benchmark successfully written to: {out_file}")

    print("\n" + "=" * 90)
    print(f"{'Metric':<20} | {'Pure Dense':<12} | {'BM25':<10} | {'Graph':<10} | {'Hybrid RRF':<12} | {'Hybrid+Rerank':<14}")
    print("-" * 90)
    print(f"{'Hit@1':<20} | {dense_agg['hit_at_1']:<10}% | {kw_agg['hit_at_1']:<8}% | {gr_agg['hit_at_1']:<8}% | {rrf_agg['hit_at_1']:<10}% | {full_agg['hit_at_1']:<12}%")
    print(f"{'Hit@3':<20} | {dense_agg['hit_at_3']:<10}% | {kw_agg['hit_at_3']:<8}% | {gr_agg['hit_at_3']:<8}% | {rrf_agg['hit_at_3']:<10}% | {full_agg['hit_at_3']:<12}%")
    print(f"{'Hit@5':<20} | {dense_agg['hit_at_5']:<10}% | {kw_agg['hit_at_5']:<8}% | {gr_agg['hit_at_5']:<8}% | {rrf_agg['hit_at_5']:<10}% | {full_agg['hit_at_5']:<12}%")
    print(f"{'MRR':<20} | {dense_agg['mrr']:<12} | {kw_agg['mrr']:<10} | {gr_agg['mrr']:<10} | {rrf_agg['mrr']:<12} | {full_agg['mrr']:<14}")
    print(f"{'Recall@5':<20} | {dense_agg['recall_at_5']:<10}% | {kw_agg['recall_at_5']:<8}% | {gr_agg['recall_at_5']:<8}% | {rrf_agg['recall_at_5']:<10}% | {full_agg['recall_at_5']:<12}%")
    print(f"{'Precision@5':<20} | {dense_agg['precision_at_5']:<10}% | {kw_agg['precision_at_5']:<8}% | {gr_agg['precision_at_5']:<8}% | {rrf_agg['precision_at_5']:<10}% | {full_agg['precision_at_5']:<12}%")
    print(f"{'MAP@5':<20} | {dense_agg['map_at_5']:<12} | {kw_agg['map_at_5']:<10} | {gr_agg['map_at_5']:<10} | {rrf_agg['map_at_5']:<12} | {full_agg['map_at_5']:<14}")
    print(f"{'NDCG@5':<20} | {dense_agg['ndcg_at_5']:<12} | {kw_agg['ndcg_at_5']:<10} | {gr_agg['ndcg_at_5']:<10} | {rrf_agg['ndcg_at_5']:<12} | {full_agg['ndcg_at_5']:<14}")
    print(f"{'Prereq Coverage':<20} | {dense_agg['avg_prereq_coverage']:<10}% | {kw_agg['avg_prereq_coverage']:<8}% | {gr_agg['avg_prereq_coverage']:<8}% | {rrf_agg['avg_prereq_coverage']:<10}% | {full_agg['avg_prereq_coverage']:<12}%")
    print(f"{'Concept Diversity':<20} | {dense_agg['avg_concept_diversity']:<12} | {kw_agg['avg_concept_diversity']:<10} | {gr_agg['avg_concept_diversity']:<10} | {rrf_agg['avg_concept_diversity']:<12} | {full_agg['avg_concept_diversity']:<14}")
    print(f"{'Term Recall':<20} | {dense_agg['avg_term_recall']:<10}% | {kw_agg['avg_term_recall']:<8}% | {gr_agg['avg_term_recall']:<8}% | {rrf_agg['avg_term_recall']:<10}% | {full_agg['avg_term_recall']:<12}%")
    print(f"{'Provenance Rate':<20} | {dense_agg['avg_provenance_rate']:<10}% | {kw_agg['avg_provenance_rate']:<8}% | {gr_agg['avg_provenance_rate']:<8}% | {rrf_agg['avg_provenance_rate']:<10}% | {full_agg['avg_provenance_rate']:<12}%")
    print(f"{'Mean Latency':<20} | {dense_agg['latency']['mean']:<9} ms | {kw_agg['latency']['mean']:<7} ms | {gr_agg['latency']['mean']:<7} ms | {rrf_agg['latency']['mean']:<9} ms | {full_agg['latency']['mean']:<11} ms")
    print("=" * 90)

    return report_payload


if __name__ == "__main__":
    run_hybrid_rag_benchmark()

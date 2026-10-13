"""
SmartInterview — Freeze Dense Baseline (Phase 14)

Executes the pure VectorRetriever over data/evaluation/golden_evaluation_dataset.json,
computes standard retrieval and ranking metrics via evaluation_metrics.py,
and freezes official baseline figures to data/evaluation/frozen_dense_baseline.json.
"""

from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.rag.vector_retriever import VectorRetriever
from app.services.question_service import (
    _init_rag,
    get_embedding_model,
    get_chroma_collection,
    build_rag_query,
)
from app.rag.evaluation_metrics import (
    evaluate_query_run,
    aggregate_evaluation_results,
)


def execute_and_freeze_dense_baseline() -> Dict[str, Any]:
    print("=" * 70)
    print("SmartInterview — Pure Dense RAG Baseline Execution & Freezing (Phase 14)")
    print("=" * 70)

    # Initialize singletons
    print("Initializing Dense RAG singletons (SentenceTransformer + ChromaDB)...")
    _init_rag()
    embedding_model = get_embedding_model()
    collection = get_chroma_collection()

    retriever = VectorRetriever(
        embedding_model=embedding_model,
        collection=collection,
        build_rag_query_fn=build_rag_query,
    )

    golden_file = PROJECT_ROOT / "data" / "evaluation" / "golden_evaluation_dataset.json"
    with open(golden_file, "r", encoding="utf-8") as f:
        golden_dataset = json.load(f)

    print(f"Loaded {len(golden_dataset)} golden evaluation benchmark records.")

    # Warm-up pass to eliminate initial model load / caching skew
    print("Warming up retriever with sample query...")
    _ = retriever.retrieve(query="Warm up query", skill="dns", domains=["cn"], top_k=1)

    query_eval_results = []
    per_query_records = []

    print(f"Evaluating {len(golden_dataset)} queries with top_k=5...")
    for idx, item in enumerate(golden_dataset, 1):
        q_id = item["query_id"]
        q_text = item["query"]
        domain = item["domain"]
        concept = item["concept"]
        bloom_level = item.get("bloom_level", "understand")
        scenario_type = item.get("scenario_type", "standard")
        expected_chunk_ids = set(item.get("expected_chunk_ids", []))
        expected_prereqs = item.get("expected_prerequisites", [])

        start_time = time.perf_counter()
        results = retriever.retrieve(
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
        query_eval_results.append(q_eval)

        retrieved_details = []
        for rank, r in enumerate(results, 1):
            retrieved_details.append({
                "rank": rank,
                "chunk_id": r.chunk_id,
                "domain": r.domain,
                "concept": r.concept,
                "vector_score": r.vector_score,
                "is_ground_truth_match": r.chunk_id in expected_chunk_ids,
                "snippet": r.text[:120].strip() + "...",
            })

        per_query_records.append({
            "query_id": q_id,
            "query": q_text,
            "domain": domain,
            "concept": concept,
            "bloom_level": bloom_level,
            "scenario_type": scenario_type,
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

    aggregate_report = aggregate_evaluation_results(query_eval_results)
    agg_dict = aggregate_report.to_dict()

    frozen_data = {
        "benchmark_metadata": {
            "title": "SmartInterview Official Pure Dense RAG Baseline",
            "frozen_timestamp": datetime.now(timezone.utc).isoformat(),
            "retrieval_mode": "dense",
            "retriever_class": "VectorRetriever",
            "embedding_model": "all-MiniLM-L6-v2 (384-dimensional dense vectors)",
            "vector_store": "ChromaDB (collection: technical_kb)",
            "similarity_metric": "cosine_distance",
            "top_k": 5,
            "total_queries": len(golden_dataset),
            "total_canonical_chunks": 402,
            "domains_evaluated": [
                "cn", "dbms", "design-patterns", "dsa", "ml-dl", "oop", "os", "system-design"
            ],
            "dataset_file": "data/evaluation/golden_evaluation_dataset.json",
        },
        "historical_paper_comparison": {
            "historical_hit_1": 96.97,
            "historical_hit_3": 100.0,
            "historical_hit_5": 100.0,
            "historical_mrr": 0.9798,
            "reproduced_hit_1": agg_dict["hit_at_1"],
            "reproduced_hit_3": agg_dict["hit_at_3"],
            "reproduced_hit_5": agg_dict["hit_at_5"],
            "reproduced_mrr": agg_dict["mrr"],
            "difference_hit_1": round(agg_dict["hit_at_1"] - 96.97, 4),
            "difference_mrr": round(agg_dict["mrr"] - 0.9798, 4),
            "recall_5_explanation": (
                "The original documentation reported Recall@5 as 100.0%, which actually measured "
                "concept Hit@5. Under canonical chunk-level retrieval where each concept possesses "
                "multiple chunks (mean 5-8 chunks), retrieving top-5 yields mathematical Recall@5 of "
                f"{agg_dict['recall_at_5']}% and Precision@5 of {agg_dict['precision_at_5']}%."
            ),
        },
        "frozen_aggregate_metrics": agg_dict,
        "per_query_evaluations": per_query_records,
    }

    out_file = PROJECT_ROOT / "data" / "evaluation" / "frozen_dense_baseline.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(frozen_data, f, indent=2)

    print(f"\nFrozen baseline successfully written to: {out_file}")
    print("\n" + "=" * 70)
    print("FROZEN DENSE BASELINE METRIC SUMMARY")
    print("=" * 70)
    print(f"Total Queries Evaluated: {agg_dict['total_queries']}")
    print(f"Hit@1                  : {agg_dict['hit_at_1']}%  (Historical: 96.97%)")
    print(f"Hit@3                  : {agg_dict['hit_at_3']}%  (Historical: 100.00%)")
    print(f"Hit@5                  : {agg_dict['hit_at_5']}%  (Historical: 100.00%)")
    print(f"MRR                    : {agg_dict['mrr']}      (Historical: 0.9798)")
    print(f"Recall@5 (Chunk-level) : {agg_dict['recall_at_5']}%")
    print(f"Precision@5            : {agg_dict['precision_at_5']}%")
    print(f"MAP@5                  : {agg_dict['map_at_5']}")
    print(f"NDCG@5                 : {agg_dict['ndcg_at_5']}")
    print(f"Prereq Coverage        : {agg_dict['avg_prereq_coverage']}%")
    print(f"Concept Diversity      : {agg_dict['avg_concept_diversity']} distinct concepts")
    print(f"Term Recall            : {agg_dict['avg_term_recall']}%")
    print(f"Provenance Rate        : {agg_dict['avg_provenance_rate']}%")
    print(f"Mean Latency           : {agg_dict['latency']['mean']} ms")
    print(f"P50 / P95 Latency      : {agg_dict['latency']['p50']} ms / {agg_dict['latency']['p95']} ms")
    print("=" * 70)

    return frozen_data


if __name__ == "__main__":
    execute_and_freeze_dense_baseline()

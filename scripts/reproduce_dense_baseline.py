"""
SmartInterview — Reproducible Dense RAG Baseline Evaluation (Phase 1)

Executes and verifies the pure Dense RAG baseline (all-MiniLM-L6-v2 + ChromaDB technical_kb)
without invoking any BM25, Graph, Fusion, or Reranking mechanisms.

Records:
  - Query IDs and text
  - Retrieved Chunk IDs, ranks, cosine distances, and similarities
  - Chunk concepts, domains, and text previews
  - Per-query and aggregate retrieval latencies
  - Hit@1, Hit@3, Hit@5, MRR
  - Comparison against historical research paper baseline (Hit@1=96.97%, Hit@3=100%, MRR=0.9798)
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any

# Ensure backend is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.rag.vector_retriever import VectorRetriever
from app.services.question_service import (
    _init_rag,
    get_embedding_model,
    get_chroma_collection,
    build_rag_query,
)


def run_dense_baseline(save_output: bool = True) -> Dict[str, Any]:
    print("Initializing Dense RAG singletons (SentenceTransformer + ChromaDB)...")
    _init_rag()
    embedding_model = get_embedding_model()
    collection = get_chroma_collection()

    retriever = VectorRetriever(
        embedding_model=embedding_model,
        collection=collection,
        build_rag_query_fn=build_rag_query,
    )

    query_file = PROJECT_ROOT / "data" / "evaluation" / "retrieval_queries.json"
    with open(query_file, "r", encoding="utf-8") as f:
        queries = json.load(f)

    total_queries = len(queries)
    hits_1 = 0
    hits_3 = 0
    hits_5 = 0
    mrr_sum = 0.0
    latencies = []
    detailed_records = []

    print(f"Executing Dense RAG evaluation over {total_queries} benchmark queries...")

    for idx, item in enumerate(queries, 1):
        q_id = f"Q{idx:02d}"
        q_text = item["query"]
        expected_domain = item["expected_domain"]
        expected_concept = item["expected_concept"]

        start_time = time.perf_counter()
        results = retriever.retrieve(
            query=q_text,
            skill=expected_concept,
            domains=[expected_domain],
            top_k=5,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        latencies.append(latency_ms)

        first_correct_rank = -1
        chunk_records = []

        for rank, r in enumerate(results, 1):
            is_match = (
                r.domain.lower() == expected_domain.lower()
                and r.concept.lower() == expected_concept.lower()
            )
            if is_match and first_correct_rank == -1:
                first_correct_rank = rank

            chunk_records.append({
                "rank": rank,
                "chunk_id": r.chunk_id,
                "domain": r.domain,
                "concept": r.concept,
                "vector_distance": r.vector_score,
                "is_concept_match": is_match,
                "text_snippet": r.text[:120].strip() + "...",
            })

        if first_correct_rank != -1:
            if first_correct_rank == 1:
                hits_1 += 1
            if first_correct_rank <= 3:
                hits_3 += 1
            if first_correct_rank <= 5:
                hits_5 += 1
            reciprocal_rank = 1.0 / first_correct_rank
            mrr_sum += reciprocal_rank
        else:
            reciprocal_rank = 0.0

        detailed_records.append({
            "query_id": q_id,
            "query": q_text,
            "expected_domain": expected_domain,
            "expected_concept": expected_concept,
            "latency_ms": round(latency_ms, 2),
            "first_correct_rank": first_correct_rank if first_correct_rank != -1 else None,
            "reciprocal_rank": round(reciprocal_rank, 4),
            "retrieved_chunks": chunk_records,
        })

    hit1_pct = (hits_1 / total_queries) * 100.0
    hit3_pct = (hits_3 / total_queries) * 100.0
    hit5_pct = (hits_5 / total_queries) * 100.0
    mrr_score = mrr_sum / total_queries
    avg_latency = sum(latencies) / len(latencies)
    sorted_lat = sorted(latencies)
    p50_latency = sorted_lat[len(sorted_lat) // 2]
    p95_latency = sorted_lat[int(len(sorted_lat) * 0.95)]

    historical_results = {
        "dataset": "33 canonical queries (retrieval_queries.json)",
        "hit@1": "96.97%",
        "hit@3": "100.00%",
        "recall@5_historical_definition": "100.00% (equated to Hit@5)",
        "mrr": 0.9798,
        "note": "Reported in original research documentation. Recall@5 was historically defined as concept hit rate.",
    }

    reproduced_results = {
        "dataset_size": total_queries,
        "hit@1": round(hit1_pct, 2),
        "hit@3": round(hit3_pct, 2),
        "hit@5": round(hit5_pct, 2),
        "mrr": round(mrr_score, 4),
        "mean_latency_ms": round(avg_latency, 2),
        "p50_latency_ms": round(p50_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
    }

    report = {
        "retrieval_mode": "dense",
        "retriever_class": "VectorRetriever",
        "embedding_model": "all-MiniLM-L6-v2 (384-dim)",
        "vector_store": "ChromaDB (collection: technical_kb)",
        "historical_paper_results": historical_results,
        "newly_reproduced_baseline_results": reproduced_results,
        "query_evaluations": detailed_records,
    }

    if save_output:
        out_dir = PROJECT_ROOT / "data" / "evaluation"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "dense_baseline_reproduced.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed baseline results written to: {out_file}")

    print("\n" + "=" * 65)
    print("DENSE RAG BASELINE: HISTORICAL VS. REPRODUCED RESULTS")
    print("=" * 65)
    print(f"Queries Evaluated : {total_queries}")
    print(f"{'Metric':<20} | {'Historical Paper':<18} | {'Newly Reproduced':<18}")
    print("-" * 65)
    print(f"{'Hit@1':<20} | {historical_results['hit@1']:<18} | {reproduced_results['hit@1']}%")
    print(f"{'Hit@3':<20} | {historical_results['hit@3']:<18} | {reproduced_results['hit@3']}%")
    print(f"{'Hit@5':<20} | {'100.00%':<18} | {reproduced_results['hit@5']}%")
    print(f"{'MRR':<20} | {historical_results['mrr']:<18} | {reproduced_results['mrr']}")
    print(f"{'Mean Latency':<20} | {'N/A (unrecorded)':<18} | {reproduced_results['mean_latency_ms']} ms")
    print(f"{'p50 / p95 Latency':<20} | {'N/A':<18} | {reproduced_results['p50_latency_ms']} ms / {reproduced_results['p95_latency_ms']} ms")
    print("=" * 65)

    return report


if __name__ == "__main__":
    run_dense_baseline()

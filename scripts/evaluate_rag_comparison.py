"""
SmartInterview — End-to-End RAG Comparison & Evaluation Benchmark (Phase 11)

Compares all 4 retrieval strategies across representative technical interview scenarios:
  1. Dense RAG (all-MiniLM-L6-v2 + ChromaDB)
  2. Keyword RAG (BM25Okapi)
  3. Graph RAG (Multi-Hop Knowledge Graph Traversal)
  4. Hybrid Graph RAG (Dense + Keyword + Graph + Contextual Reranking)

Evaluation Scenarios:
  - Scenario 1: Multi-hop prerequisite discovery (ACID properties & transactions)
  - Scenario 2: Exact terminology & syntax retrieval (B-tree indexing & normalization)
  - Scenario 3: Weak-topic foundational remediation (remediating candidate gap in DBMS)
  - Scenario 4: Bloom cognitive progression (Remember vs Analyze)

Computes quantitative metrics:
  - Concept Diversity (unique concepts retrieved in top-k)
  - Prerequisite Coverage (retrieval of foundational prerequisite concepts)
  - Keyword Term Recall (% of query tokens in retrieved text)
  - Execution Latency (milliseconds per query)
"""

import os
import sys
import time
import json
from typing import Dict, List, Any

# Ensure backend directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.vector_retriever import VectorRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.graph_retriever import GraphRetriever
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import get_reranker
from app.rag.graph_store import get_graph_store
from app.services.question_service import _init_rag, get_embedding_model, get_chroma_collection, build_rag_query


def init_all_retrievers():
    """Initialize instances for all four retrieval architectures."""
    _init_rag()
    emb = get_embedding_model()
    chroma = get_chroma_collection()

    vector_ret = VectorRetriever(
        embedding_model=emb,
        collection=chroma,
        build_rag_query_fn=build_rag_query,
    )
    keyword_ret = KeywordRetriever()
    graph_store = get_graph_store()
    graph_ret = GraphRetriever(graph_store=graph_store)

    hybrid_ret = HybridRetriever(
        vector_retriever=vector_ret,
        keyword_retriever=keyword_ret,
        graph_retriever=graph_ret,
        weights={"vector": 0.40, "keyword": 0.25, "graph": 0.35},
        fetch_k=10,
    )
    reranker = get_reranker(backend="semantic", embedding_model=emb)

    return {
        "Dense RAG": vector_ret,
        "Keyword RAG": keyword_ret,
        "Graph RAG": graph_ret,
        "Hybrid Graph RAG": (hybrid_ret, reranker),
    }


def compute_metrics(query: str, results: list, target_prereqs: list[str]) -> dict:
    """Compute quantitative metrics on a retrieved candidate list."""
    if not results:
        return {
            "num_results": 0,
            "unique_concepts": 0,
            "prereq_found": 0,
            "prereq_coverage": 0.0,
            "keyword_recall": 0.0,
            "concepts": [],
        }

    concepts = [r.concept for r in results]
    unique_concepts = list(set(concepts))

    # Prerequisite coverage
    prereq_found = [p for p in target_prereqs if any(p.lower() in c.lower() for c in concepts)]
    prereq_cov = len(prereq_found) / len(target_prereqs) if target_prereqs else 1.0

    # Keyword recall
    q_tokens = set(query.lower().split())
    # remove short tokens
    q_tokens = {t for t in q_tokens if len(t) > 3}
    combined_text = " ".join([r.text for r in results]).lower()
    matches = sum(1 for t in q_tokens if t in combined_text)
    kw_recall = matches / len(q_tokens) if q_tokens else 1.0

    return {
        "num_results": len(results),
        "unique_concepts": len(unique_concepts),
        "prereq_found": len(prereq_found),
        "prereq_coverage": round(prereq_cov, 3),
        "keyword_recall": round(kw_recall, 3),
        "concepts": unique_concepts,
    }


def run_benchmark():
    """Run all evaluation scenarios and collect comparative metrics."""
    retrievers = init_all_retrievers()

    scenarios = [
        {
            "id": "scenario_1_multihop",
            "name": "Scenario 1: Multi-Hop Prerequisite Discovery",
            "query": "ACID properties transaction atomicity consistency isolation durability",
            "skill": "SQL",
            "domains": ["dbms"],
            "target_prereqs": ["Transactions"],
            "bloom_level": "understand",
            "weak_topics": [],
        },
        {
            "id": "scenario_2_keyword",
            "name": "Scenario 2: Exact Terminology & Syntax Retrieval",
            "query": "Database indexing B-tree performance query execution",
            "skill": "SQL",
            "domains": ["dbms"],
            "target_prereqs": [],
            "bloom_level": "apply",
            "weak_topics": [],
        },
        {
            "id": "scenario_3_remediation",
            "name": "Scenario 3: Weak-Topic Foundational Remediation",
            "query": "ACID properties in database transactions",
            "skill": "SQL",
            "domains": ["dbms"],
            "target_prereqs": ["Transactions"],
            "bloom_level": "remember",
            "weak_topics": ["acid-properties", "transactions"],
        },
        {
            "id": "scenario_4_bloom_analyze",
            "name": "Scenario 4: High-Order Bloom Tradeoff Analysis",
            "query": "Database concurrency control locking tradeoffs isolation levels",
            "skill": "SQL",
            "domains": ["dbms"],
            "target_prereqs": [],
            "bloom_level": "analyze",
            "weak_topics": [],
        },
    ]

    benchmark_results = {}

    for sc in scenarios:
        sc_id = sc["id"]
        benchmark_results[sc_id] = {
            "name": sc["name"],
            "query": sc["query"],
            "modes": {},
        }

        for mode_name, ret_obj in retrievers.items():
            start_t = time.perf_counter()

            if mode_name == "Hybrid Graph RAG":
                hybrid_ret, reranker = ret_obj
                raw_res = hybrid_ret.retrieve(
                    query=sc["query"],
                    skill=sc["skill"],
                    domains=sc["domains"],
                    top_k=8,
                    bloom_level=sc["bloom_level"],
                    weak_topics=sc["weak_topics"],
                )
                final_res = reranker.rerank(
                    query=sc["query"],
                    results=raw_res,
                    top_k=3,
                )
            else:
                final_res = ret_obj.retrieve(
                    query=sc["query"],
                    skill=sc["skill"],
                    domains=sc["domains"],
                    top_k=3,
                    bloom_level=sc["bloom_level"],
                    weak_topics=sc["weak_topics"],
                )

            latency_ms = (time.perf_counter() - start_t) * 1000.0
            metrics = compute_metrics(sc["query"], final_res, sc["target_prereqs"])
            metrics["latency_ms"] = round(latency_ms, 2)

            benchmark_results[sc_id]["modes"][mode_name] = {
                "metrics": metrics,
                "chunks": [
                    {
                        "chunk_id": r.chunk_id,
                        "concept": r.concept,
                        "score": round(r.final_score, 4),
                        "retriever": r.retriever,
                        "sources": r.metadata.get("sources", [r.retriever]),
                        "text_snippet": r.text[:120].strip() + "...",
                    }
                    for r in final_res
                ],
            }

    return benchmark_results


if __name__ == "__main__":
    results = run_benchmark()
    print("\n" + "=" * 80)
    print("SMARTINTERVIEW HYBRID GRAPH RAG BENCHMARK RESULTS")
    print("=" * 80)
    for sc_id, data in results.items():
        print(f"\n[SCENARIO] {data['name']}")
        print(f"Query: \"{data['query']}\"")
        print(f"{'Mode':<22} | {'Unique Concepts':<16} | {'Prereq Cov':<12} | {'KW Recall':<10} | {'Latency':<10}")
        print("-" * 78)
        for mode, mdata in data["modes"].items():
            m = mdata["metrics"]
            print(f"{mode:<22} | {m['unique_concepts']:<16} | {m['prereq_coverage']:<12.1%} | {m['keyword_recall']:<10.1%} | {m['latency_ms']:<8.1f}ms")
    print("=" * 80)

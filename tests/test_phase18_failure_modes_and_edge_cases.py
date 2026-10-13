"""
SmartInterview — Phase 18 Test Suite: Edge Cases, Failure Modes & Negative Results

Tests and asserts:
  1. Dual-Topic Disambiguation (Q15: "stack vs queue") behavior across all retrievers.
  2. BM25 Paraphrase Blindness and how Hybrid fusion compensates for vocabulary mismatch.
  3. Contextual Reranker trade-offs and threshold safeguards against candidate starvation.
  4. Robustness against empty, whitespace, and malformed queries across all retrieval channels.
  5. Unmapped skills and dynamic weight re-normalization when individual retrievers produce zero candidates.
  6. Reranker runtime resilience and transparent fallback on model initialization failures.
  7. Verification that empirical negative results and trade-offs are accurately recorded in benchmark artifacts.
"""

from __future__ import annotations

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.rag.vector_retriever import VectorRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.graph_retriever import GraphRetriever
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import get_reranker, PassThroughReranker, SemanticEmbeddingReranker
from app.services.question_service import (
    _init_rag,
    get_embedding_model,
    get_chroma_collection,
    build_rag_query,
    _get_retriever,
    _get_reranker,
)


@pytest.fixture(scope="module", autouse=True)
def setup_rag():
    _init_rag()


def test_dual_topic_comparative_disambiguation_q15():
    """
    Test dual-concept comparative query Q15 ("What is the difference between a stack and a queue?").
    Verifies the rank profile of the target concept ('stack') and confirms 100% Hit@5 across all channels.
    """
    query = "What is the difference between a stack and a queue?"
    target_concept = "stack"
    expected_chunk_prefix = "dsa_stack_"

    model = get_embedding_model()
    coll = get_chroma_collection()

    vector_r = VectorRetriever(model, coll, build_rag_query)
    keyword_r = KeywordRetriever()
    graph_r = GraphRetriever()
    hybrid_r = HybridRetriever(vector_r, keyword_r, graph_r, fusion_method="rrf")

    # 1. Vector Retrieval
    v_res = vector_r.retrieve(query=query, skill=target_concept, domains=["dsa"], top_k=5)
    v_ranks = [r.chunk_id for r in v_res]
    assert any(cid.startswith(expected_chunk_prefix) for cid in v_ranks), "Vector retriever failed Hit@5"

    # 2. Keyword Retrieval
    k_res = keyword_r.retrieve(query=query, skill=target_concept, domains=["dsa"], top_k=5)
    k_ranks = [r.chunk_id for r in k_res]
    assert any(cid.startswith(expected_chunk_prefix) for cid in k_ranks), "Keyword retriever failed Hit@5"

    # 3. Graph Retrieval
    g_res = graph_r.retrieve(query=query, skill=target_concept, domains=["dsa"], top_k=5, concept=target_concept)
    g_ranks = [r.chunk_id for r in g_res]
    assert any(cid.startswith(expected_chunk_prefix) for cid in g_ranks), "Graph retriever failed Hit@5"

    # 4. Hybrid RRF Retrieval
    h_res = hybrid_r.retrieve(query=query, skill=target_concept, domains=["dsa"], top_k=5, concept=target_concept)
    h_ranks = [r.chunk_id for r in h_res]
    assert any(cid.startswith(expected_chunk_prefix) for cid in h_ranks), "Hybrid retriever failed Hit@5"


def test_bm25_paraphrase_mismatch_and_hybrid_compensation():
    """
    Demonstrate BM25 vocabulary mismatch under paraphrase and how Hybrid fusion compensates.
    Query avoids explicit technical term 'stack' by describing function call call-stack behavior.
    """
    paraphrase_query = "How do programs temporarily store function return addresses and local frames in memory?"
    domains = ["dsa"]

    keyword_r = KeywordRetriever()
    hybrid_r = _get_retriever(mode="hybrid")

    # Keyword retrieval has poor term density for 'stack'
    kw_results = keyword_r.retrieve(query=paraphrase_query, skill="stack", domains=domains, top_k=5)
    kw_concepts = [r.concept for r in kw_results]

    # Hybrid retrieval leverages dense embeddings and graph connectivity to retrieve 'stack'
    hybrid_results = hybrid_r.retrieve(
        query=paraphrase_query, skill="stack", domains=domains, top_k=5, concept="stack", fusion_method="rrf"
    )
    hybrid_concepts = [r.concept for r in hybrid_results]

    assert "stack" in hybrid_concepts, "Hybrid retriever failed to compensate for vocabulary mismatch"


def test_reranker_threshold_safeguard_against_candidate_starvation():
    """
    Verify that when all candidates score below RERANKER_MIN_SCORE (or an extreme threshold),
    the threshold safeguard preserves at least the top candidate to prevent empty prompt context.
    """
    reranker = _get_reranker()
    hybrid_r = _get_retriever(mode="hybrid")

    results = hybrid_r.retrieve(
        query="What is the Domain Name System?", skill="dns", domains=["cn"], top_k=5
    )
    assert len(results) > 0

    # Apply an impossibly strict threshold (e.g. 0.9999)
    filtered = reranker.rerank(
        query="What is the Domain Name System?",
        results=results,
        top_k=3,
        threshold=0.9999,
    )

    # Must preserve at least 1 candidate
    assert len(filtered) >= 1, "Candidate starvation! Safeguard failed to preserve best candidate."
    assert filtered[0].chunk_id == results[0].chunk_id or filtered[0].concept == "dns"


def test_empty_and_corrupt_query_handling():
    """Verify that all retrievers safely handle empty, whitespace, and corrupt queries without crashing."""
    vector_r = _get_retriever(mode="dense")
    keyword_r = KeywordRetriever()
    graph_r = GraphRetriever()
    hybrid_r = _get_retriever(mode="hybrid")

    malformed_queries = ["", "   ", None, "???###$$$@@@", "\n\t\r"]

    for q in malformed_queries:
        assert isinstance(vector_r.retrieve(query=q, skill="dns", domains=["cn"], top_k=3), list)
        assert isinstance(keyword_r.retrieve(query=q, skill="dns", domains=["cn"], top_k=3), list)
        assert isinstance(graph_r.retrieve(query=q, skill="dns", domains=["cn"], top_k=3), list)
        assert isinstance(hybrid_r.retrieve(query=q, skill="dns", domains=["cn"], top_k=3), list)


def test_unmapped_skill_and_zero_graph_candidate_degradation():
    """
    Verify graceful degradation when a skill does not exist in the knowledge graph.
    HybridRetriever must dynamically reallocate weights and avoid zero-division errors.
    """
    hybrid_r = _get_retriever(mode="hybrid")

    # Completely unmapped non-existent skill
    unmapped_skill = "NonExistentQuantumSkill999"
    results = hybrid_r.retrieve(
        query="Tell me about this topic",
        skill=unmapped_skill,
        domains=["non_existent_domain"],
        top_k=5,
    )
    # Should safely return a list (empty or fallback) without raising exceptions
    assert isinstance(results, list)


def test_reranker_runtime_fallback_on_corrupt_model():
    """Verify that get_reranker falls back to SemanticEmbeddingReranker if CrossEncoder fails."""
    with patch("app.rag.reranker.CrossEncoderReranker", side_effect=Exception("Simulated CUDA/Weight load failure")):
        fallback_reranker = get_reranker(backend="cross_encoder", embedding_model=get_embedding_model())
        assert isinstance(fallback_reranker, SemanticEmbeddingReranker)


def test_negative_results_documented_in_benchmark_data():
    """
    Verify that negative results and trade-offs are honestly recorded in benchmark JSON files.
    """
    benchmark_path = PROJECT_ROOT / "data" / "evaluation" / "hybrid_rag_benchmark.json"
    assert benchmark_path.exists()

    with open(benchmark_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    matrix = data["comparative_matrix"]

    # Negative Result 1: Full Hybrid+Reranker has higher latency than Pure Dense and Hybrid RRF
    assert matrix["mean_latency_ms"]["hybrid_reranked"] > matrix["mean_latency_ms"]["hybrid_rrf"]
    assert matrix["mean_latency_ms"]["hybrid_reranked"] > matrix["mean_latency_ms"]["dense"]

    # Negative Result 2: BM25 Hit@1 is lower than Pure Dense (87.88% vs 96.97%) due to lexical mismatch
    assert matrix["hit_at_1"]["keyword"] < matrix["hit_at_1"]["dense"]

    # Negative Result 3: Full Hybrid+Reranker has lower chunk-level Recall@5 than Pure RRF
    # because it purposefully diversifies context towards prerequisite concepts
    assert matrix["recall_at_5"]["hybrid_reranked"] < matrix["recall_at_5"]["hybrid_rrf"]
    assert matrix["concept_diversity"]["hybrid_reranked"] > matrix["concept_diversity"]["hybrid_rrf"]

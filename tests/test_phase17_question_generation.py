"""
SmartInterview — Phase 17 Test Suite: Qualitative Question Generation Evaluation

Tests and asserts:
  1. The evaluation artifact (data/evaluation/question_generation_evaluation.json) exists and conforms to schema.
  2. Grounding score reflects strong factual alignment with retrieved knowledge chunks (>= 35%).
  3. Bloom's Taxonomy cognitive alignment achieves 100% in Hybrid Graph RAG.
  4. Knowledge Graph Prerequisite Context Enrichment is active in Hybrid Graph RAG (>= 50%) and absent in Pure Dense (0%).
  5. Transition naturalness is high (>= 90%) with zero artificial filler praise.
  6. Live question generation contract returns valid metadata and full context shapes.
"""

from __future__ import annotations

import os
import sys
import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

EVAL_PATH = PROJECT_ROOT / "data" / "evaluation" / "question_generation_evaluation.json"


@pytest.fixture(scope="module")
def eval_data():
    assert EVAL_PATH.exists(), f"Evaluation file missing at: {EVAL_PATH}"
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_question_generation_evaluation_file_exists_and_schema(eval_data):
    """Verify top-level structure of the qualitative evaluation report."""
    assert "metadata" in eval_data
    assert "aggregate_comparison" in eval_data
    assert "scenarios" in eval_data

    meta = eval_data["metadata"]
    assert meta["total_scenarios"] == 8
    assert len(meta["bloom_levels_covered"]) == 6
    assert meta["domains_covered"] == 8


def test_grounding_and_factual_alignment(eval_data):
    """Verify that generated questions maintain high token grounding from retrieved context."""
    grounding = eval_data["aggregate_comparison"]["grounding_score"]

    assert grounding["dense"] >= 35.0
    assert grounding["hybrid"] >= 35.0

    # Verify individual scenarios have positive grounding
    for scen in eval_data["scenarios"]:
        assert scen["dense_generation"]["grounding_score"] > 0.0
        assert scen["hybrid_generation"]["grounding_score"] > 0.0


def test_bloom_taxonomy_fidelity(eval_data):
    """Verify that Hybrid Graph RAG achieves perfect Bloom's taxonomy cognitive alignment."""
    bloom_agg = eval_data["aggregate_comparison"]["bloom_alignment_score"]

    assert bloom_agg["hybrid"] == 100.0
    assert bloom_agg["dense"] >= 90.0

    # Ensure every single scenario in Hybrid mode achieved 1.0 Bloom alignment
    for scen in eval_data["scenarios"]:
        assert scen["hybrid_generation"]["bloom_alignment_score"] == 1.0


def test_prerequisite_context_enrichment(eval_data):
    """Verify that Hybrid Graph RAG enriches prompt with graph prerequisites, while Dense is blind."""
    agg = eval_data["aggregate_comparison"]

    assert agg["prerequisite_context_enrichment_rate"] >= 50.0

    # In scenarios with weak topics, verify that hybrid generation incorporated prerequisite context
    weak_topic_scenarios = [s for s in eval_data["scenarios"] if s["weak_topics"]]
    assert len(weak_topic_scenarios) >= 4
    for s in weak_topic_scenarios:
        assert s["hybrid_generation"]["has_prereq_context"] is True


def test_conversational_transitions_and_filler_absence(eval_data):
    """Verify natural transitions and complete absence of filler praise."""
    trans_agg = eval_data["aggregate_comparison"]["transition_naturalness"]

    assert trans_agg["hybrid"] >= 90.0
    assert trans_agg["dense"] >= 90.0

    filler_tokens = ["great job", "awesome", "excellent answer", "well done", "perfect"]
    for s in eval_data["scenarios"]:
        q_text = s["hybrid_generation"]["question_text"].lower()
        for f in filler_tokens:
            assert f not in q_text, f"Filler token '{f}' found in: {q_text}"


def test_live_question_generation_contract():
    """Verify live question generation contract produces decoupled rag_context and rag_context_full."""
    from app.services.question_service import generate_single_question
    from app.services.bloom import UNDERSTAND

    result = generate_single_question(
        skill="dns",
        difficulty="easy",
        question_type="conceptual",
        bloom_level=UNDERSTAND,
        rag_mode="hybrid",
    )

    assert "question_text" in result
    assert len(result["question_text"]) > 15
    assert "rag_context" in result
    assert "rag_context_full" in result

    # Check decoupling: rag_context has no 'text', rag_context_full has 'text'
    if result["rag_context"]:
        assert "text" not in result["rag_context"][0]
    if result["rag_context_full"]:
        assert "text" in result["rag_context_full"][0]

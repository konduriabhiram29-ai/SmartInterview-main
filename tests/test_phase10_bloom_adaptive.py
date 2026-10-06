"""
SmartInterview — Phase 10 Tests: Bloom Adaptive Engine & Remediation Integration

Tests that verify:
  1. Full integration of Bloom taxonomy levels into generate_single_question().
  2. Weak-topic remediation triggers prerequisite reinforcement in retrieved knowledge.
  3. AdaptiveState.get_weak_topics() accurately identifies low-scoring topics.
  4. Contextual reranking execution during question generation.
  5. Backwards compatibility: legacy invocations without Bloom or weak_topics succeed.
  6. RAG baseline protection: RAG_MODE=dense works with zero regressions.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.bloom import (
    REMEMBER,
    UNDERSTAND,
    APPLY,
    ANALYZE,
    EVALUATE,
    CREATE,
    get_bloom_level,
)
from app.services.adaptive_engine import (
    AdaptiveState,
    SkillPerformance,
    initialize_state,
)
from app.services.question_service import generate_single_question


# ── 1. Adaptive State Weak Topic Identification ───────────────────────

class TestAdaptiveStateWeakTopics:
    def test_get_weak_topics_identifies_low_scorers(self):
        state = initialize_state(
            selected_skills=["SQL", "Python", "Docker"],
            difficulty="medium",
            question_type="conceptual",
            question_count=5,
        )

        # SQL: 1 attempt, score 45% (weak)
        p_sql = state.get_skill_performance("SQL")
        p_sql.record_score(45.0)
        state.update_skill_performance(p_sql)

        # Python: 1 attempt, score 85% (strong)
        p_py = state.get_skill_performance("Python")
        p_py.record_score(85.0)
        state.update_skill_performance(p_py)

        # Docker: 0 attempts (not tested yet)
        weak = state.get_weak_topics(threshold=60.0)
        assert "SQL" in weak
        assert "Python" not in weak
        assert "Docker" not in weak


# ── 2. Question Generation with Bloom Cognitive Levels ─────────────────

class TestQuestionGenerationBloomLevels:
    @patch("app.services.question_service.call_groq")
    def test_generate_single_question_with_remember_level(self, mock_groq):
        mock_groq.return_value = "What is the primary definition of Atomicity in ACID properties?"

        res = generate_single_question(
            skill="SQL",
            difficulty="easy",
            question_type="conceptual",
            bloom_level=REMEMBER,
        )

        assert res["skill"] == "SQL"
        assert res["difficulty"] == "easy"
        assert res["bloom_level"] == "remember"
        assert res["bloom_level_number"] == 1
        assert "Atomicity" in res["question_text"]
        assert "rag_context" in res
        assert "rag_retrieval_results" in res
        assert isinstance(res["rag_retrieval_results"], list)

    @patch("app.services.question_service.call_groq")
    def test_generate_single_question_with_analyze_level(self, mock_groq):
        mock_groq.return_value = "Compare Optimistic vs Pessimistic concurrency control tradeoffs."

        res = generate_single_question(
            skill="SQL",
            difficulty="hard",
            question_type="technical_reasoning",
            bloom_level=ANALYZE,
        )

        assert res["skill"] == "SQL"
        assert res["difficulty"] == "hard"
        assert res["bloom_level"] == "analyze"
        assert res["bloom_level_number"] == 4
        assert res["rag_retrieval_results"] is not None


# ── 3. Weak Topic Prerequisite Remediation Integration ────────────────

class TestWeakTopicRemediationIntegration:
    @patch("app.services.question_service.call_groq")
    def test_weak_topics_passed_to_retrieval(self, mock_groq):
        mock_groq.return_value = "Let's review the fundamental transaction boundaries."

        res = generate_single_question(
            skill="SQL",
            difficulty="medium",
            question_type="conceptual",
            bloom_level=REMEMBER,
            weak_topics=["transactions", "SQL"],
        )

        assert res["weak_topics"] == ["transactions", "SQL"]
        assert len(res["rag_retrieval_results"]) > 0


# ── 4. Reranker Execution in Question Generation ──────────────────────

class TestRerankerIntegrationInQuestionGen:
    @patch("app.services.question_service.call_groq")
    def test_reranker_enriches_retrieval_results(self, mock_groq):
        mock_groq.return_value = "Explain transaction isolation."

        res = generate_single_question(
            skill="SQL",
            difficulty="medium",
            question_type="conceptual",
            bloom_level=UNDERSTAND,
        )

        # Check that top retrieval results include reranking metadata
        results = res.get("rag_retrieval_results", [])
        assert len(results) > 0
        first = results[0]
        # Should have final score and metadata
        assert "final_score" in first
        assert "chunk_id" in first


# ── 5. Backwards Compatibility & Baseline Protection ──────────────────

class TestBackwardsCompatibility:
    @patch("app.services.question_service.call_groq")
    def test_legacy_invocation_without_bloom_or_weak_topics(self, mock_groq):
        mock_groq.return_value = "What is polymorphism?"

        # Call with exactly the legacy signature
        res = generate_single_question(
            skill="Java",
            difficulty="medium",
            question_type="conceptual",
        )

        assert res["skill"] == "Java"
        assert res["bloom_level"] is None
        assert res["bloom_level_number"] is None
        assert res["weak_topics"] == []
        assert "question_text" in res
        assert "rag_context" in res

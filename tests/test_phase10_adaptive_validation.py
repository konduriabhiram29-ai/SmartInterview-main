"""
SmartInterview — Phase 10 Tests: Bloom's Taxonomy & Weak-Topic Adaptive Engine Validation

Comprehensive test suite verifying:
  1. Full cognitive progression across all 6 Bloom levels:
     REMEMBER (1) -> UNDERSTAND (2) -> APPLY (3) -> ANALYZE (4) -> EVALUATE (5) -> CREATE (6).
  2. Ceiling and floor boundary protections:
     - Ceiling: at Create (6), high score advances difficulty (easy -> medium -> hard) and caps cleanly.
     - Floor: at Remember (1), low score regresses difficulty (hard -> medium -> easy) and floors cleanly.
     - Neutral band (50-79): maintains exact Bloom order and difficulty.
  3. Weakness-biased skill selection: ensures coverage and prioritizes lowest scoring skills.
  4. AdaptiveState serialization, deserialization, and auto-stop safety criteria.
  5. End-to-end weak-topic remediation flow with Knowledge Graph prerequisite retrieval.
  6. Final session summary calculation and personalized recommendation generation.
"""

from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.bloom import (
    BloomLevel,
    REMEMBER,
    UNDERSTAND,
    APPLY,
    ANALYZE,
    EVALUATE,
    CREATE,
    ALL_LEVELS,
    get_bloom_level,
    next_level,
    prev_level,
    clamp_bloom_order,
)
from app.services.adaptive_engine import (
    AdaptiveState,
    SkillPerformance,
    AdaptiveDecision,
    initialize_state,
    decide_next,
    select_skill,
    select_question_type,
    generate_recommendations,
    calculate_session_summary,
    ADVANCE_THRESHOLD,
    MAINTAIN_LOWER,
)
from app.services.question_service import generate_single_question
from app.rag.retrieval_result import RetrievalResult


# ── 1. Bloom Cognitive Progression & Boundaries ───────────────────────

class TestBloomCognitiveProgression:
    def test_all_six_bloom_levels_order_and_properties(self):
        assert len(ALL_LEVELS) == 6
        orders = [lvl.order for lvl in ALL_LEVELS]
        assert orders == [1, 2, 3, 4, 5, 6]
        ids = [lvl.id for lvl in ALL_LEVELS]
        assert ids == ["remember", "understand", "apply", "analyze", "evaluate", "create"]

    def test_progression_across_all_six_levels(self):
        """Simulate candidate getting consecutive high scores (>= 80) advancing from 1 to 6."""
        state = initialize_state(
            selected_skills=["SQL"],
            difficulty="easy",
            question_type="conceptual",
            question_count=10,
        )

        expected_orders = [1, 2, 3, 4, 5, 6]
        current_expected_order = 1

        for expected in expected_orders[1:]:
            decision = decide_next(state, overall_score=85.0)
            assert decision.bloom_level.order == expected
            assert decision.skill == "SQL"

    def test_ceiling_protection_advances_difficulty_then_caps(self):
        """At Create (6), score >= 80 advances difficulty: easy -> medium -> hard, then caps."""
        state = initialize_state(
            selected_skills=["Python"],
            difficulty="easy",
            question_type="practical",
            question_count=10,
        )
        perf = state.get_skill_performance("Python")
        perf.current_bloom_order = 6  # Already at Create
        perf.current_difficulty = "easy"
        state.update_skill_performance(perf)
        state.current_bloom_id = "create"
        state.current_difficulty = "easy"

        # Advancement 1: easy -> medium
        d1 = decide_next(state, overall_score=90.0)
        assert d1.bloom_level.order == 6
        assert d1.difficulty == "medium"

        # Advancement 2: medium -> hard
        d2 = decide_next(state, overall_score=95.0)
        assert d2.bloom_level.order == 6
        assert d2.difficulty == "hard"

        # Advancement 3: already at hard -> remains hard, remains Create (no crash or overflow)
        d3 = decide_next(state, overall_score=98.0)
        assert d3.bloom_level.order == 6
        assert d3.difficulty == "hard"

    def test_regression_across_levels(self):
        """Simulate candidate getting consecutive low scores (< 50) regressing from 6 to 1."""
        state = initialize_state(
            selected_skills=["Docker"],
            difficulty="hard",
            question_type="scenario",
            question_count=10,
        )
        perf = state.get_skill_performance("Docker")
        perf.current_bloom_order = 6
        perf.current_difficulty = "hard"
        state.update_skill_performance(perf)
        state.current_bloom_id = "create"
        state.current_difficulty = "hard"

        expected_regressions = [5, 4, 3, 2, 1]
        for expected in expected_regressions:
            decision = decide_next(state, overall_score=40.0)
            assert decision.bloom_level.order == expected

    def test_floor_protection_lowers_difficulty_then_floors(self):
        """At Remember (1), score < 50 lowers difficulty: hard -> medium -> easy, then floors."""
        state = initialize_state(
            selected_skills=["Docker"],
            difficulty="hard",
            question_type="conceptual",
            question_count=10,
        )
        # Already at Remember (1)
        assert state.current_bloom_id == "remember"
        assert state.current_difficulty == "hard"

        # Regression 1: hard -> medium
        d1 = decide_next(state, overall_score=35.0)
        assert d1.bloom_level.order == 1
        assert d1.difficulty == "medium"

        # Regression 2: medium -> easy
        d2 = decide_next(state, overall_score=30.0)
        assert d2.bloom_level.order == 1
        assert d2.difficulty == "easy"

        # Regression 3: already at easy -> remains easy, remains Remember
        d3 = decide_next(state, overall_score=25.0)
        assert d3.bloom_level.order == 1
        assert d3.difficulty == "easy"

    def test_maintain_band_preserves_level_and_difficulty(self):
        """Score between 50 and 79 maintains exact level and difficulty."""
        state = initialize_state(
            selected_skills=["Java"],
            difficulty="medium",
            question_type="conceptual",
            question_count=5,
        )
        perf = state.get_skill_performance("Java")
        perf.current_bloom_order = 3  # Apply
        state.update_skill_performance(perf)
        state.current_bloom_id = "apply"

        d = decide_next(state, overall_score=65.0)
        assert d.bloom_level.order == 3
        assert d.difficulty == "medium"


# ── 2. Weakness-Biased Skill Selection ────────────────────────────────

class TestSkillSelectionAndWeaknessBias:
    def test_round_robin_coverage_among_untested_skills(self):
        state = initialize_state(
            selected_skills=["Python", "SQL", "Docker"],
            difficulty="medium",
            question_type="conceptual",
            question_count=6,
        )
        # Question 1 was Python
        state.current_skill = "Python"
        perf_py = state.get_skill_performance("Python")
        perf_py.record_score(75.0)
        state.update_skill_performance(perf_py)

        # Next skill should be one of the untested skills (SQL or Docker)
        next_s = select_skill(state)
        assert next_s in ["SQL", "Docker"]

    def test_weakness_priority_among_equally_attempted(self):
        state = initialize_state(
            selected_skills=["Python", "SQL", "Docker"],
            difficulty="medium",
            question_type="conceptual",
            question_count=6,
        )
        # All 3 have 1 attempt:
        # Python: 85%
        # SQL: 45% (weakest)
        # Docker: 70%
        for skill, score in [("Python", 85.0), ("SQL", 45.0), ("Docker", 70.0)]:
            p = state.get_skill_performance(skill)
            p.record_score(score)
            state.update_skill_performance(p)

        next_s = select_skill(state)
        # SQL has lowest avg_score, must be selected!
        assert next_s == "SQL"


# ── 3. Adaptive State Lifecycle & Serialization ───────────────────────

class TestAdaptiveStateLifecycle:
    def test_serialization_and_deserialization_roundtrip(self):
        state = initialize_state(
            selected_skills=["SQL", "Python"],
            difficulty="medium",
            question_type="conceptual",
            question_count=5,
        )
        state.questions_generated = 2
        state.questions_answered = 2
        state.previous_questions = ["Q1 text", "Q2 text"]

        serialized = state.serialize()
        assert isinstance(serialized, dict)
        assert serialized["questions_generated"] == 2

        restored = AdaptiveState.deserialize(serialized)
        assert restored.selected_skills == ["SQL", "Python"]
        assert restored.questions_generated == 2
        assert restored.questions_answered == 2
        assert restored.previous_questions == ["Q1 text", "Q2 text"]

    def test_auto_stop_and_remaining_questions(self):
        state = initialize_state(
            selected_skills=["SQL"],
            difficulty="easy",
            question_type="conceptual",
            question_count=3,
        )
        assert state.questions_remaining == 3
        assert not state.is_complete

        state.questions_generated = 3
        state.questions_answered = 3
        assert state.questions_remaining == 0
        assert state.is_complete


# ── 4. End-to-End Weak Topic Prerequisite Remediation Flow ─────────────

class TestWeakTopicPrerequisiteRemediationFlow:
    @patch("app.services.question_service.call_groq")
    @patch("app.services.question_service._get_retriever")
    def test_low_score_triggers_graph_prerequisite_remediation(self, mock_get_retriever, mock_groq):
        """
        Flow:
        1. Candidate scores 35% on SQL Transactions -> added to weak topics.
        2. decide_next identifies SQL as weak topic.
        3. Next question generated with rag_mode='graph' and weak_topics=['SQL'].
        4. GraphRetriever retrieves prerequisite concepts and prompts LLM accordingly.
        """
        state = initialize_state(
            selected_skills=["SQL"],
            difficulty="medium",
            question_type="conceptual",
            question_count=5,
        )

        # Candidate fails question with score 35.0
        decide_next(state, overall_score=35.0)

        weak_topics = state.get_weak_topics(threshold=60.0)
        assert "SQL" in weak_topics

        # Mock GraphRetriever returning a prerequisite chunk
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [
            RetrievalResult(
                chunk_id="dbms_acid_01",
                text="Atomicity ensures database operations succeed or fail as a single unit.",
                domain="dbms",
                concept="Atomicity",
                final_score=0.95,
                retriever="graph",
                metadata={"role": "prerequisite", "remediation": True},
            )
        ]
        mock_get_retriever.return_value = mock_retriever
        mock_groq.return_value = "Let's review atomicity before exploring transactions."

        res = generate_single_question(
            skill="SQL",
            difficulty=state.current_difficulty,
            question_type="conceptual",
            bloom_level=get_bloom_level(state.current_bloom_id),
            weak_topics=weak_topics,
            rag_mode="graph",
        )

        assert res["weak_topics"] == ["SQL"]
        assert res["rag_mode"] == "graph"
        assert len(res["rag_retrieval_results"]) > 0

        # Verify LLM prompt received the prerequisite guidance
        user_prompt = mock_groq.call_args[0][1]
        assert "Knowledge Graph Prerequisite Context:" in user_prompt
        assert "Atomicity" in user_prompt


# ── 5. Session Summary & Personalized Recommendations ─────────────────

class TestSessionSummaryAndRecommendations:
    def test_summary_and_recommendations_generation(self):
        state = initialize_state(
            selected_skills=["SQL", "Python"],
            difficulty="medium",
            question_type="conceptual",
            question_count=4,
        )

        # SQL: 2 attempts, poor score 35%
        p_sql = state.get_skill_performance("SQL")
        p_sql.record_score(30.0)
        p_sql.record_score(40.0)
        state.update_skill_performance(p_sql)

        # Python: 2 attempts, excellent score 90%
        p_py = state.get_skill_performance("Python")
        p_py.record_score(90.0)
        p_py.record_score(90.0)
        p_py.current_bloom_order = 5  # Evaluate
        state.update_skill_performance(p_py)

        summary = calculate_session_summary(state)
        assert summary["total_questions_answered"] == 4
        # (35 + 90) / 2 = 62.5
        assert summary["overall_average_score"] == 62.5

        recs = summary["recommendations"]
        assert len(recs) > 0
        sql_rec = next(r for r in recs if r["skill"] == "SQL")
        assert sql_rec["priority"] == "high"
        assert "significant improvement" in sql_rec["message"]

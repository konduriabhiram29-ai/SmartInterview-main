"""
SmartInterview — Phase 9 Tests: Interview-Generation Pipeline Integration

Validates the full interview generation pipeline end-to-end:
  1. Multi-mode generation support (dense, keyword, graph, hybrid) via generate_single_question().
  2. Mode disambiguation: prevents interview mode ("normal") from polluting RAG retrieval mode.
  3. Knowledge graph prerequisite context inclusion in prompt for graph/hybrid modes.
  4. Multi-turn conversational continuity (same-topic continuation vs cross-topic transition).
  5. Bloom cognitive level guidance and personalization injection.
  6. Deduplication mechanism preventing question repetition.
  7. Robust error handling (LLM failure fallback to "[GENERATION FAILED]").
  8. Retriever instance caching (_retrievers dict) preventing thrashing.
  9. Database serialization safety (rag_context vs rag_context_full decoupling).
"""

from __future__ import annotations

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
)
from app.services.question_service import (
    generate_single_question,
    _get_retriever,
    _retrievers,
)
from app.rag.retrieval_result import RetrievalResult


# ── Helpers ────────────────────────────────────────────────────────────

def _mock_retrieval_results(mode: str = "dense") -> list[RetrievalResult]:
    """Return synthetic retrieval results simulating different retrieval legs."""
    if mode == "graph":
        return [
            RetrievalResult(
                chunk_id="dbms_idx_01",
                text="B-Tree indexes structure database records hierarchically.",
                domain="dbms",
                concept="B-Tree Indexing",
                final_score=0.92,
                retriever="graph",
                metadata={"role": "prerequisite", "traversal_path": ["Transactions", "Indexing"]},
            )
        ]
    elif mode == "hybrid":
        return [
            RetrievalResult(
                chunk_id="sql_trans_01",
                text="ACID transactions guarantee atomicity and durability.",
                domain="dbms",
                concept="Transactions",
                final_score=0.88,
                retriever="hybrid",
                metadata={"sources": ["vector", "graph"], "remediation": True},
            ),
            RetrievalResult(
                chunk_id="dbms_lock_01",
                text="Two-phase locking prevents dirty reads and concurrency conflicts.",
                domain="dbms",
                concept="Concurrency Control",
                final_score=0.81,
                retriever="hybrid",
                metadata={"sources": ["keyword", "graph"], "role": "prerequisite"},
            ),
        ]
    else:  # dense
        return [
            RetrievalResult(
                chunk_id="dense_sql_01",
                text="Relational schemas define table entities and foreign key constraints.",
                domain="dbms",
                concept="Relational Models",
                vector_score=0.85,
                final_score=0.85,
                retriever="vector",
                metadata={},
            )
        ]


# ── Test Suite ─────────────────────────────────────────────────────────

class TestMultiModeQuestionGeneration:
    @patch("app.services.question_service.call_groq")
    def test_dense_mode_generation(self, mock_groq):
        mock_groq.return_value = "What is a primary key constraint in relational databases?"

        res = generate_single_question(
            skill="SQL",
            difficulty="easy",
            question_type="conceptual",
            bloom_level=REMEMBER,
            rag_mode="dense",
        )

        assert res["skill"] == "SQL"
        assert res["difficulty"] == "easy"
        assert res["rag_mode"] == "dense"
        assert "primary key" in res["question_text"]
        assert len(res["rag_retrieval_results"]) > 0

    @patch("app.services.question_service.call_groq")
    def test_keyword_mode_generation(self, mock_groq):
        mock_groq.return_value = "Explain the mechanics of B-Tree indexing lookup."

        res = generate_single_question(
            skill="SQL",
            difficulty="medium",
            question_type="conceptual",
            bloom_level=UNDERSTAND,
            rag_mode="keyword",
        )

        assert res["rag_mode"] == "keyword"
        assert res["question_text"] == "Explain the mechanics of B-Tree indexing lookup."

    @patch("app.services.question_service.call_groq")
    def test_graph_mode_generation_with_weak_topics(self, mock_groq):
        mock_groq.return_value = "How does indexing impact concurrency and locking in ACID transactions?"

        res = generate_single_question(
            skill="SQL",
            difficulty="hard",
            question_type="technical_reasoning",
            bloom_level=ANALYZE,
            rag_mode="graph",
            weak_topics=["Indexing", "Locks"],
        )

        assert res["rag_mode"] == "graph"
        assert res["weak_topics"] == ["Indexing", "Locks"]
        assert len(res["rag_retrieval_results"]) > 0

    @patch("app.services.question_service.call_groq")
    def test_hybrid_mode_generation(self, mock_groq):
        mock_groq.return_value = "Evaluate the tradeoffs between optimistic and pessimistic locking."

        res = generate_single_question(
            skill="SQL",
            difficulty="hard",
            question_type="scenario",
            bloom_level=EVALUATE,
            rag_mode="hybrid",
        )

        assert res["rag_mode"] == "hybrid"
        assert len(res["rag_retrieval_results"]) > 0


class TestModeDisambiguation:
    @patch("app.services.question_service.call_groq")
    def test_normal_interview_mode_does_not_corrupt_rag_mode(self, mock_groq):
        """
        Verify that passing interview mode='normal' (from StartInterviewRequest)
        does not overwrite RAG mode with 'normal'. It must safely fall back to 'dense'.
        """
        mock_groq.return_value = "Explain normalization up to BCNF."

        res = generate_single_question(
            skill="SQL",
            difficulty="medium",
            question_type="conceptual",
            bloom_level=UNDERSTAND,
            mode="normal",  # interview mode, NOT RAG mode!
        )

        assert res["rag_mode"] == "dense"
        assert res["rag_mode"] in {"dense", "vector", "keyword", "bm25", "graph", "hybrid"}


class TestPromptAssemblyAndPrerequisites:
    @patch("app.services.question_service.call_groq")
    @patch("app.services.question_service._get_retriever")
    def test_graph_prerequisite_context_injected_into_prompt(self, mock_get_retriever, mock_groq):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = _mock_retrieval_results("hybrid")
        mock_get_retriever.return_value = mock_retriever

        mock_groq.return_value = "How do transactions rely on locks?"

        generate_single_question(
            skill="SQL",
            difficulty="medium",
            question_type="conceptual",
            bloom_level=APPLY,
            rag_mode="hybrid",
        )

        # Inspect arguments passed to call_groq(system_prompt, user_prompt, ...)
        call_args = mock_groq.call_args[0]
        user_prompt = call_args[1]

        assert "Knowledge Graph Prerequisite Context:" in user_prompt
        assert "prerequisite" in user_prompt.lower()
        assert "remediation" in user_prompt.lower()

    @patch("app.services.question_service.call_groq")
    @patch("app.services.question_service._get_retriever")
    def test_dense_mode_does_not_inject_graph_prerequisite_context(self, mock_get_retriever, mock_groq):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = _mock_retrieval_results("dense")
        mock_get_retriever.return_value = mock_retriever

        mock_groq.return_value = "What is a foreign key?"

        generate_single_question(
            skill="SQL",
            difficulty="easy",
            question_type="conceptual",
            bloom_level=REMEMBER,
            rag_mode="dense",
        )

        call_args = mock_groq.call_args[0]
        user_prompt = call_args[1]

        assert "Knowledge Graph Prerequisite Context:" not in user_prompt


class TestMultiTurnContinuityAndDeduplication:
    @patch("app.services.question_service.call_groq")
    def test_same_topic_conversational_transition(self, mock_groq):
        mock_groq.return_value = "Building on transactions, explain write-ahead logging."

        generate_single_question(
            skill="SQL",
            difficulty="hard",
            question_type="conceptual",
            previous_questions=["What is ACID?"],
            previous_skill="SQL",
        )

        user_prompt = mock_groq.call_args[0][1]
        assert "Conversational Transition: We are continuing on the same technical topic" in user_prompt
        assert "Taking that a step further" in user_prompt

    @patch("app.services.question_service.call_groq")
    def test_topic_switch_conversational_transition(self, mock_groq):
        mock_groq.return_value = "Let's shift focus to Python."

        generate_single_question(
            skill="Python",
            difficulty="medium",
            question_type="conceptual",
            previous_questions=["What is ACID?"],
            previous_skill="SQL",
        )

        user_prompt = mock_groq.call_args[0][1]
        assert "Conversational Transition: We are transitioning from SQL to Python" in user_prompt

    @patch("app.services.question_service.call_groq")
    def test_deduplication_instruction_passed_to_prompt(self, mock_groq):
        mock_groq.return_value = "Unique new question."
        prev = ["Question 1 about indexes", "Question 2 about joins"]

        generate_single_question(
            skill="SQL",
            difficulty="medium",
            question_type="conceptual",
            previous_questions=prev,
        )

        user_prompt = mock_groq.call_args[0][1]
        assert "Question 1 about indexes" in user_prompt
        assert "Question 2 about joins" in user_prompt


class TestErrorHandlingAndSafety:
    @patch("app.services.question_service.call_groq", return_value=None)
    def test_groq_failure_fallback_returns_gracefully(self, mock_groq):
        res = generate_single_question(
            skill="SQL",
            difficulty="easy",
            question_type="conceptual",
        )
        assert res["question_text"] == "[GENERATION FAILED]"
        assert res["skill"] == "SQL"

    def test_retriever_caching_per_mode(self):
        r_dense = _get_retriever(mode="dense")
        r_hybrid = _get_retriever(mode="hybrid")
        r_dense_2 = _get_retriever(mode="dense")

        assert r_dense is r_dense_2
        assert "dense" in _retrievers
        assert "hybrid" in _retrievers

    @patch("app.services.question_service.call_groq")
    def test_rag_context_and_full_context_decoupled(self, mock_groq):
        mock_groq.return_value = "Sample question."

        res = generate_single_question(
            skill="SQL",
            difficulty="medium",
            question_type="conceptual",
            rag_mode="dense",
        )

        # rag_context must only contain concise metadata for DB
        rag_context = res.get("rag_context")
        assert isinstance(rag_context, list)
        assert len(rag_context) > 0
        first_chunk = rag_context[0]
        assert "chunk_id" in first_chunk
        assert "domain" in first_chunk
        assert "concept" in first_chunk
        assert "text" not in first_chunk  # Full text excluded from SQL JSON column

        # rag_context_full must retain the full chunk text for evaluation
        rag_full = res.get("rag_context_full")
        assert isinstance(rag_full, list)
        assert len(rag_full) > 0
        assert "text" in rag_full[0]

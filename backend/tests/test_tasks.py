import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add root dir to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from scripts.generate_question import retrieve_rag_context
from backend.app.services.evaluation_service import evaluate_answer
import backend.app.services.interview_service as interview_service

def test_retrieve_rag_context_exclusion():
    # Setup mock embedding and collection
    mock_embedding = MagicMock()
    mock_embedding.encode.return_value = [0.1, 0.2, 0.3]
    
    mock_collection = MagicMock()
    # Assume the collect returns 5 items
    mock_collection.query.return_value = {
        "ids": [["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"]],
        "metadatas": [[{"domain": "foo", "concept": "bar"}] * 5],
        "documents": [["doc1", "doc2", "doc3", "doc4", "doc5"]],
        "distances": [[0.1, 0.2, 0.3, 0.4, 0.5]]
    }
    
    # Exclude chunk1 and chunk2
    exclude = {"chunk1", "chunk2"}
    chunks, query = retrieve_rag_context("test_skill", mock_embedding, mock_collection, exclude_chunk_ids=exclude)
    
    assert len(chunks) == 3
    assert chunks[0]["chunk_id"] == "chunk3"
    assert chunks[1]["chunk_id"] == "chunk4"
    assert chunks[2]["chunk_id"] == "chunk5"

@patch('backend.app.services.evaluation_service._llm_evaluate')
def test_low_word_count_score_cap(mock_llm_eval):
    # Mock LLM returning 90 for technical and completeness
    mock_llm_eval.return_value = {
        "technical_score": 90,
        "completeness_score": 90,
        "relevance_score": 90,
        "concept_coverage_score": 90,
        "feedback": "Great job!",
        "strengths": [],
        "weaknesses": [],
        "expected_concepts": [],
        "found_concepts": [],
    }
    
    short_answer = "This is a very short answer. Just a few words."
    eval_res = evaluate_answer(
        question_text="Tell me everything about python?",
        answer_text=short_answer,
        difficulty="hard",
        bloom_level_name="analyze",
        rag_context=None,
        expected_concepts=["python"],
        ideal_answer_summary="Good python",
        groq_client=MagicMock(),
        groq_model="fake-model",
        embedding_model=None
    )
    
    # Should be capped at 40
    assert eval_res.technical_score == 40, f"Expected 40, got {eval_res.technical_score}"
    assert eval_res.completeness_score == 40
    assert "capped" in eval_res.feedback.lower()
    
    
from backend.app.services.adaptive_engine import AdaptiveState, AdaptiveDecision
from backend.app.models.question import InterviewQuestion

@patch('backend.app.services.interview_service.generate_single_question')
@patch('backend.app.services.interview_service.SessionLocal')
@patch('backend.app.services.interview_service.get_embedding_model')
def test_dedup_similarity_check(mock_get_emb, mock_db, mock_gsq):
    # Setup db mock
    mock_session = MagicMock()
    mock_db.return_value = mock_session
    
    mock_interview_session = MagicMock()
    mock_interview_session.id = 1
    mock_interview_session.status = "in_progress"
    
    state = AdaptiveState(selected_skills=["python"], initial_difficulty="medium", question_count=3)
    state.current_skill = "python"
    # Pre-add a previous question
    state.previous_questions = ["Explain closures in Javascript."]
    mock_interview_session.adaptive_state = state.serialize()
    mock_session.query().filter().first.return_value = mock_interview_session
    
    # Setup embedding mock to return identical embeddings (similarity > 0.90)
    mock_emb = MagicMock()
    mock_get_emb.return_value = mock_emb
    import numpy as np
    mock_emb.encode.return_value = np.array([1, 0, 0])  # dot product will be 1.0 > 0.90
    
    # First call: returns colliding question. Second call: returns non-colliding question
    mock_gsq.side_effect = [
        {"skill": "python", "question_type": "conceptual", "difficulty": "medium", 
         "question_text": "Explain closures in JS?", "rag_context": [], "project_context": None, "bloom_level": "analyze", "bloom_level_number": 4, "expected_concepts": [], "ideal_answer_summary": ""},
        {"skill": "python", "question_type": "practical", "difficulty": "medium", 
         "question_text": "Write a python function?", "rag_context": [], "project_context": None, "bloom_level": "analyze", "bloom_level_number": 4, "expected_concepts": [], "ideal_answer_summary": ""}
    ]
    
    # Run
    interview_service.generate_next_question_bg(session_id=1)
    
    # Verify generate_single_question was called twice (due to collision)
    assert mock_gsq.call_count == 2
    # Verify second call used variant_index=1
    args, kwargs = mock_gsq.call_args_list[1]
    assert kwargs.get('variant_index') == 1

"""
SmartInterview — Answer Evaluation Service (Week 9)

Evaluates candidate text answers using:
    1. LLM-based evaluation (Groq) — technical correctness, completeness, relevance
    2. Semantic similarity (SentenceTransformer) — one signal, NOT proof of correctness
    3. Concept coverage — expected vs found concepts

Scoring Formula:
    overall = 0.30 * technical
            + 0.20 * completeness
            + 0.20 * relevance
            + 0.15 * semantic_similarity
            + 0.15 * concept_coverage

This formula is the project's defined scoring framework.
It is NOT claimed to be scientifically validated.

Semantic similarity measures semantic closeness between the candidate
response and the reference information. It does NOT by itself establish
technical correctness. Technical correctness primarily comes from the
LLM evaluation and concept coverage signals.

Voice/STT evaluation is NOT part of this service — deferred to Week 11.
"""

import json
import os
import time
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from app.config import PROMPTS_FILE

logger = logging.getLogger(__name__)



# ── Scoring Weights (documented) ─────────────────────────────

WEIGHT_TECHNICAL = 0.30
WEIGHT_COMPLETENESS = 0.20
WEIGHT_RELEVANCE = 0.20
WEIGHT_SEMANTIC_SIMILARITY = 0.15
WEIGHT_CONCEPT_COVERAGE = 0.15

# ── Evaluation Result ─────────────────────────────────────────

@dataclass
class EvaluationResult:
    """Structured evaluation result for one answer."""
    technical_score: int = 0
    completeness_score: int = 0
    relevance_score: int = 0
    semantic_similarity_score: int = 0
    concept_coverage_score: int = 0
    overall_score: int = 0
    feedback: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    concepts_expected: list[str] = field(default_factory=list)
    concepts_found: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "technical_score": self.technical_score,
            "completeness_score": self.completeness_score,
            "relevance_score": self.relevance_score,
            "semantic_similarity_score": self.semantic_similarity_score,
            "concept_coverage_score": self.concept_coverage_score,
            "overall_score": self.overall_score,
            "feedback": self.feedback,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "concepts_expected": self.concepts_expected,
            "concepts_found": self.concepts_found,
        }


# ── Load Evaluation Prompts ──────────────────────────────────

_eval_prompts = None

def _get_eval_prompts() -> dict:
    global _eval_prompts
    if _eval_prompts is None:
        eval_prompts_path = os.path.join(
            os.path.dirname(PROMPTS_FILE), "evaluation_prompts.json"
        )
        with open(eval_prompts_path, "r", encoding="utf-8") as f:
            _eval_prompts = json.load(f)
    return _eval_prompts


# ── Main Evaluation Function ─────────────────────────────────

def evaluate_answer(
    question_text: str,
    answer_text: str,
    difficulty: str,
    bloom_level_name: str,
    rag_context: Optional[list[dict]] = None,
    groq_client=None,
    groq_model: str = "",
    embedding_model=None,
) -> EvaluationResult:
    """
    Evaluate a candidate's text answer.

    Uses:
        1. LLM evaluation via Groq (technical, completeness, relevance, concepts)
        2. Semantic similarity via SentenceTransformer

    Args:
        question_text: The interview question
        answer_text: The candidate's answer
        difficulty: Question difficulty (easy/medium/hard)
        bloom_level_name: Bloom level name for context
        rag_context: RAG chunks used when generating the question
        groq_client: Initialized Groq client (from question_service singletons)
        groq_model: Groq model name
        embedding_model: SentenceTransformer model (from question_service singletons)

    Returns:
        EvaluationResult with all scores and feedback
    """
    result = EvaluationResult()

    # Handle empty/very short answers
    stripped = answer_text.strip() if answer_text else ""
    if len(stripped) < 5:
        result.feedback = "The answer is too short or empty to evaluate meaningfully."
        result.weaknesses = ["Answer is essentially empty or too brief."]
        result.overall_score = 0
        return result

    # Build reference context from RAG chunks
    reference_text = _build_reference_text(rag_context)

    # ── Step 1: LLM Evaluation ────────────────────────────────
    llm_result = _llm_evaluate(
        question_text=question_text,
        answer_text=stripped,
        difficulty=difficulty,
        bloom_level_name=bloom_level_name,
        reference_context=reference_text,
        groq_client=groq_client,
        groq_model=groq_model,
    )

    result.technical_score = llm_result.get("technical_score", 0)
    result.completeness_score = llm_result.get("completeness_score", 0)
    result.relevance_score = llm_result.get("relevance_score", 0)
    result.feedback = llm_result.get("feedback", "")
    result.strengths = llm_result.get("strengths", [])
    result.weaknesses = llm_result.get("weaknesses", [])
    result.concepts_expected = llm_result.get("expected_concepts", [])
    result.concepts_found = llm_result.get("found_concepts", [])

    # Concept coverage from LLM
    llm_concept_coverage = llm_result.get("concept_coverage_score", 0)

    # ── Step 2: Semantic Similarity ───────────────────────────
    if embedding_model is not None and reference_text:
        result.semantic_similarity_score = _compute_semantic_similarity(
            answer_text=stripped,
            reference_text=reference_text,
            question_text=question_text,
            embedding_model=embedding_model,
        )
    else:
        # Fallback if embedding model unavailable
        result.semantic_similarity_score = 0

    # ── Step 3: Concept Coverage ──────────────────────────────
    # Use LLM-extracted concept coverage, validated
    result.concept_coverage_score = llm_concept_coverage

    # If LLM provided expected/found concepts, verify coverage independently
    if result.concepts_expected and len(result.concepts_expected) > 0:
        found_count = len(result.concepts_found) if result.concepts_found else 0
        expected_count = len(result.concepts_expected)
        calculated_coverage = round(100 * found_count / expected_count)
        # Use average of LLM coverage and our calculation for robustness
        result.concept_coverage_score = _clamp(
            round((llm_concept_coverage + calculated_coverage) / 2)
        )

    # ── Step 4: Calculate Overall Score ───────────────────────
    result.overall_score = _calculate_overall(result)

    return result


# ── LLM Evaluation ────────────────────────────────────────────

def _llm_evaluate(
    question_text: str,
    answer_text: str,
    difficulty: str,
    bloom_level_name: str,
    reference_context: str,
    groq_client,
    groq_model: str,
) -> dict:
    """
    Call Groq to evaluate the answer. Returns parsed JSON dict.
    Never crashes — returns safe defaults on failure.
    """
    if groq_client is None or not groq_model:
        return _safe_defaults("LLM evaluation unavailable (no Groq client)")

    prompts = _get_eval_prompts()
    system_prompt = prompts["evaluation_system_prompt"]
    user_template = prompts["evaluation_user_template"]

    user_prompt = user_template.format(
        difficulty=difficulty,
        bloom_level=bloom_level_name,
        question_text=question_text,
        answer_text=answer_text,
        reference_context=reference_context if reference_context else "No reference context available.",
    )

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = groq_client.chat.completions.create(
                model=groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,  # lower temperature for more consistent evaluation
                max_tokens=1200,
                timeout=30.0,
            )

            text = response.choices[0].message.content
            if not text or not text.strip():
                return _safe_defaults("Empty LLM response")

            return _parse_evaluation_json(text.strip())

        except Exception as e:
            if attempt < max_retries:
                backoff = (0.5 * (2 ** attempt)) + 0.1
                time.sleep(backoff)
                continue
            logger.warning("[EvaluationService] LLM evaluation error after %d retries: %s", max_retries, e)
            return _safe_defaults(f"LLM evaluation failed: {str(e)[:100]}")



def _parse_evaluation_json(text: str) -> dict:
    """
    Parse and validate LLM evaluation JSON response.
    Handles malformed JSON gracefully with safe defaults.
    """
    # Try to extract JSON from the response (handle markdown code blocks)
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (```json and ```)
        json_lines = []
        inside = False
        for line in lines:
            if line.strip().startswith("```") and not inside:
                inside = True
                continue
            elif line.strip() == "```" and inside:
                break
            elif inside:
                json_lines.append(line)
        cleaned = "\n".join(json_lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                return _safe_defaults("Could not parse LLM JSON response")
        else:
            return _safe_defaults("No JSON found in LLM response")

    # Validate and clamp all score fields
    validated = {}
    for score_field in ["technical_score", "completeness_score", "relevance_score", "concept_coverage_score"]:
        val = data.get(score_field, 0)
        validated[score_field] = _clamp(_to_int(val))

    # String fields
    validated["feedback"] = str(data.get("feedback", ""))[:2000]

    # List fields
    validated["strengths"] = _validate_string_list(data.get("strengths", []))
    validated["weaknesses"] = _validate_string_list(data.get("weaknesses", []))
    validated["expected_concepts"] = _validate_string_list(data.get("expected_concepts", []))
    validated["found_concepts"] = _validate_string_list(data.get("found_concepts", []))

    return validated


def _safe_defaults(reason: str = "") -> dict:
    """Return safe default evaluation when LLM fails."""
    return {
        "technical_score": 0,
        "completeness_score": 0,
        "relevance_score": 0,
        "concept_coverage_score": 0,
        "feedback": f"Automated evaluation could not be completed. {reason}".strip(),
        "strengths": [],
        "weaknesses": [],
        "expected_concepts": [],
        "found_concepts": [],
    }


# ── Semantic Similarity ──────────────────────────────────────

def _compute_semantic_similarity(
    answer_text: str,
    reference_text: str,
    question_text: str,
    embedding_model,
) -> int:
    """
    Compute semantic similarity between the candidate answer and reference context.

    This is ONE evaluation signal alongside LLM scoring.
    Semantic similarity measures semantic closeness — it does NOT
    by itself establish technical correctness.

    Uses cosine similarity between embeddings.
    """
    try:
        # Build reference: question + reference knowledge
        # This represents what a good answer should be semantically close to
        reference = f"{question_text}\n{reference_text[:1500]}"

        ref_embedding = embedding_model.encode(reference, convert_to_numpy=True)
        ans_embedding = embedding_model.encode(answer_text, convert_to_numpy=True)

        # Cosine similarity
        dot = np.dot(ref_embedding, ans_embedding)
        norm_ref = np.linalg.norm(ref_embedding)
        norm_ans = np.linalg.norm(ans_embedding)

        if norm_ref == 0 or norm_ans == 0:
            return 0

        cosine_sim = dot / (norm_ref * norm_ans)

        # Scale cosine similarity [0, 1] → [0, 100]
        # Cosine similarity for text is typically 0.1-0.8 range
        # We use a nonlinear mapping: sim < 0.2 → low, sim > 0.7 → high
        score = max(0.0, min(1.0, (cosine_sim - 0.1) / 0.6)) * 100
        return _clamp(round(score))

    except Exception as e:
        print(f"[EvaluationService] Semantic similarity error: {e}")
        return 0


# ── Helpers ───────────────────────────────────────────────────

def _build_reference_text(rag_context: Optional[list[dict]]) -> str:
    """Build reference text from RAG chunks for evaluation context."""
    if not rag_context:
        return ""
    parts = []
    for chunk in rag_context[:3]:
        if isinstance(chunk, dict):
            text = chunk.get("text", "")
            if text:
                parts.append(text[:500])
    return "\n---\n".join(parts)


def _calculate_overall(result: EvaluationResult) -> int:
    """
    Calculate weighted overall score.

    Formula:
        overall = 0.30 * technical
                + 0.20 * completeness
                + 0.20 * relevance
                + 0.15 * semantic_similarity
                + 0.15 * concept_coverage
    """
    raw = (
        WEIGHT_TECHNICAL * result.technical_score
        + WEIGHT_COMPLETENESS * result.completeness_score
        + WEIGHT_RELEVANCE * result.relevance_score
        + WEIGHT_SEMANTIC_SIMILARITY * result.semantic_similarity_score
        + WEIGHT_CONCEPT_COVERAGE * result.concept_coverage_score
    )
    return _clamp(round(raw))


def _clamp(score: int, lo: int = 0, hi: int = 100) -> int:
    """Clamp score to [0, 100]."""
    return max(lo, min(hi, score))


def _to_int(val) -> int:
    """Safely convert a value to int."""
    if isinstance(val, (int, float)):
        return int(val)
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return 0


def _validate_string_list(val, max_items: int = 10) -> list[str]:
    """Validate and clean a list of strings from LLM output."""
    if not isinstance(val, list):
        return []
    result = []
    for item in val[:max_items]:
        if isinstance(item, str) and item.strip():
            result.append(item.strip()[:500])
    return result

"""
SmartInterview — Adaptive Learning Engine (Week 8)

Deterministic decision engine that controls interview progression.
Decides: next skill, Bloom level, difficulty, and question type
based on per-skill performance tracking.

Architecture:
    - LearnerProfile: tracks per-skill performance (attempts, scores, bloom, difficulty)
    - AdaptiveState: serializable session state
    - decide_next(): deterministic rules for progression
    - select_skill(): weakness-biased coverage
    - select_question_type(): Bloom-guided type selection

Adaptive Rules (deterministic):
    Score >= 80  → advance Bloom level (if at max, advance difficulty)
    Score 50–79  → maintain current level
    Score < 50   → regress Bloom level (if at min, lower difficulty if possible)

These rules are implemented in Python — the LLM does NOT decide progression.
"""

from __future__ import annotations
import json
import copy
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.services.bloom import (
    BloomLevel, get_bloom_level, next_level, prev_level,
    REMEMBER, MIN_ORDER, MAX_ORDER, clamp_bloom_order,
    ALL_LEVELS,
)


# ── Constants ─────────────────────────────────────────────────

DIFFICULTIES = ["easy", "medium", "hard"]
DIFFICULTY_ORDER = {d: i for i, d in enumerate(DIFFICULTIES)}

# Adaptive score thresholds
ADVANCE_THRESHOLD = 80   # Score >= 80 → progress
MAINTAIN_LOWER = 50      # Score 50-79 → maintain
# Score < 50 → regress/reinforce

# Bloom-to-question-type guidance (not rigid — provides suitable types)
# Each Bloom level maps to a list of suitable question types, ordered by preference
BLOOM_QUESTION_TYPES = {
    "remember":    ["conceptual", "practical", "technical_reasoning"],
    "understand":  ["conceptual", "technical_reasoning", "practical"],
    "apply":       ["practical", "conceptual", "scenario"],
    "analyze":     ["technical_reasoning", "practical", "scenario"],
    "evaluate":    ["scenario", "technical_reasoning", "project"],
    "create":      ["project", "scenario", "practical"],
}


# ── Skill Performance Tracking ────────────────────────────────

@dataclass
class SkillPerformance:
    """Tracks performance for a single skill across an interview."""
    skill: str
    attempts: int = 0
    total_score: float = 0.0
    current_bloom_order: int = 1          # starts at Remember
    current_difficulty: str = "medium"    # will be overridden by session config
    scores: list[float] = field(default_factory=list)

    @property
    def average_score(self) -> float:
        if self.attempts == 0:
            return 0.0
        return self.total_score / self.attempts

    def record_score(self, score: float):
        """Record a new evaluation score for this skill."""
        self.attempts += 1
        clamped = max(0.0, min(100.0, score))
        self.total_score += clamped
        self.scores.append(clamped)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SkillPerformance:
        return cls(**data)


# ── Adaptive State ────────────────────────────────────────────

@dataclass
class AdaptiveState:
    """
    Serializable state of the adaptive engine for one interview session.
    Stored as JSON in interview_sessions.adaptive_state.
    """
    selected_skills: list[str]
    initial_difficulty: str
    question_count: int
    questions_generated: int = 0
    questions_answered: int = 0
    current_skill: str = ""
    current_bloom_id: str = "remember"
    current_difficulty: str = "medium"
    current_question_type: str = "conceptual"
    skill_performances: dict[str, dict] = field(default_factory=dict)
    previous_questions: list[str] = field(default_factory=list)
    skill_rotation_index: int = 0

    @property
    def questions_remaining(self) -> int:
        return max(0, self.question_count - self.questions_generated)

    @property
    def is_complete(self) -> bool:
        return self.questions_answered >= self.question_count

    def get_skill_performance(self, skill: str) -> SkillPerformance:
        """Get or create a SkillPerformance for the given skill."""
        if skill not in self.skill_performances:
            self.skill_performances[skill] = SkillPerformance(
                skill=skill,
                current_difficulty=self.initial_difficulty,
            ).to_dict()
        data = self.skill_performances[skill]
        if isinstance(data, dict):
            return SkillPerformance.from_dict(data)
        return data

    def update_skill_performance(self, perf: SkillPerformance):
        """Persist a SkillPerformance back into the state."""
        self.skill_performances[perf.skill] = perf.to_dict()

    def get_weak_topics(self, threshold: float = 60.0) -> list[str]:
        """
        Return list of skills where the candidate has scored below the threshold,
        signaling that foundation/prerequisite remediation should be triggered.
        """
        weak = []
        for skill_name, data in self.skill_performances.items():
            perf = SkillPerformance.from_dict(data) if isinstance(data, dict) else data
            if perf.attempts > 0 and perf.average_score < threshold:
                weak.append(skill_name)
        return weak

    def serialize(self) -> dict:
        """Serialize state to JSON-safe dict for MySQL storage."""
        return {
            "selected_skills": self.selected_skills,
            "initial_difficulty": self.initial_difficulty,
            "question_count": self.question_count,
            "questions_generated": self.questions_generated,
            "questions_answered": self.questions_answered,
            "current_skill": self.current_skill,
            "current_bloom_id": self.current_bloom_id,
            "current_difficulty": self.current_difficulty,
            "current_question_type": self.current_question_type,
            "skill_performances": self.skill_performances,
            "previous_questions": self.previous_questions,
            "skill_rotation_index": self.skill_rotation_index,
        }

    @classmethod
    def deserialize(cls, data: dict) -> AdaptiveState:
        """Reconstruct state from stored JSON dict."""
        return cls(**data)


# ── Adaptive Decision ────────────────────────────────────────

@dataclass
class AdaptiveDecision:
    """Result of the adaptive engine's decision for the next question."""
    skill: str
    bloom_level: BloomLevel
    difficulty: str
    question_type: str


# ── Initialization ────────────────────────────────────────────

def initialize_state(
    selected_skills: list[str],
    difficulty: str,
    question_type: str,
    question_count: int,
) -> AdaptiveState:
    """
    Create initial adaptive state from interview configuration.
    The first question always starts at Remember level.
    """
    difficulty = difficulty if difficulty in DIFFICULTIES else "medium"

    state = AdaptiveState(
        selected_skills=selected_skills,
        initial_difficulty=difficulty,
        question_count=question_count,
        current_difficulty=difficulty,
        current_bloom_id="remember",
        current_question_type=question_type if question_type != "mixed" else "conceptual",
    )

    # Initialize performance tracking for each skill
    for skill in selected_skills:
        perf = SkillPerformance(skill=skill, current_difficulty=difficulty)
        state.update_skill_performance(perf)

    # Select first skill
    state.current_skill = selected_skills[0] if selected_skills else ""

    return state


# ── Core Adaptive Logic ──────────────────────────────────────

def decide_next(state: AdaptiveState, overall_score: float) -> AdaptiveDecision:
    """
    Deterministic adaptive decision based on the latest evaluation score.

    Rules:
        Score >= 80  → advance Bloom level (if max Bloom, advance difficulty)
        Score 50–79  → maintain current level
        Score < 50   → regress Bloom level (if min Bloom, reduce difficulty if possible)

    Returns an AdaptiveDecision with the next skill, bloom, difficulty, and question type.
    """
    # Get current skill performance
    current_skill = state.current_skill
    perf = state.get_skill_performance(current_skill)

    # Record the score
    perf.record_score(overall_score)

    current_bloom = get_bloom_level(state.current_bloom_id)
    current_difficulty = state.current_difficulty

    # ── Apply deterministic rules ──
    new_bloom = current_bloom
    new_difficulty = current_difficulty

    if overall_score >= ADVANCE_THRESHOLD:
        # Try to advance Bloom level
        higher = next_level(current_bloom)
        if higher is not None:
            new_bloom = higher
        else:
            # Already at Create — advance difficulty instead
            new_difficulty = _next_difficulty(current_difficulty)

    elif overall_score < MAINTAIN_LOWER:
        # Try to regress Bloom level
        lower = prev_level(current_bloom)
        if lower is not None:
            new_bloom = lower
        else:
            # Already at Remember — lower difficulty if possible
            new_difficulty = _prev_difficulty(current_difficulty)
    # else: 50-79 → maintain current level (no changes)

    # Update skill performance state
    perf.current_bloom_order = new_bloom.order
    perf.current_difficulty = new_difficulty
    state.update_skill_performance(perf)

    # Select next skill (may change from current)
    next_skill = select_skill(state)

    # Get the next skill's bloom level (may differ from current skill's progression)
    next_perf = state.get_skill_performance(next_skill)
    # If switching skills, use that skill's current bloom level
    if next_skill != current_skill:
        skill_bloom = get_bloom_level(clamp_bloom_order(next_perf.current_bloom_order))
        skill_difficulty = next_perf.current_difficulty
    else:
        skill_bloom = new_bloom
        skill_difficulty = new_difficulty

    # Select question type based on Bloom level
    question_type = select_question_type(skill_bloom)

    # Update state
    state.current_skill = next_skill
    state.current_bloom_id = skill_bloom.id
    state.current_difficulty = skill_difficulty
    state.current_question_type = question_type

    return AdaptiveDecision(
        skill=next_skill,
        bloom_level=skill_bloom,
        difficulty=skill_difficulty,
        question_type=question_type,
    )


def get_initial_decision(state: AdaptiveState) -> AdaptiveDecision:
    """Get the decision for the very first question (no previous evaluation)."""
    bloom = get_bloom_level(state.current_bloom_id)
    question_type = select_question_type(bloom)
    state.current_question_type = question_type

    return AdaptiveDecision(
        skill=state.current_skill,
        bloom_level=bloom,
        difficulty=state.current_difficulty,
        question_type=question_type,
    )


# ── Skill Selection ───────────────────────────────────────────

def select_skill(state: AdaptiveState) -> str:
    """
    Select the next skill using weakness-biased round-robin.

    Strategy:
        1. Identify skills that have been attempted least
        2. Among equally-attempted skills, prefer the weakest (lowest avg score)
        3. Advance the rotation index for coverage

    This ensures:
        - All selected skills get coverage
        - Weaker skills get more attention
        - No skill is asked repeatedly without justification
    """
    skills = state.selected_skills
    if not skills:
        return ""
    if len(skills) == 1:
        return skills[0]

    # Build performance data
    perf_data = []
    for skill in skills:
        perf = state.get_skill_performance(skill)
        perf_data.append({
            "skill": skill,
            "attempts": perf.attempts,
            "avg_score": perf.average_score,
        })

    # Find minimum attempts
    min_attempts = min(p["attempts"] for p in perf_data)

    # Filter to least-attempted skills
    candidates = [p for p in perf_data if p["attempts"] == min_attempts]

    if len(candidates) == 1:
        return candidates[0]["skill"]

    # Among equally-attempted, pick weakest (lowest average score)
    candidates.sort(key=lambda p: p["avg_score"])
    return candidates[0]["skill"]


# ── Question Type Selection ───────────────────────────────────

def select_question_type(bloom: BloomLevel) -> str:
    """
    Select a suitable question type based on the current Bloom level.

    This is NOT a rigid 1:1 mapping. Each Bloom level has several suitable
    question types, ordered by preference. The first (most suitable) type
    is selected.

    Bloom levels represent cognitive complexity, not a mandatory question-type.
    The selected type guides the LLM in question formulation.
    """
    types = BLOOM_QUESTION_TYPES.get(bloom.id, ["conceptual"])
    return types[0]


# ── Difficulty Helpers ────────────────────────────────────────

def _next_difficulty(current: str) -> str:
    """Move to the next higher difficulty, or stay at 'hard'."""
    idx = DIFFICULTY_ORDER.get(current, 1)
    next_idx = min(idx + 1, len(DIFFICULTIES) - 1)
    return DIFFICULTIES[next_idx]


def _prev_difficulty(current: str) -> str:
    """Move to the next lower difficulty, or stay at 'easy'."""
    idx = DIFFICULTY_ORDER.get(current, 1)
    prev_idx = max(idx - 1, 0)
    return DIFFICULTIES[prev_idx]


# ── Results Generation ────────────────────────────────────────

def generate_recommendations(state: AdaptiveState) -> list[dict]:
    """
    Generate personalized recommendations from actual performance data.
    Returns a list of recommendation dicts with skill, message, and priority.
    """
    recommendations = []

    # Gather per-skill performance
    skill_avgs = []
    for skill in state.selected_skills:
        perf = state.get_skill_performance(skill)
        if perf.attempts > 0:
            skill_avgs.append({
                "skill": skill,
                "avg_score": perf.average_score,
                "attempts": perf.attempts,
                "final_bloom": perf.current_bloom_order,
            })

    if not skill_avgs:
        return recommendations

    # Sort by average score (weakest first)
    skill_avgs.sort(key=lambda x: x["avg_score"])

    for item in skill_avgs:
        avg = item["avg_score"]
        skill = item["skill"]
        bloom_order = item["final_bloom"]

        if avg < 40:
            recommendations.append({
                "skill": skill,
                "priority": "high",
                "message": (
                    f"Your {skill} performance needs significant improvement "
                    f"(average: {avg:.0f}%). Focus on foundational concepts and "
                    f"practice basic problems before attempting advanced topics."
                ),
            })
        elif avg < 60:
            recommendations.append({
                "skill": skill,
                "priority": "medium",
                "message": (
                    f"Your {skill} understanding shows gaps (average: {avg:.0f}%). "
                    f"Review core concepts and practice applying them in problem-solving scenarios."
                ),
            })
        elif avg < 80:
            recommendations.append({
                "skill": skill,
                "priority": "low",
                "message": (
                    f"Your {skill} skills are developing well (average: {avg:.0f}%). "
                    f"Challenge yourself with more complex analysis and design questions."
                ),
            })
        else:
            bloom_name = get_bloom_level(clamp_bloom_order(bloom_order)).name
            recommendations.append({
                "skill": skill,
                "priority": "none",
                "message": (
                    f"Strong {skill} performance (average: {avg:.0f}%, "
                    f"reached {bloom_name} level). Continue with advanced topics."
                ),
            })

    # Add Bloom-specific recommendations
    overall_bloom = max((state.get_skill_performance(s).current_bloom_order for s in state.selected_skills), default=1)
    if overall_bloom <= 2:
        recommendations.append({
            "skill": "General",
            "priority": "medium",
            "message": (
                "You're primarily demonstrating recall and understanding. "
                "Practice applying concepts to real problems to advance to higher cognitive levels."
            ),
        })

    return recommendations


def calculate_session_summary(state: AdaptiveState) -> dict:
    """Calculate final session summary from adaptive state."""
    skill_results = {}
    total_score = 0.0
    total_attempts = 0

    for skill in state.selected_skills:
        perf = state.get_skill_performance(skill)
        if perf.attempts > 0:
            bloom = get_bloom_level(clamp_bloom_order(perf.current_bloom_order))
            skill_results[skill] = {
                "attempts": perf.attempts,
                "average_score": round(perf.average_score, 1),
                "scores": perf.scores,
                "final_bloom_level": bloom.id,
                "final_bloom_name": bloom.name,
                "final_bloom_order": bloom.order,
                "final_difficulty": perf.current_difficulty,
            }
            total_score += perf.total_score
            total_attempts += perf.attempts

    overall_avg = round(total_score / total_attempts, 1) if total_attempts > 0 else 0.0

    return {
        "overall_average_score": overall_avg,
        "total_questions_answered": total_attempts,
        "skill_results": skill_results,
        "recommendations": generate_recommendations(state),
    }

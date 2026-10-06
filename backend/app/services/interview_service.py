"""
SmartInterview — Interview Service (Weeks 7-9)
Orchestrates interview session creation, adaptive question generation,
answer evaluation, and result computation.

Week 7 (legacy): Generates all questions upfront
Week 8 (adaptive): One-question-at-a-time with Bloom progression
Week 9 (evaluation): Answer evaluation feeds adaptive engine
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func

from app.models.interview import InterviewSession
from app.models.question import InterviewQuestion, Answer, AnswerEvaluation
from app.models.resume import Resume
from app.services.question_service import (
    generate_questions,
    generate_single_question,
    get_embedding_model,
    get_groq_client,
    get_groq_model_name,
)
from app.services.adaptive_engine import (
    AdaptiveState,
    AdaptiveDecision,
    initialize_state,
    decide_next,
    get_initial_decision,
    calculate_session_summary,
    generate_recommendations,
)
from app.services.evaluation_service import evaluate_answer, EvaluationResult
from app.models.job_description import JobDescription
from app.services.jd_service import map_skills
from app.services.syllabus_engine import (
    SyllabusState,
    initialize_syllabus_state,
    calculate_syllabus_summary,
)
from app.services.syllabus_rag_service import delete_temporary_rag, merge_temporary_to_permanent_kb
from app.services.question_service import generate_syllabus_question

MAX_ADAPTIVE_QUESTIONS = 30  # Safety limit for infinite loops


# ── Adaptive Session Creation ─────────────────────────────

def create_interview_session(
    db: Session,
    user_id: int,
    resume_id: int | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    question_count: int | None = None,
    selected_skills: list[str] | None = None,
    mode: str = "normal",
    syllabus_id: str | None = None,
    selected_topics: list[str] | None = None,
) -> dict:
    """
    Create a new ADAPTIVE interview session and generate the FIRST question only.
    Supports both Normal Mode (Resume + JD) and Syllabus Mode (Coursework RAG).
    """

    # ── Syllabus Mode Branch ──────────────────────────────────────────────────
    if mode == "syllabus":
        if not syllabus_id:
            raise ValueError("syllabus_id is required for Syllabus Mode")
        if not selected_topics:
            raise ValueError("At least one topic must be selected for Syllabus Mode")

        # Resolve resume_id (optional for syllabus mode)
        if not resume_id or resume_id <= 0:
            latest_resume = (
                db.query(Resume)
                .filter(Resume.user_id == user_id)
                .order_by(Resume.uploaded_at.desc())
                .first()
            )
            resume_id = latest_resume.id if latest_resume else None

        use_skills = selected_topics
        difficulty = difficulty or "medium"
        question_type = question_type or "mixed"
        internal_question_count = question_count if question_count else MAX_ADAPTIVE_QUESTIONS

        # Initialize shared adaptive state for Bloom & difficulty progression
        adaptive_state = initialize_state(
            selected_skills=use_skills,
            difficulty=difficulty,
            question_type=question_type,
            question_count=internal_question_count,
        )
        decision = get_initial_decision(adaptive_state)

        # Initialize syllabus state for adaptive topic progression
        syllabus_state = initialize_syllabus_state(selected_topics=selected_topics)

        session = InterviewSession(
            user_id=user_id,
            resume_id=resume_id,
            difficulty=difficulty,
            question_type=question_type,
            question_count=question_count or 0,
            selected_skills=use_skills,
            status="in_progress",
            is_adaptive=True,
            adaptive_state=adaptive_state.serialize(),
            current_bloom_level=decision.bloom_level.id,
            mode="syllabus",
            syllabus_id=syllabus_id,
            syllabus_state=syllabus_state.serialize(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Generate first question strictly from syllabus RAG
        q_data = generate_syllabus_question(
            topic=syllabus_state.current_topic,
            difficulty=decision.difficulty,
            question_type=decision.question_type,
            syllabus_id=syllabus_id,
            bloom_level=decision.bloom_level,
            previous_questions=[],
        )

        question = InterviewQuestion(
            session_id=session.id,
            question_number=1,
            skill=q_data["skill"],
            question_type=q_data["question_type"],
            difficulty=q_data["difficulty"],
            question_text=q_data["question_text"],
            rag_context=q_data.get("rag_context"),
            project_context=None,
            bloom_level=q_data.get("bloom_level"),
            bloom_level_number=q_data.get("bloom_level_number"),
        )
        db.add(question)

        adaptive_state.questions_generated = 1
        if q_data["question_text"] and q_data["question_text"] != "[GENERATION FAILED]":
            adaptive_state.previous_questions.append(q_data["question_text"])
        session.adaptive_state = adaptive_state.serialize()

        db.commit()
        db.refresh(session)
        db.refresh(question)

        return {
            "session": session,
            "current_question": question,
            "rag_context_full": q_data.get("rag_context_full"),
        }

    # ── Normal Mode Branch (Resume + Job Description) ─────────────────────────
    resume = db.query(Resume).filter(
        Resume.id == resume_id, Resume.user_id == user_id
    ).first()
    if not resume:
        raise ValueError("Resume not found or does not belong to this user")

    skills = resume.skills or []
    projects = resume.projects or []

    if not skills:
        raise ValueError("No skills found in resume. Please upload a resume with technical skills.")

    # ── Require Job Description ───────────────────────────────────────────────
    jd = (
        db.query(JobDescription)
        .filter(JobDescription.user_id == user_id)
        .order_by(JobDescription.uploaded_at.desc())
        .first()
    )
    if not jd:
        raise ValueError(
            "Please upload both your resume and job description to continue. "
            "The job description determines which skills to focus on."
        )

    # ── Map Resume + JD skills (approved priority order) ─────────────────────
    # Priority 1 (Group A): JD skills present in Resume  → verify claimed experience
    # Priority 2 (Group B): JD skills not in Resume      → test role requirements/gaps
    # Resume-only skills: excluded from default interview plan
    jd_skills = jd.skills or []
    if not jd_skills:
        # JD uploaded but extraction yielded nothing — fall back to resume skills
        mapped_interview_skills = skills
    else:
        mapping = map_skills(resume_skills=skills, jd_skills=jd_skills)
        mapped_interview_skills = mapping["interview_skills"]
        if not mapped_interview_skills:
            # No overlap at all — fall back to all JD skills then resume skills
            mapped_interview_skills = jd_skills or skills

    # Validate selected_skills against the mapped interview skill set and preserve priority order
    if selected_skills:
        valid_pool = {s.lower().strip() for s in selected_skills}
        ordered_selected = [s for s in mapped_interview_skills if s.lower().strip() in valid_pool]
        use_skills = ordered_selected if ordered_selected else mapped_interview_skills
    else:
        use_skills = mapped_interview_skills

    # Use defaults for open-ended interviews
    difficulty = difficulty or "medium"
    question_type = question_type or "mixed"
    # Use MAX_ADAPTIVE_QUESTIONS as internal state bound, but user doesn't see it
    internal_question_count = question_count if question_count else MAX_ADAPTIVE_QUESTIONS

    # Initialize adaptive state
    adaptive_state = initialize_state(
        selected_skills=use_skills,
        difficulty=difficulty,
        question_type=question_type,
        question_count=internal_question_count,
    )

    # Get initial adaptive decision (first question parameters)
    decision = get_initial_decision(adaptive_state)

    # Create session in DB
    session = InterviewSession(
        user_id=user_id,
        resume_id=resume_id,
        difficulty=difficulty,
        question_type=question_type,
        question_count=question_count or 0,  # 0 indicates open-ended
        selected_skills=use_skills,
        status="in_progress",
        is_adaptive=True,
        adaptive_state=adaptive_state.serialize(),
        current_bloom_level=decision.bloom_level.id,
        job_description_id=jd.id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Generate ONLY the first question
    q_data = generate_single_question(
        skill=decision.skill,
        difficulty=decision.difficulty,
        question_type=decision.question_type,
        bloom_level=decision.bloom_level,
        projects=projects,
        previous_questions=[],
    )

    # Store in DB
    question = InterviewQuestion(
        session_id=session.id,
        question_number=1,
        skill=q_data["skill"],
        question_type=q_data["question_type"],
        difficulty=q_data["difficulty"],
        question_text=q_data["question_text"],
        rag_context=q_data.get("rag_context"),
        project_context=q_data.get("project_context"),
        bloom_level=q_data.get("bloom_level"),
        bloom_level_number=q_data.get("bloom_level_number"),
    )
    db.add(question)

    # Update adaptive state
    adaptive_state.questions_generated = 1
    if q_data["question_text"] and q_data["question_text"] != "[GENERATION FAILED]":
        adaptive_state.previous_questions.append(q_data["question_text"])
    session.adaptive_state = adaptive_state.serialize()

    db.commit()
    db.refresh(session)
    db.refresh(question)

    return {
        "session": session,
        "current_question": question,
        "rag_context_full": q_data.get("rag_context_full"),  # kept in memory for evaluation
    }


# ── Submit Answer + Evaluate + Generate Next ──────────────

def submit_and_evaluate(
    db: Session,
    user_id: int,
    session_id: int,
    question_id: int,
    answer_text: str,
) -> dict:
    """
    Submit answer → evaluate → update adaptive state → generate next question.

    This is the core adaptive loop:
        1. Validate session/question ownership
        2. Store the answer
        3. Evaluate the answer (LLM + semantic similarity)
        4. Store the evaluation
        5. Update adaptive state based on evaluation score
        6. Generate next question if interview continues
        7. Return evaluation + next question (or completion signal)

    Args:
        db: Database session
        user_id: Authenticated user ID
        session_id: Interview session ID
        question_id: Database ID of the question being answered
        answer_text: Candidate's text answer

    Returns:
        Dict with evaluation, next_question (if any), and completion status
    """

    # Validate session ownership
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == user_id,
    ).first()
    if not session:
        raise ValueError("Interview session not found")

    if session.status == "completed":
        raise ValueError("This interview has already been completed")

    # Find the question
    question = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == question_id,
        InterviewQuestion.session_id == session_id,
    ).first()
    if not question:
        raise ValueError(f"Question not found in this session")

    # Check for duplicate answer
    existing_answer = db.query(Answer).filter(
        Answer.question_id == question.id
    ).first()
    if existing_answer and existing_answer.answer_text:
        raise ValueError("This question has already been answered")

    # ── Step 1: Store the answer ──────────────────────────
    answer = Answer(
        question_id=question.id,
        session_id=session_id,
        user_id=user_id,
        answer_text=answer_text,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)

    # ── Step 2: Evaluate the answer ───────────────────────
    # Retrieve RAG context for evaluation (re-fetch from question's stored context)
    rag_context_for_eval = question.rag_context  # stored as metadata only
    # We need full text for evaluation — re-retrieve from ChromaDB if possible
    rag_full = _get_rag_context_for_eval(question, session)

    eval_result = evaluate_answer(
        question_text=question.question_text,
        answer_text=answer_text,
        difficulty=question.difficulty,
        bloom_level_name=question.bloom_level or "remember",
        rag_context=rag_full,
        groq_client=get_groq_client(),
        groq_model=get_groq_model_name(),
        embedding_model=get_embedding_model(),
    )

    # ── Step 3: Store the evaluation ──────────────────────
    evaluation = AnswerEvaluation(
        answer_id=answer.id,
        question_id=question.id,
        technical_score=eval_result.technical_score,
        completeness_score=eval_result.completeness_score,
        relevance_score=eval_result.relevance_score,
        semantic_similarity_score=eval_result.semantic_similarity_score,
        concept_coverage_score=eval_result.concept_coverage_score,
        overall_score=eval_result.overall_score,
        feedback=eval_result.feedback,
        strengths=eval_result.strengths,
        weaknesses=eval_result.weaknesses,
        concepts_expected=eval_result.concepts_expected,
        concepts_found=eval_result.concepts_found,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    # ── Step 4: Update adaptive state ─────────────────────
    state = AdaptiveState.deserialize(session.adaptive_state)
    state.questions_answered += 1

    # Shared Adaptive Decision (Bloom + difficulty update)
    decision = decide_next(state, eval_result.overall_score)

    # ── Strict Evidence-Based Auto-Stop ───────────────────
    # Auto-stop only triggers when ALL of the following are met:
    # 1. Minimum 5 questions answered
    # 2. Current difficulty has reached "easy"
    # 3. Candidate has 3 consecutive fails (< 40%) at easy level
    # 4. Clear evidence that candidate cannot handle fundamental level
    is_auto_stop = False
    if state.questions_answered >= 5 and decision.difficulty == "easy":
        recent_evals = (
            db.query(AnswerEvaluation.overall_score)
            .join(Answer, AnswerEvaluation.answer_id == Answer.id)
            .filter(Answer.session_id == session.id)
            .order_by(Answer.id.desc())
            .limit(3)
            .all()
        )
        if len(recent_evals) == 3 and all(ev[0] < 40.0 for ev in recent_evals):
            is_auto_stop = True

    is_complete = is_auto_stop or (state.questions_answered >= MAX_ADAPTIVE_QUESTIONS)

    next_question_data = None

    if not is_complete:
        if session.mode == "syllabus":
            # Adaptive topic selection with syllabus coverage constraints
            s_state = SyllabusState.deserialize(session.syllabus_state)
            s_state.record_score(question.skill, eval_result.overall_score)
            next_topic = s_state.select_next_topic()
            session.syllabus_state = s_state.serialize()

            q_data = generate_syllabus_question(
                topic=next_topic,
                difficulty=decision.difficulty,
                question_type=decision.question_type,
                syllabus_id=session.syllabus_id,
                bloom_level=decision.bloom_level,
                previous_questions=state.previous_questions,
                previous_topic=question.skill,
            )
        else:
            # ── Step 6: Generate next question for Normal Mode ──
            resume = db.query(Resume).filter(Resume.id == session.resume_id).first()
            projects = resume.projects if resume else []

            q_data = generate_single_question(
                skill=decision.skill,
                difficulty=decision.difficulty,
                question_type=decision.question_type,
                bloom_level=decision.bloom_level,
                projects=projects,
                previous_questions=state.previous_questions,
                previous_skill=question.skill,
                weak_topics=state.get_weak_topics(),
            )

        next_q_number = state.questions_generated + 1
        state.questions_generated = next_q_number

        if q_data["question_text"] and q_data["question_text"] != "[GENERATION FAILED]":
            state.previous_questions.append(q_data["question_text"])

        # Store next question
        next_question = InterviewQuestion(
            session_id=session.id,
            question_number=next_q_number,
            skill=q_data["skill"],
            question_type=q_data["question_type"],
            difficulty=q_data["difficulty"],
            question_text=q_data["question_text"],
            rag_context=q_data.get("rag_context"),
            project_context=q_data.get("project_context"),
            bloom_level=q_data.get("bloom_level"),
            bloom_level_number=q_data.get("bloom_level_number"),
        )
        db.add(next_question)

        # Update session state
        session.current_bloom_level = decision.bloom_level.id
        next_question_data = next_question

    else:
        # Interview complete (auto-stop or safety limit reached)
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        session.completion_reason = "auto_stop_fundamental_struggle" if is_auto_stop else "max_questions_safety_limit"

        if session.mode == "syllabus":
            if session.syllabus_state:
                s_state = SyllabusState.deserialize(session.syllabus_state)
                s_summary = calculate_syllabus_summary(s_state)
                session.final_recommendations = s_summary.get("recommendations")
            # Knowledge Ingestion with Deduplication (post-interview only)
            if session.syllabus_id:
                try:
                    merge_temporary_to_permanent_kb(session.syllabus_id)
                except Exception as e:
                    print(f"[InterviewService] Warning: Post-interview syllabus merge error: {e}")
                delete_temporary_rag(session.syllabus_id)
        else:
            summary = calculate_session_summary(state)
            session.final_recommendations = summary.get("recommendations")

    # Persist adaptive state
    session.adaptive_state = state.serialize()
    db.commit()

    if next_question_data:
        db.refresh(next_question_data)

    return {
        "evaluation": eval_result.to_dict(),
        "next_question": next_question_data,
        "is_complete": is_complete,
        "questions_answered": state.questions_answered,
        "questions_remaining": state.questions_remaining,
        "current_bloom_level": state.current_bloom_id,
        "current_difficulty": state.current_difficulty,
    }


# ── Legacy Answer Submission (Week 7 backward compat) ─────

def submit_answer(
    db: Session,
    user_id: int,
    session_id: int,
    question_number: int,
    answer_text: str,
) -> Answer:
    """Submit or update an answer for a question (legacy non-adaptive flow)."""

    # Validate session ownership
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == user_id,
    ).first()
    if not session:
        raise ValueError("Interview session not found")

    # Find the question
    question = db.query(InterviewQuestion).filter(
        InterviewQuestion.session_id == session_id,
        InterviewQuestion.question_number == question_number,
    ).first()
    if not question:
        raise ValueError(f"Question {question_number} not found in this session")

    # Check if answer already exists
    existing = db.query(Answer).filter(Answer.question_id == question.id).first()
    if existing:
        existing.answer_text = answer_text
        existing.submitted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    answer = Answer(
        question_id=question.id,
        session_id=session_id,
        user_id=user_id,
        answer_text=answer_text,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


# ── Complete Interview ────────────────────────────────────

def complete_interview(db: Session, user_id: int, session_id: int, completion_reason: str = "manual") -> InterviewSession:
    """Mark an interview session as completed and generate final results."""
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == user_id,
    ).first()
    if not session:
        raise ValueError("Interview session not found")

    if session.status == "completed":
        return session

    # For adaptive sessions, generate final recommendations
    if session.mode == "syllabus":
        if session.syllabus_state:
            try:
                s_state = SyllabusState.deserialize(session.syllabus_state)
                s_summary = calculate_syllabus_summary(s_state)
                session.final_recommendations = s_summary.get("recommendations")
            except Exception as e:
                print(f"[InterviewService] Warning: Could not generate syllabus recommendations: {e}")
        # Lifecycle cleanup: merge new syllabus knowledge into technical_kb then delete temporary Chroma collection
        if session.syllabus_id:
            try:
                merge_temporary_to_permanent_kb(session.syllabus_id)
            except Exception as e:
                print(f"[InterviewService] Warning: Post-interview syllabus merge error: {e}")
            delete_temporary_rag(session.syllabus_id)
    elif session.is_adaptive and session.adaptive_state:
        try:
            state = AdaptiveState.deserialize(session.adaptive_state)
            summary = calculate_session_summary(state)
            session.final_recommendations = summary.get("recommendations")
        except Exception as e:
            print(f"[InterviewService] Warning: Could not generate recommendations: {e}")

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    if not session.completion_reason:
        session.completion_reason = completion_reason
    db.commit()
    db.refresh(session)
    return session


# ── Statistics ────────────────────────────────────────────

def get_user_stats(db: Session, user_id: int) -> dict:
    """Get interview statistics for a user."""
    total_sessions = db.query(sql_func.count(InterviewSession.id)).filter(
        InterviewSession.user_id == user_id
    ).scalar() or 0

    completed_sessions = db.query(sql_func.count(InterviewSession.id)).filter(
        InterviewSession.user_id == user_id,
        InterviewSession.status == "completed",
    ).scalar() or 0

    total_questions = db.query(sql_func.count(InterviewQuestion.id)).join(
        InterviewSession
    ).filter(InterviewSession.user_id == user_id).scalar() or 0

    total_answered = db.query(sql_func.count(Answer.id)).filter(
        Answer.user_id == user_id
    ).scalar() or 0

    # Average score from evaluations
    avg_score_result = (
        db.query(sql_func.avg(AnswerEvaluation.overall_score))
        .join(Answer, AnswerEvaluation.answer_id == Answer.id)
        .filter(Answer.user_id == user_id)
        .scalar()
    )
    avg_score = round(float(avg_score_result), 1) if avg_score_result else None

    return {
        "total_interviews": total_sessions,
        "completed_interviews": completed_sessions,
        "total_questions": total_questions,
        "total_answered": total_answered,
        "average_score": avg_score,
    }


# ── Performance Data (Week 10 Dashboard) ──────────────────

def get_user_performance(db: Session, user_id: int) -> dict:
    """
    Get aggregated performance data for the user across all evaluated interviews.
    Returns ONLY real data — no fake percentages or placeholders.
    """
    # Get all completed adaptive sessions
    sessions = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
            InterviewSession.is_adaptive == True,
        )
        .order_by(InterviewSession.completed_at.desc())
        .all()
    )

    if not sessions:
        return {
            "has_data": False,
            "overall_average": None,
            "skill_performance": {},
            "bloom_progression": [],
            "strengths": [],
            "weak_areas": [],
            "recommendations": [],
            "recent_interviews": [],
        }

    # Aggregate per-skill performance
    skill_data = {}  # skill -> {total_score, count, bloom_levels}
    all_recommendations = []
    recent_interviews = []
    bloom_progression = []
    bloom_data = {}  # level -> {total_score, count}

    for sess in sessions:
        # Get evaluations for this session
        evaluations = (
            db.query(AnswerEvaluation)
            .join(InterviewQuestion, AnswerEvaluation.question_id == InterviewQuestion.id)
            .filter(InterviewQuestion.session_id == sess.id)
            .all()
        )

        questions = (
            db.query(InterviewQuestion)
            .filter(InterviewQuestion.session_id == sess.id)
            .order_by(InterviewQuestion.question_number)
            .all()
        )

        session_scores = []
        session_skills_data = {}
        for ev in evaluations:
            q = db.query(InterviewQuestion).filter(InterviewQuestion.id == ev.question_id).first()
            if q:
                skill = q.skill
                if skill not in skill_data:
                    skill_data[skill] = {"total_score": 0, "count": 0, "bloom_levels": []}
                skill_data[skill]["total_score"] += ev.overall_score
                skill_data[skill]["count"] += 1
                
                if skill not in session_skills_data:
                    session_skills_data[skill] = []
                session_skills_data[skill].append(ev.overall_score)
                
                if q.bloom_level:
                    skill_data[skill]["bloom_levels"].append(q.bloom_level_number or 1)
                    level_name = str(q.bloom_level).capitalize()
                    if level_name not in bloom_data:
                        bloom_data[level_name] = {"total_score": 0, "count": 0}
                    bloom_data[level_name]["total_score"] += ev.overall_score
                    bloom_data[level_name]["count"] += 1
                session_scores.append(ev.overall_score)

        # Track bloom progression per question in session
        for q in questions:
            if q.bloom_level_number:
                bloom_progression.append({
                    "session_id": sess.id,
                    "question_number": q.question_number,
                    "bloom_level": q.bloom_level,
                    "bloom_order": q.bloom_level_number,
                })

        # Session summary for recent interviews
        avg = round(sum(session_scores) / len(session_scores), 1) if session_scores else 0
        
        session_strong_areas = []
        session_focus_next = []
        for s_skill, s_scores in session_skills_data.items():
            s_avg = sum(s_scores) / len(s_scores) if s_scores else 0
            if s_avg >= 75:
                session_strong_areas.append(s_skill)
            elif s_avg < 50:
                session_focus_next.append(s_skill)
                
        recent_interviews.append({
            "id": sess.id,
            "date": sess.completed_at.isoformat() if sess.completed_at else None,
            "average_score": avg,
            "question_count": sess.question_count,
            "difficulty": sess.difficulty,
            "skills": sess.selected_skills or list(session_skills_data.keys()),
            "strong_areas": session_strong_areas,
            "focus_next": session_focus_next,
        })

        # Collect recommendations
        if sess.final_recommendations:
            for rec in sess.final_recommendations:
                if isinstance(rec, dict) and rec.get("message"):
                    all_recommendations.append(rec)

    # Calculate skill performance
    skill_performance = {}
    strengths = []
    weak_areas = []

    for skill, data in skill_data.items():
        avg = round(data["total_score"] / data["count"], 1) if data["count"] > 0 else 0
        max_bloom = max(data["bloom_levels"]) if data["bloom_levels"] else 1
        skill_performance[skill] = {
            "average_score": avg,
            "questions_answered": data["count"],
            "highest_bloom_order": max_bloom,
        }
        if avg >= 75:
            strengths.append(skill)
        elif avg < 50:
            weak_areas.append(skill)

    # Overall average
    total_score = sum(d["total_score"] for d in skill_data.values())
    total_count = sum(d["count"] for d in skill_data.values())
    overall_avg = round(total_score / total_count, 1) if total_count > 0 else 0

    # Deduplicate recommendations — keep most recent per skill
    seen_skills = set()
    unique_recs = []
    for rec in all_recommendations:
        s = rec.get("skill", "")
        if s not in seen_skills:
            seen_skills.add(s)
            unique_recs.append(rec)

    bloom_performance = {}
    for level, data in bloom_data.items():
        bloom_performance[level] = round(data["total_score"] / data["count"], 1) if data["count"] > 0 else 0

    return {
        "has_data": True,
        "overall_average": overall_avg,
        "skill_performance": skill_performance,
        "bloom_progression": bloom_progression[:50],  # limit for payload size
        "bloom_performance": bloom_performance,
        "strengths": strengths,
        "weak_areas": weak_areas,
        "recommendations": unique_recs[:10],
        "recent_interviews": recent_interviews[:10],
    }


# ── Session Results ───────────────────────────────────────

def get_session_results(db: Session, user_id: int, session_id: int) -> dict:
    """
    Get rich results for a completed interview session.
    Includes per-question evaluations, skill breakdown, bloom progression,
    and recommendations — all from actual stored data.
    """
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == user_id,
    ).first()
    if not session:
        raise ValueError("Interview session not found")

    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session.id)
        .order_by(InterviewQuestion.question_number)
        .all()
    )

    question_results = []
    skill_scores = {}  # skill -> [scores]
    bloom_data = []

    for q in questions:
        answer = db.query(Answer).filter(Answer.question_id == q.id).first()
        evaluation = db.query(AnswerEvaluation).filter(
            AnswerEvaluation.question_id == q.id
        ).first()

        q_result = {
            "id": q.id,
            "question_number": q.question_number,
            "skill": q.skill,
            "question_type": q.question_type,
            "difficulty": q.difficulty,
            "question_text": q.question_text,
            "bloom_level": q.bloom_level,
            "bloom_level_number": q.bloom_level_number,
            "answer_text": answer.answer_text if answer else None,
            "evaluation": None,
        }

        if evaluation:
            q_result["evaluation"] = {
                "technical_score": evaluation.technical_score,
                "completeness_score": evaluation.completeness_score,
                "relevance_score": evaluation.relevance_score,
                "semantic_similarity_score": evaluation.semantic_similarity_score,
                "concept_coverage_score": evaluation.concept_coverage_score,
                "overall_score": evaluation.overall_score,
                "feedback": evaluation.feedback,
                "strengths": evaluation.strengths,
                "weaknesses": evaluation.weaknesses,
                "concepts_expected": evaluation.concepts_expected,
                "concepts_found": evaluation.concepts_found,
            }

            # Track per-skill scores
            if q.skill not in skill_scores:
                skill_scores[q.skill] = []
            skill_scores[q.skill].append(evaluation.overall_score)

        # Track bloom progression
        if q.bloom_level_number:
            bloom_data.append({
                "question_number": q.question_number,
                "bloom_level": q.bloom_level,
                "bloom_order": q.bloom_level_number,
            })

        question_results.append(q_result)

    # Calculate skill performance
    skill_performance = {}
    for skill, scores in skill_scores.items():
        skill_performance[skill] = {
            "average_score": round(sum(scores) / len(scores), 1),
            "questions": len(scores),
        }

    # Overall average
    all_scores = [s for scores in skill_scores.values() for s in scores]
    overall_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

    return {
        "session": {
            "id": session.id,
            "difficulty": session.difficulty,
            "question_type": session.question_type,
            "question_count": session.question_count,
            "selected_skills": session.selected_skills,
            "status": session.status,
            "completion_reason": session.completion_reason,
            "is_adaptive": session.is_adaptive,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        },
        "overall_average_score": overall_avg,
        "skill_performance": skill_performance,
        "bloom_progression": bloom_data,
        "questions": question_results,
        "recommendations": session.final_recommendations or [],
    }


# ── RAG Context Helper ───────────────────────────────────

def _get_rag_context_for_eval(question: InterviewQuestion, session: InterviewSession | None = None) -> list[dict] | None:
    """
    Re-retrieve RAG chunks with full text for evaluation.
    Supports both permanent technical_kb and temporary syllabus collections.
    """
    if not question.rag_context:
        return None

    try:
        import chromadb
        from app.config import CHROMA_DB_DIR
        client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

        if session and session.mode == "syllabus" and session.syllabus_id:
            collection = client.get_collection(f"temp_syllabus_{session.syllabus_id}")
        else:
            from app.services.question_service import get_chroma_collection
            collection = get_chroma_collection()

        chunk_ids = [c["chunk_id"] for c in question.rag_context if "chunk_id" in c]
        if not chunk_ids:
            return None

        results = collection.get(ids=chunk_ids, include=["documents", "metadatas"])

        chunks = []
        if results and results.get("ids"):
            for i, cid in enumerate(results["ids"]):
                chunks.append({
                    "chunk_id": cid,
                    "domain": results["metadatas"][i].get("domain", "") if results.get("metadatas") else "",
                    "concept": results["metadatas"][i].get("concept", "") if results.get("metadatas") else "",
                    "text": results["documents"][i] if results.get("documents") else "",
                })
        return chunks if chunks else None

    except Exception as e:
        print(f"[InterviewService] Warning: Could not re-retrieve RAG context: {e}")
        return None

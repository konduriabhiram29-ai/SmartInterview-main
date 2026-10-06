"""
SmartInterview — Question Generation Service
Wraps the EXISTING Week 6 generate_question.py functions.

This service imports the standalone functions directly from generate_question.py
WITHOUT modifying that file. Both the CLI and the API use the same engine.

Week 8 additions:
    - generate_single_question(): generates ONE question with Bloom-level guidance
    - Safe Groq model verification (no sys.exit)
    - Exposes singletons for use by evaluation_service.py

Phase 1 (Hybrid Graph RAG):
    - Retrieval now goes through app.rag.retriever_factory.get_retriever()
    - RAG_MODE=dense (default) → VectorRetriever, identical to previous behaviour
    - All return shapes, function signatures, and external contracts are unchanged
"""

import sys
import os
import importlib.util
import json
import time
import threading

from app.config import SCRIPTS_DIR, CHROMA_DB_DIR, PROMPTS_FILE

# ── Import existing Week 6 functions ──────────────────────
_gen_path = os.path.join(SCRIPTS_DIR, "generate_question.py")
_spec = importlib.util.spec_from_file_location("generate_question_mod", _gen_path)
_gen_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen_mod)

# All functions from Week 6, unchanged
load_prompts = _gen_mod.load_prompts
find_project_for_skill = _gen_mod.find_project_for_skill
resolve_skill_domains = _gen_mod.resolve_skill_domains
build_rag_query = _gen_mod.build_rag_query
retrieve_rag_context = _gen_mod.retrieve_rag_context
build_prompt = _gen_mod.build_prompt
call_groq = _gen_mod.call_groq
QUESTION_TYPES = _gen_mod.QUESTION_TYPES
SKILL_DOMAIN_MAP = _gen_mod.SKILL_DOMAIN_MAP

# ── Lazy-initialized singletons ──────────────────────────
_lock = threading.Lock()
_embedding_model = None
_chroma_collection = None
_groq_client = None
_groq_model = None
_prompts = None

# ── Retriever & Reranker singletons (Phase 1, 9, 10) ─────
_retriever = None
_reranker = None


def _init_rag():
    """Initialize SentenceTransformer + ChromaDB (once, thread-safe)."""
    global _embedding_model, _chroma_collection
    if _embedding_model is not None and _chroma_collection is not None:
        return
    with _lock:
        if _embedding_model is not None and _chroma_collection is not None:
            return
        from sentence_transformers import SentenceTransformer
        import chromadb
        if _embedding_model is None:
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        if _chroma_collection is None:
            client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
            _chroma_collection = client.get_collection(name="technical_kb")


def _init_groq():
    """Initialize Unified LLM client (Groq with local Ollama fallback, thread-safe)."""
    global _groq_client, _groq_model
    if _groq_client is not None:
        return
    with _lock:
        if _groq_client is not None:
            return
        from app.services.llm_client import get_universal_llm_client, get_universal_model_name
        _groq_client = get_universal_llm_client()
        _groq_model = get_universal_model_name()


def _get_prompts():
    """Load prompts once."""
    global _prompts
    if _prompts is None:
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            _prompts = json.load(f)
    return _prompts


def _get_retriever(mode: str | None = None):
    """
    Return the active BaseRetriever singleton.
    Respects app.config.RAG_MODE (dense, keyword, graph, hybrid).
    """
    global _retriever
    _init_rag()  # ensure embedding model and collection are ready
    from app.config import RAG_MODE
    effective_mode = (mode or RAG_MODE or "dense").lower().strip()
    if _retriever is None or getattr(_retriever, "_mode", None) != effective_mode:
        with _lock:
            if _retriever is None or getattr(_retriever, "_mode", None) != effective_mode:
                from app.rag.retriever_factory import get_retriever
                _retriever = get_retriever(
                    embedding_model=_embedding_model,
                    chroma_collection=_chroma_collection,
                    build_rag_query_fn=build_rag_query,
                    mode=effective_mode,
                )
                setattr(_retriever, "_mode", effective_mode)
    return _retriever


def _get_reranker():
    """Return the active BaseReranker singleton (Phase 9 & 10)."""
    global _reranker
    _init_rag()
    if _reranker is None:
        with _lock:
            if _reranker is None:
                from app.rag.reranker import get_reranker
                _reranker = get_reranker(embedding_model=_embedding_model)
    return _reranker


# ── Singleton Accessors (for evaluation_service) ─────────

def get_embedding_model():
    """Get the lazy-initialized embedding model singleton."""
    _init_rag()
    return _embedding_model


def get_groq_client():
    """Get the lazy-initialized Groq client singleton."""
    _init_groq()
    return _groq_client


def get_groq_model_name():
    """Get the verified Groq model name."""
    _init_groq()
    return _groq_model


def get_chroma_collection():
    """Get the ChromaDB collection singleton."""
    _init_rag()
    return _chroma_collection


# ── Single Question Generation (Week 8 — Adaptive) ──────

def generate_single_question(
    skill: str,
    difficulty: str,
    question_type: str,
    bloom_level=None,
    projects: list[dict] | None = None,
    previous_questions: list[str] | None = None,
    previous_skill: str | None = None,
    weak_topics: list[str] | None = None,
    **kwargs,
) -> dict:
    """
    Generate ONE interview question with optional Bloom-level guidance,
    weak-topic remediation, and conversational continuity.

    Adaptive RAG Pipeline:
        resolve_skill_domains → retrieve (Bloom & weak-topic aware) → rerank → build_prompt → call_groq

    Args:
        skill: The technical skill to ask about
        difficulty: easy / medium / hard
        question_type: conceptual / practical / technical_reasoning / scenario / project
        bloom_level: Optional BloomLevel object for cognitive-level guidance
        projects: Candidate's projects for personalization
        previous_questions: Previously asked questions for deduplication
        previous_skill: Previous question's skill for natural conversational continuity
        weak_topics: Optional list of identified weak topics for prerequisite remediation

    Returns:
        Dict with: skill, question_type, difficulty, question_text,
                    bloom_level, bloom_level_number, rag_context, project_context,
                    rag_retrieval_results, weak_topics
    """
    _init_rag()
    _init_groq()
    prompts = _get_prompts()

    projects = projects or []
    previous_questions = previous_questions or []
    weak_topics = weak_topics or []

    # Resolve skill → knowledge-base domains
    skill_domains = resolve_skill_domains(skill)

    # ── RAG retrieval via retriever abstraction (Phase 1, 6, 7, 8, 10) ──
    from app.config import RAG_MODE, RERANKER_ENABLED, RERANKER_TOP_K
    retriever = _get_retriever()
    rag_query = build_rag_query(skill, skill_domains)
    bloom_id = bloom_level.id if hasattr(bloom_level, "id") else (str(bloom_level) if bloom_level else None)
    fetch_k = 10 if RAG_MODE in {"hybrid", "graph"} else 3

    retrieval_results = retriever.retrieve(
        query=rag_query,
        skill=skill,
        domains=skill_domains,
        top_k=fetch_k,
        bloom_level=bloom_id,
        weak_topics=weak_topics,
        **kwargs,
    )

    # ── Contextual Reranking (Phase 9 & 10) ──
    if RERANKER_ENABLED and len(retrieval_results) > 1:
        reranker = _get_reranker()
        if reranker is not None:
            retrieval_results = reranker.rerank(
                query=rag_query,
                results=retrieval_results,
                top_k=RERANKER_TOP_K,
            )

    # Convert RetrievalResult objects back to the legacy dict shape so that
    # build_prompt() and the rest of this function remain unchanged.
    rag_chunks = [
        {
            "chunk_id": r.chunk_id,
            "domain": r.domain,
            "concept": r.concept,
            "text": r.text,
            "distance": r.vector_score,
            "score": r.final_score,
            "retriever": r.retriever,
            "metadata": r.metadata,
        }
        for r in retrieval_results[:3]
    ]

    # Optional project context — uses existing function
    project_ctx = find_project_for_skill(skill, projects)

    # Build prompt — uses existing function with Bloom augmentation
    system_prompt, user_prompt = build_prompt(
        skill=skill,
        rag_chunks=rag_chunks,
        project_context=project_ctx,
        difficulty=difficulty,
        question_type=question_type,
        previous_questions=previous_questions,
        prompts=prompts,
    )

    # Add Bloom-level guidance to the user prompt
    if bloom_level is not None:
        bloom_instruction = (
            f"\n\nCognitive Level: {bloom_level.name}\n"
            f"{bloom_level.question_guidance}\n"
            f"The question MUST target the '{bloom_level.name}' cognitive level."
        )
        user_prompt += bloom_instruction

    # Add subtle conversational transition guidance for subsequent questions
    if previous_questions and len(previous_questions) > 0:
        if previous_skill and previous_skill.lower() == skill.lower():
            user_prompt += (
                "\n\nConversational Transition: We are continuing on the same technical topic. "
                "You may open naturally with a brief, professional transition like 'Taking that a step further...', "
                "'Now let's examine that from a practical perspective...', or 'Building on that...'. "
                "Keep it concise, calm, and professional. Do NOT use empty filler praise like 'Great answer!'."
            )
        elif previous_skill:
            user_prompt += (
                f"\n\nConversational Transition: We are transitioning from {previous_skill} to {skill}. "
                f"You may open naturally with a brief, professional transition like 'Let's shift our focus to {skill}...', "
                f"'Moving to another area of your technical stack: {skill}...', or 'Now let's look at {skill}...'. "
                "Keep it concise, calm, and professional. Do NOT use empty filler praise."
            )

    # Call Groq — uses existing function with retry/backoff
    question_text = call_groq(system_prompt, user_prompt, _groq_client, _groq_model)

    # Serialize RAG chunk metadata (not full text, to keep DB clean)
    rag_meta = None
    rag_context_full = None  # Full context for evaluation later
    if rag_chunks:
        rag_meta = [
            {"chunk_id": c["chunk_id"], "domain": c["domain"], "concept": c["concept"]}
            for c in rag_chunks[:3]
        ]
        rag_context_full = [
            {"chunk_id": c["chunk_id"], "domain": c["domain"], "concept": c["concept"], "text": c.get("text", "")}
            for c in rag_chunks[:3]
        ]

    proj_meta = None
    if project_ctx:
        proj_meta = {
            "name": project_ctx.get("name", ""),
            "technologies": project_ctx.get("technologies", []),
        }

    result = {
        "skill": skill,
        "question_type": question_type,
        "difficulty": difficulty,
        "question_text": question_text or "[GENERATION FAILED]",
        "rag_context": rag_meta,
        "rag_context_full": rag_context_full,  # kept for evaluation, NOT stored in DB
        "project_context": proj_meta,
        "bloom_level": bloom_level.id if hasattr(bloom_level, "id") else (str(bloom_level) if bloom_level else None),
        "bloom_level_number": bloom_level.order if hasattr(bloom_level, "order") else None,
        "rag_retrieval_results": [r.to_dict() for r in retrieval_results[:3]],
        "weak_topics": weak_topics or [],
    }

    return result


# ── Batch Question Generation (Week 7 — Legacy) ─────────

def generate_questions(
    skills: list[str],
    projects: list[dict],
    difficulty: str,
    question_type: str,
    count: int,
    selected_skills: list[str] | None = None,
) -> list[dict]:
    """
    Generate interview questions using the existing Week 6 engine.
    PRESERVED for backward compatibility with legacy (non-adaptive) sessions.

    Args:
        skills: All skills extracted from resume
        projects: All projects extracted from resume
        difficulty: easy / medium / hard
        question_type: conceptual / practical / technical_reasoning / scenario / project / mixed
        count: Number of questions (1-10)
        selected_skills: Optional subset of skills to use. If None, uses all skills.

    Returns:
        List of dicts: [{skill, question_type, difficulty, question_text, rag_context, project_context}, ...]
    """
    _init_rag()
    _init_groq()
    prompts = _get_prompts()

    # Use selected skills if provided, otherwise use all
    use_skills = selected_skills if selected_skills else skills
    if not use_skills:
        use_skills = skills

    # Deterministic rotation (same as Week 6 main())
    skill_rotation = [use_skills[i % len(use_skills)] for i in range(count)]

    # Question type rotation (same as Week 6 main())
    if question_type == "mixed":
        slot_types = [QUESTION_TYPES[i % len(QUESTION_TYPES)] for i in range(count)]
    else:
        slot_types = [question_type] * count

    generated = []
    previous_questions = []

    for i in range(count):
        skill = skill_rotation[i]
        q_type = slot_types[i]

        # Resolve skill → knowledge-base domains
        skill_domains = resolve_skill_domains(skill)

        # ── RAG retrieval via retriever abstraction (Phase 1) ──
        retriever = _get_retriever()
        rag_query = build_rag_query(skill, skill_domains)
        retrieval_results = retriever.retrieve(
            query=rag_query,
            skill=skill,
            domains=skill_domains,
            top_k=3,
        )
        rag_chunks = [
            {
                "chunk_id": r.chunk_id,
                "domain": r.domain,
                "concept": r.concept,
                "text": r.text,
                "distance": r.vector_score,
            }
            for r in retrieval_results
        ]

        # Optional project context — uses existing function
        project_ctx = find_project_for_skill(skill, projects)

        # Build prompt — uses existing function
        system_prompt, user_prompt = build_prompt(
            skill=skill,
            rag_chunks=rag_chunks,
            project_context=project_ctx,
            difficulty=difficulty,
            question_type=q_type,
            previous_questions=previous_questions,
            prompts=prompts,
        )

        # Call Groq — uses existing function with retry/backoff
        question_text = call_groq(system_prompt, user_prompt, _groq_client, _groq_model)

        if question_text:
            previous_questions.append(question_text)

            # Serialize RAG chunk metadata (not full text, to keep DB clean)
            rag_meta = None
            if rag_chunks:
                rag_meta = [
                    {"chunk_id": c["chunk_id"], "domain": c["domain"], "concept": c["concept"]}
                    for c in rag_chunks[:3]
                ]

            proj_meta = None
            if project_ctx:
                proj_meta = {
                    "name": project_ctx.get("name", ""),
                    "technologies": project_ctx.get("technologies", []),
                }

            generated.append({
                "question_number": i + 1,
                "skill": skill,
                "question_type": q_type,
                "difficulty": difficulty,
                "question_text": question_text,
                "rag_context": rag_meta,
                "project_context": proj_meta,
            })
        else:
            generated.append({
                "question_number": i + 1,
                "skill": skill,
                "question_type": q_type,
                "difficulty": difficulty,
                "question_text": "[GENERATION FAILED]",
                "rag_context": None,
                "project_context": None,
            })

        # Rate limit spacing between questions
        if i < count - 1:
            time.sleep(1)

    return generated


# ── Syllabus Question Generation (Shared Adaptive Engine) ─

def generate_syllabus_question(
    topic: str,
    difficulty: str,
    question_type: str,
    syllabus_id: str,
    bloom_level=None,
    previous_questions: list[str] | None = None,
    previous_topic: str | None = None,
) -> dict:
    """
    Generate ONE interview question for Syllabus Mode strictly grounded in
    the temporary RAG collection (temp_syllabus_<syllabus_id>).

    Follows the shared adaptive architecture:
    - Topic: Provided by SyllabusState.
    - Difficulty & Bloom Level: Provided by the shared Adaptive Engine.
    - Grounding: Strictly constrained to retrieved document chunks.
    """
    import chromadb

    _init_rag()
    _init_groq()
    prompts = _get_prompts()
    previous_questions = previous_questions or []

    # 1. Connect to isolated temporary collection
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    collection_name = f"temp_syllabus_{syllabus_id}"
    try:
        temp_collection = client.get_collection(name=collection_name)
    except Exception:
        raise ValueError(f"Temporary syllabus RAG collection not found: {collection_name}")

    # 2. Semantic query strictly within temporary collection
    query = f"{topic} definitions mechanisms concepts principles examples"
    query_embedding = _embedding_model.encode(query, convert_to_numpy=True).tolist()

    results = temp_collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        include=["documents", "metadatas"],
    )

    rag_chunks = []
    if results and results.get("ids") and results["ids"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
            rag_chunks.append({
                "chunk_id": results["ids"][0][i],
                "domain": meta.get("domain", "Syllabus"),
                "concept": topic,
                "text": doc,
            })

    # 3. Build strictly source-grounded prompt
    if rag_chunks:
        rag_parts = [f"[Excerpt {j+1} - {c['domain']}]:\n{c['text'][:500]}" for j, c in enumerate(rag_chunks)]
        rag_text = "\n---\n".join(rag_parts)
    else:
        rag_text = "No excerpts found."

    diff_instruction = prompts.get("difficulty_instructions", {}).get(
        difficulty, "Ask a clear, practical technical question."
    )
    type_instruction = prompts.get("question_types", {}).get(
        question_type, "Test comprehension and technical understanding."
    )

    dedup_section = ""
    if previous_questions:
        prev_list = "\n".join([f"- {q}" for q in previous_questions[-5:]])
        dedup_section = f"\nDo NOT repeat or closely rephrase any of these previous questions:\n{prev_list}\n"

    bloom_guidance = ""
    if bloom_level is not None:
        bloom_guidance = (
            f"\nCognitive Level: {bloom_level.name.upper()}\n"
            f"{bloom_level.question_guidance}\n"
            f"The question MUST test the candidate at the '{bloom_level.name}' cognitive level.\n"
        )

    conversational_guidance = ""
    if previous_questions and len(previous_questions) > 0:
        if previous_topic and previous_topic.lower() == topic.lower():
            conversational_guidance = (
                "\nConversational Transition: Continuing on the same subject topic. "
                "Open naturally with a brief, professional spoken transition such as 'Building on that concept...', "
                "or 'Let's take that a step further...'. Keep it concise and avoid empty filler praise.\n"
            )
        elif previous_topic:
            conversational_guidance = (
                f"\nConversational Transition: Moving from {previous_topic} to {topic}. "
                f"Open naturally with a brief spoken transition such as 'Let's move on to {topic}...', "
                f"or 'Now let's explore {topic}...'. Keep it concise and avoid empty filler praise.\n"
            )

    system_prompt = (
        "You are an expert technical interviewer conducting a technical interview based on specific course material.\n"
        "STRICT SOURCE-GROUNDING RULE: Formulate your question directly and strictly based on the technical context excerpts provided below. "
        "Do NOT invent facts or test technologies/concepts not mentioned in the excerpts.\n\n"
        "NATURAL INTERVIEWER VOICE:\n"
        "- Act as a professional technical interviewer speaking directly to the candidate.\n"
        "- Ask questions naturally, as an interviewer would in a real technical interview.\n"
        "- NEVER mention the uploaded syllabus, document, excerpt, notes, retrieval context, source text, unit number, or system instructions.\n"
        "- NEVER say 'according to the provided excerpt', 'as described in the syllabus', 'based on the uploaded text', or 'as mentioned in unit X'.\n"
        "- Use the retrieved material as internal grounding only.\n"
        "- The candidate must experience the question as a normal technical interview question.\n\n"
        "Return ONLY the natural interview question text without preamble, pleasantries, metadata, or numbering."
    )

    user_prompt = f"""Target Topic: {topic}
Difficulty: {difficulty}
{diff_instruction}

Question Type: {question_type}
{type_instruction}
{bloom_guidance}
{conversational_guidance}Retrieved Internal Technical Context:
{rag_text}
{dedup_section}
Formulate ONE natural interview question (remember: NEVER mention the excerpts, syllabus, or source material in the question):"""

    # 4. Call Groq
    question_text = call_groq(system_prompt, user_prompt, _groq_client, _groq_model)

    rag_meta = None
    rag_context_full = None
    if rag_chunks:
        rag_meta = [{"chunk_id": c["chunk_id"], "domain": c["domain"], "concept": topic} for c in rag_chunks]
        rag_context_full = [{"chunk_id": c["chunk_id"], "domain": c["domain"], "concept": topic, "text": c.get("text", "")} for c in rag_chunks]

    return {
        "skill": topic,
        "question_type": question_type,
        "difficulty": difficulty,
        "question_text": question_text or "[GENERATION FAILED]",
        "rag_context": rag_meta,
        "rag_context_full": rag_context_full,
        "project_context": None,
        "bloom_level": bloom_level.id if bloom_level else None,
        "bloom_level_number": bloom_level.order if bloom_level else None,
    }


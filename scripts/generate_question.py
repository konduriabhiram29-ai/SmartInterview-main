"""
SmartInterview — Technical Mock Interview Question Generator
Week 6: Skill-first, RAG-assisted, multi-question generation using Groq.

Usage:
    python scripts/generate_question.py --resume data/resumes/candidate.pdf
    python scripts/generate_question.py --resume data/resumes/candidate.pdf --count 5
    python scripts/generate_question.py --resume data/resumes/candidate.pdf --count 3 --difficulty hard --type mixed --verbose
"""

import os
import sys
import json
import argparse
import time
import importlib.util
import re

# Fix Windows terminal encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ============================================================
# CONSTANTS
# ============================================================

CHROMA_DB_DIR = "chroma_db"
COLLECTION_NAME = "technical_kb"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MAX_QUESTION_COUNT = 10
PROMPTS_FILE = os.path.join("prompts", "question_generation.json")
QUESTION_TYPES = ["conceptual", "practical", "technical_reasoning", "scenario", "project"]

# ============================================================
# SKILL → DOMAIN MAPPING (CENTRAL CANONICAL TAXONOMY)
# Maps canonical skills to relevant knowledge-base domains so that
# RAG retrieval is filtered to the most relevant chunks.
# ============================================================
SKILL_DOMAIN_MAP = {
    # --- Programming languages ---
    "java":        ["oop", "dsa", "design-patterns"],
    "python":      ["dsa", "oop", "ml-dl"],
    "c++":         ["oop", "dsa"],
    "c":           ["dsa", "os"],
    "c#":          ["oop", "dsa", "design-patterns"],
    "go":          ["dsa", "system-design", "os"],
    "rust":        ["dsa", "os"],
    "kotlin":      ["oop", "dsa"],
    "swift":       ["oop", "dsa"],
    "typescript":  ["dsa", "design-patterns"],
    "javascript":  ["dsa", "design-patterns"],
    "bash":        ["os"],
    "sql":         ["dbms"],
    # --- Database / SQL / Vector ---
    "postgresql":  ["dbms"],
    "mysql":       ["dbms"],
    "mongodb":     ["dbms"],
    "sqlite":      ["dbms"],
    "redis":       ["dbms", "system-design"],
    "dynamodb":    ["dbms", "system-design"],
    "pgvector":    ["dbms", "ml-dl"],
    "pinecone":    ["dbms", "ml-dl"],
    "qdrant":      ["dbms", "ml-dl"],
    "milvus":      ["dbms", "ml-dl"],
    # --- Backend, Distributed Systems & Messaging ---
    "grpc":        ["cn", "system-design"],
    "kafka":       ["system-design"],
    "rabbitmq":    ["system-design"],
    "distributed tracing": ["system-design"],
    "microservices": ["system-design"],
    "asyncio":     ["os", "design-patterns"],
    "rest api":    ["cn", "design-patterns"],
    "graphql":     ["cn", "design-patterns"],
    # --- Web / Frameworks ---
    "fastapi":     ["design-patterns", "system-design"],
    "flask":       ["design-patterns", "system-design"],
    "django":      ["design-patterns", "system-design"],
    "spring boot": ["design-patterns", "oop"],
    "node.js":     ["system-design", "design-patterns"],
    "express.js":  ["design-patterns", "system-design"],
    "react":       ["design-patterns", "dsa"],
    "angular":     ["design-patterns", "dsa"],
    "vue.js":      ["design-patterns", "dsa"],
    "html":        ["cn"],
    "css":         ["cn"],
    # --- AI / LLM Systems ---
    "rag":         ["ml-dl", "system-design"],
    "vllm":        ["ml-dl", "system-design"],
    "langchain":   ["ml-dl", "design-patterns"],
    "llamaindex":  ["ml-dl", "design-patterns"],
    "semantic caching": ["system-design", "ml-dl"],
    "tensorflow":  ["ml-dl"],
    "pytorch":     ["ml-dl"],
    "pandas":      ["ml-dl", "dsa"],
    "numpy":       ["ml-dl", "dsa"],
    "scikit-learn":["ml-dl"],
    "matplotlib":  ["ml-dl"],
    # --- DevOps / Cloud ---
    "docker":      ["os", "system-design"],
    "kubernetes":  ["system-design", "os"],
    "aws":         ["system-design", "cn"],
    "azure":       ["system-design", "cn"],
    "google cloud platform": ["system-design", "cn"],
    "terraform":   ["system-design"],
    "helm":        ["system-design"],
    "ci/cd":       ["system-design"],
    "git":         ["system-design"],
    "linux":       ["os"],
    # --- Observability & Reliability ---
    "opentelemetry": ["system-design"],
    "prometheus":  ["system-design"],
    "grafana":     ["system-design"],
    "datadog":     ["system-design"],
    # --- Testing ---
    "junit":       ["oop", "design-patterns"],
    "pytest":      ["oop", "design-patterns"],
}

# Canonical proper display names for skills
CANONICAL_SKILL_NAMES = {
    # Languages
    "python": "Python",
    "java": "Java",
    "c++": "C++",
    "c": "C",
    "c#": "C#",
    "go": "Go",
    "rust": "Rust",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "bash": "Bash",
    "sql": "SQL",
    # Databases & Vector Stores
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "sqlite": "SQLite",
    "redis": "Redis",
    "dynamodb": "DynamoDB",
    "pgvector": "pgvector",
    "pinecone": "Pinecone",
    "qdrant": "Qdrant",
    "milvus": "Milvus",
    # Backend & Distributed Systems
    "grpc": "gRPC",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "distributed tracing": "Distributed Tracing",
    "microservices": "Microservices",
    "asyncio": "AsyncIO",
    "rest api": "REST API",
    "graphql": "GraphQL",
    # Frameworks & Web
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "spring boot": "Spring Boot",
    "node.js": "Node.js",
    "express.js": "Express.js",
    "react": "React",
    "angular": "Angular",
    "vue.js": "Vue.js",
    "html": "HTML",
    "css": "CSS",
    # AI / LLM Systems
    "rag": "RAG",
    "vllm": "vLLM",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "semantic caching": "Semantic Caching",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "matplotlib": "Matplotlib",
    # Cloud & DevOps
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "google cloud platform": "Google Cloud Platform",
    "terraform": "Terraform",
    "helm": "Helm",
    "ci/cd": "CI/CD",
    "git": "Git",
    "linux": "Linux",
    # Observability & Reliability
    "opentelemetry": "OpenTelemetry",
    "prometheus": "Prometheus",
    "grafana": "Grafana",
    "datadog": "Datadog",
    # Testing
    "junit": "JUnit",
    "pytest": "PyTest",
}

# Aliases mapping variants to canonical keys
SKILL_ALIASES = {
    "golang": "go",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "sql (postgres)": "postgresql",
    "sql (postgresql)": "postgresql",
    "postgresql (query optimization)": "postgresql",
    "amazon web services": "aws",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "apache kafka": "kafka",
    "restful apis": "rest api",
    "restful api": "rest api",
    "rest apis": "rest api",
    "rest": "rest api",
    "rag architectures": "rag",
    "rag architecture": "rag",
    "retrieval-augmented generation": "rag",
    "retrieval augmented generation": "rag",
    "helm charts": "helm",
    "helm chart": "helm",
    "terraform modules": "terraform",
    "terraform iac": "terraform",
    "async.io": "asyncio",
    "github actions ci/cd": "ci/cd",
    "github actions": "ci/cd",
    "spring": "spring boot",
    "node": "node.js",
    "nodejs": "node.js",
    "express": "express.js",
    "vue": "vue.js",
    "vuejs": "vue.js",
    "developer tools: git": "git",
    "travisci": "ci/cd",
}


def _build_skill_pattern(phrase: str) -> re.Pattern:
    """Build a boundary-safe regex pattern for a skill or alias."""
    escaped = re.escape(phrase)
    # Left boundary: if word character, require non-word character before
    if phrase[0].isalnum() or phrase[0] == "_":
        left = r"(?<![a-zA-Z0-9_])"
    else:
        left = r"(?<!\S)"

    # Right boundary: if word character, require non-word character after
    if phrase[-1].isalnum() or phrase[-1] == "_":
        right = r"(?![a-zA-Z0-9_])"
    else:
        last_char = re.escape(phrase[-1])
        right = rf"(?![a-zA-Z0-9_{last_char}])"

    return re.compile(left + escaped + right, re.IGNORECASE)


def match_skills_in_text(text: str) -> list[str]:
    """
    Extract canonical technical skills from text using the central taxonomy:
      1. Longest / most-specific match first (phrase length descending).
      2. Token-safe boundary matching (word boundary or complete token for symbols).
      3. Overlap protection (shorter phrases cannot match inside an already matched span).
      4. Alias normalization to canonical display names.
      5. Deduplication while preserving order of first appearance.
    """
    if not text or not text.strip():
        return []

    # Build all (phrase, canonical_key) candidates
    candidates: list[tuple[str, str]] = []
    for canon_key in CANONICAL_SKILL_NAMES:
        candidates.append((canon_key, canon_key))
    for alias_key, canon_key in SKILL_ALIASES.items():
        candidates.append((alias_key, canon_key))

    # Sort candidates by descending phrase length (longest first)
    candidates.sort(key=lambda item: len(item[0]), reverse=True)

    # Track occupied character spans: list of (start, end)
    occupied_spans: list[tuple[int, int]] = []
    # Track matches: list of (start_index, canonical_display_name)
    found_matches: list[tuple[int, str]] = []

    for phrase, canon_key in candidates:
        pattern = _build_skill_pattern(phrase)
        for match in pattern.finditer(text):
            m_start, m_end = match.span()
            # Check if this match overlaps with any previously accepted longer match
            overlaps = any(
                not (m_end <= o_start or m_start >= o_end)
                for o_start, o_end in occupied_spans
            )
            if not overlaps:
                occupied_spans.append((m_start, m_end))
                display_name = CANONICAL_SKILL_NAMES.get(canon_key, canon_key.title())
                found_matches.append((m_start, display_name))

    # Sort matches by first appearance in the document
    found_matches.sort(key=lambda x: x[0])

    # Deduplicate while preserving order of first occurrence
    seen: set[str] = set()
    result: list[str] = []
    for _, skill_name in found_matches:
        lk = skill_name.lower()
        if lk not in seen:
            seen.add(lk)
            result.append(skill_name)

    return result

# Domain-specific query templates produce better semantic matches
# than the generic "Technical interview concepts related to {skill}"
DOMAIN_QUERY_TEMPLATES = {
    "dbms":            "SQL database {skill} concepts: indexing, joins, normalization, transactions, keys, ACID",
    "oop":             "Object-oriented programming {skill} concepts: classes, inheritance, polymorphism, encapsulation, abstraction",
    "dsa":             "Data structures and algorithms {skill}: arrays, trees, graphs, sorting, searching, complexity",
    "design-patterns": "Software design patterns {skill}: singleton, factory, observer, strategy, architecture",
    "system-design":   "System design {skill}: scalability, caching, load balancing, microservices, distributed systems",
    "os":              "Operating systems {skill}: processes, threads, memory management, scheduling, synchronization",
    "cn":              "Computer networking {skill}: protocols, TCP/IP, HTTP, DNS, OSI model, security",
    "ml-dl":           "Machine learning {skill}: regression, classification, neural networks, overfitting, bias-variance",
}


def load_prompts():
    """Load prompt templates from the prompt library."""
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_project_for_skill(skill, projects):
    """Find a candidate project that uses the given skill. Returns the project dict or None."""
    skill_lower = skill.lower().strip()
    for project in projects:
        # Check project technologies
        for tech in project.get("technologies", []):
            if skill_lower == tech.lower().strip():
                return project
        # Check project description
        desc = project.get("description", "").lower()
        if skill_lower in desc:
            return project
    return None


def resolve_skill_domains(skill):
    """
    Map a resume skill to its relevant knowledge-base domains.
    Returns a list of domain strings, or an empty list if no mapping found.
    """
    skill_lower = skill.lower().strip()

    # Direct lookup
    if skill_lower in SKILL_DOMAIN_MAP:
        return SKILL_DOMAIN_MAP[skill_lower]

    # Partial match — e.g. "sql (postgres)" contains "sql"
    for key, domains in SKILL_DOMAIN_MAP.items():
        if key in skill_lower or skill_lower in key:
            return domains

    return []


def build_rag_query(skill, domains):
    """
    Build a domain-aware RAG query string.
    Uses domain-specific templates when a domain mapping exists,
    falls back to a generic query otherwise.
    """
    if domains:
        primary_domain = domains[0]
        template = DOMAIN_QUERY_TEMPLATES.get(primary_domain)
        if template:
            return template.replace("{skill}", skill)
    # Fallback
    return f"Technical interview concepts related to {skill}"


def retrieve_rag_context(skill, embedding_model, collection, domains=None):
    """
    Retrieve RAG context for a given skill from ChromaDB.
    Uses domain-filtered search when domains are available,
    falls back to unfiltered search otherwise.
    Returns (chunks_list, query_string).
    """
    query = build_rag_query(skill, domains or [])
    query_embedding = embedding_model.encode(query, convert_to_numpy=True).tolist()

    # Build ChromaDB where-filter for domain(s)
    where_filter = None
    if domains:
        if len(domains) == 1:
            where_filter = {"domain": domains[0]}
        else:
            where_filter = {"$or": [{"domain": d} for d in domains]}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where=where_filter,
    )

    chunks = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            chunks.append({
                "chunk_id": results["ids"][0][i],
                "domain": results["metadatas"][0][i].get("domain", ""),
                "concept": results["metadatas"][0][i].get("concept", ""),
                "text": results["documents"][0][i],
                "distance": results["distances"][0][i] if results["distances"] else None,
            })

    return chunks, query


def build_prompt(skill, rag_chunks, project_context, difficulty, question_type, previous_questions, prompts):
    """Build the LLM prompt for a skill-based question."""
    system_prompt = prompts["system_prompt"]
    diff_instruction = prompts["difficulty_instructions"].get(difficulty, "")
    type_instruction = prompts["question_types"].get(question_type, "")

    # Deduplication
    dedup_section = ""
    if previous_questions:
        prev_list = "\n".join([f"- {q}" for q in previous_questions])
        dedup_section = prompts["dedup_instruction"].replace("{previous_questions}", prev_list)

    # RAG context
    if rag_chunks:
        rag_parts = []
        for c in rag_chunks[:3]:
            rag_parts.append(f"[{c['domain']}/{c['concept']}]\n{c['text']}")
        rag_text = "\n---\n".join(rag_parts)
    else:
        rag_text = "None available."

    # Optional project context
    project_section = ""
    if project_context:
        p_name = project_context.get("name", "")
        p_desc = project_context.get("description", "")[:200]
        p_techs = ", ".join(project_context.get("technologies", []))
        project_section = f"\nCandidate Project (optional personalization):\nProject: {p_name}\nDescription: {p_desc}\nTechnologies: {p_techs}"

    user_prompt = f"""{diff_instruction}

Question type: {question_type}
{type_instruction}

Selected Skill: {skill}
{project_section}

Retrieved Technical Context:
{rag_text}

{dedup_section}"""

    return system_prompt, user_prompt


def get_groq_model(groq_client):
    """Get and verify configured Groq model."""
    configured_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    try:
        models_response = groq_client.models.list()
        available_ids = {m.id for m in models_response.data}
        if configured_model not in available_ids:
            print(f"ERROR: Model '{configured_model}' is not available.")
            sys.exit(1)
        return configured_model
    except Exception as e:
        print(f"ERROR: Failed to verify model: {e}")
        sys.exit(1)


def call_groq(system_prompt, user_prompt, groq_client, model_name, max_retries=3):
    """Call Groq API to generate a question with retry + exponential backoff."""
    current_max_tokens = 1024

    for attempt in range(1, max_retries + 1):
        try:
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=current_max_tokens,
            )

            choice = response.choices[0]
            text = choice.message.content
            finish_reason = getattr(choice, "finish_reason", None)

            # Check for empty response (e.g. reasoning token exhaustion)
            if not text or not text.strip():
                print(f"  [Attempt {attempt}/{max_retries}] Empty response (finish_reason={finish_reason}), retrying with increased budget...")
                current_max_tokens = min(current_max_tokens + 256, 1500)
            # Check for truncated response (hit token limit)
            elif finish_reason == "length":
                print(f"  [Attempt {attempt}/{max_retries}] Truncated (hit {current_max_tokens} tokens), retrying with more...")
                current_max_tokens = min(current_max_tokens + 256, 1500)
            # Check if it was cut off mid-sentence without finish_reason="length"
            elif text.strip()[-1] not in ["?", ".", "!", '"', "'", "`"]:
                print(f"  [Attempt {attempt}/{max_retries}] Incomplete sentence detected (finish_reason={finish_reason}), retrying...")
                current_max_tokens = min(current_max_tokens + 256, 1500)
            else:
                return text.strip()

        except Exception as e:
            error_msg = str(e)
            print(f"  [Attempt {attempt}/{max_retries}] Error: {error_msg[:120]}")

        # Exponential backoff: 5s, 10s, 20s
        if attempt < max_retries:
            wait = 5 * (2 ** (attempt - 1))
            time.sleep(wait)

    # Automatic fallback to local Ollama if Cloud Groq is offline or unavailable
    try:
        import requests
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")
        print(f"  [Fallback] Cloud Groq unavailable. Querying local Ollama ({ollama_model})...")
        res = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False
            },
            timeout=60
        )
        if res.status_code == 200:
            return res.json()["message"]["content"].strip()
    except Exception as e_ollama:
        print(f"  [Fallback Error] Local Ollama failed: {e_ollama}")

    return None


def main():
    parser = argparse.ArgumentParser(description="SmartInterview — Technical Mock Interview")
    parser.add_argument("--resume", type=str, required=True, help="Path to candidate resume PDF")
    parser.add_argument("--count", type=int, default=1, help="Number of questions (1-10)")
    parser.add_argument("--difficulty", type=str, default="medium", choices=["easy", "medium", "hard"])
    parser.add_argument("--type", type=str, default="mixed",
                        choices=["conceptual", "technical_reasoning", "practical", "scenario", "project", "mixed"])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.resume):
        print(f"ERROR: Resume not found: {args.resume}")
        sys.exit(1)

    count = max(1, min(args.count, MAX_QUESTION_COUNT))

    # Load environment and dependencies
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv is required.")
        sys.exit(1)
    load_dotenv()

    prompts = load_prompts()

    from groq import Groq
    import chromadb
    from sentence_transformers import SentenceTransformer

    # Parse resume
    _pr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parse_resume.py")
    _spec = importlib.util.spec_from_file_location("parse_resume_mod", _pr_path)
    _pr_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_pr_mod)
    parse_resume_fn = _pr_mod.parse_resume

    try:
        profile = parse_resume_fn(args.resume)
    except Exception as e:
        print(f"ERROR: Failed to parse resume: {e}")
        sys.exit(1)

    skills = profile.get("skills", [])
    projects = profile.get("projects", [])

    if not skills:
        print("ERROR: No technical skills found in the resume.")
        sys.exit(1)

    # Groq setup
    groq_client = Groq()
    groq_model = get_groq_model(groq_client)

    # ============================================================
    # HEADER
    # ============================================================
    print("============================================================")
    print("SMARTINTERVIEW \u2014 TECHNICAL MOCK INTERVIEW")
    print("============================================================")
    print(f"\nResume       : {os.path.basename(args.resume)}")
    print(f"Model        : {groq_model}")
    print(f"Difficulty   : {args.difficulty.capitalize()}")
    print(f"Question Type: {args.type.capitalize()}")
    print(f"Questions    : {count}")

    # ============================================================
    # SKILL SELECTION (deterministic rotation)
    # ============================================================
    selected_skills = []
    for i in range(count):
        selected_skills.append(skills[i % len(skills)])

    print("\n============================================================")
    print(f"EXTRACTED SKILLS ({len(skills)})")
    print("============================================================")
    for i, s in enumerate(skills, 1):
        print(f"{i}. {s}")

    print("\n============================================================")
    print(f"SELECTED FOR QUESTIONS ({len(selected_skills)})")
    print("============================================================")
    for i, s in enumerate(selected_skills, 1):
        print(f"{i}. {s}")

    # ============================================================
    # RAG SETUP
    # ============================================================
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    collection = client.get_collection(name=COLLECTION_NAME)

    # Question type rotation
    if args.type == "mixed":
        slot_types = [QUESTION_TYPES[i % len(QUESTION_TYPES)] for i in range(count)]
    else:
        slot_types = [args.type] * count

    # ============================================================
    # QUESTION GENERATION
    # ============================================================
    print("\n============================================================")
    print("GENERATED QUESTIONS")
    print("============================================================")

    generated_questions = []
    skills_used = set()

    for i in range(count):
        skill = selected_skills[i]
        skills_used.add(skill)
        q_type = slot_types[i]

        # Resolve skill → knowledge-base domains
        skill_domains = resolve_skill_domains(skill)

        # RAG retrieval (domain-filtered)
        rag_chunks, rag_query = retrieve_rag_context(skill, embedding_model, collection, domains=skill_domains)
        rag_available = len(rag_chunks) > 0

        # Optional project context
        project_ctx = find_project_for_skill(skill, projects)

        # Build prompt
        system_prompt, user_prompt = build_prompt(
            skill=skill,
            rag_chunks=rag_chunks,
            project_context=project_ctx,
            difficulty=args.difficulty,
            question_type=q_type,
            previous_questions=generated_questions,
            prompts=prompts,
        )

        # Verbose output
        if args.verbose:
            print(f"\n--- QUESTION {i + 1} PIPELINE ---")
            print(f"Skill     : {skill}")
            print(f"Domains   : {', '.join(skill_domains) if skill_domains else 'None (unfiltered)'}")
            print(f"RAG Query : {rag_query}")
            if rag_chunks:
                print("Retrieved :")
                for c in rag_chunks[:3]:
                    dist_str = f"{c['distance']:.4f}" if c['distance'] is not None else "N/A"
                    print(f"  - {c['chunk_id']} (dist: {dist_str})")
            else:
                print("Retrieved : None")
            if project_ctx:
                print(f"Project   : {project_ctx.get('name', 'N/A')}")
            print(f"Type      : {q_type.title().replace('_', ' ')}")
            print(f"Difficulty: {args.difficulty.capitalize()}")
            print("---")

        # Generate question
        question = call_groq(system_prompt, user_prompt, groq_client, groq_model)

        if question:
            generated_questions.append(question)

            print(f"\nQUESTION {i + 1}")
            print("------------------------------------------------------------")
            print(f"Skill : {skill}")
            print(f"Type  : {q_type.title().replace('_', ' ')}")
            print(f"RAG   : {'Available' if rag_available else 'None available'}")
            print(f"\n{question}")
            print("\n------------------------------------------------------------")
        else:
            print(f"\nQuestion {i + 1}: [GENERATION FAILED]")

        # Rate limit spacing
        if i < count - 1:
            time.sleep(1)

    # ============================================================
    # FINAL RESULT
    # ============================================================
    print("\n============================================================")
    print("FINAL RESULT")
    print("============================================================")
    print(f"\nQuestions Generated : {len(generated_questions)} / {count}")
    print(f"Skills Used         : {len(skills_used)}")
    print("\n============================================================")
    print("WEEK 6 COMPLETE")
    print("============================================================")


if __name__ == "__main__":
    main()

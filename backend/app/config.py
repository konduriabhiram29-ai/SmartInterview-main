"""
SmartInterview — Application Configuration
Loads all settings from the project-root .env file.
"""

import os
from typing import Any
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Database ──────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:root@localhost:3306/smartinterview"
)

# ── Redis ─────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── JWT ───────────────────────────────────────────────────
# ── JWT ───────────────────────────────────────────────────
JWT_SECRET_KEY = (
    os.getenv("JWT_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "dev-secret-change-in-production"
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM") or os.getenv("ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(
    os.getenv("JWT_EXPIRATION_MINUTES")
    or os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
)

# ── Groq / AI ────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")

# ── Local / Ollama AI ────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq" or "ollama"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# ── Paths ─────────────────────────────────────────────────
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

SYLLABUS_UPLOAD_DIR = PROJECT_ROOT / "uploads" / "syllabi"
SYLLABUS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_raw_chroma_dir = os.getenv("CHROMA_DB_DIR", "chroma_db")
if os.path.isabs(_raw_chroma_dir):
    CHROMA_DB_DIR = str(Path(_raw_chroma_dir).resolve())
else:
    CHROMA_DB_DIR = str((PROJECT_ROOT / _raw_chroma_dir).resolve())

PROMPTS_FILE = str(PROJECT_ROOT / "prompts" / "question_generation.json")
SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")

# ── RAG Mode (Hybrid Graph RAG — Phase 1+) ────────────────
# Controls which retrieval strategy question_service.py uses.
#
# Available values:
#   dense    — ChromaDB dense vector retrieval only (DEFAULT, existing system)
#   keyword  — BM25 keyword retrieval only (Phase 7)
#   graph    — Neo4j graph retrieval only (Phase 6)
#   hybrid   — Dense + Keyword + Graph fusion (Phase 8+)
#
# The existing system is always available as fallback when RAG_MODE=dense.
RAG_MODE = os.getenv("RAG_MODE", "dense").lower().strip()

# ── Neo4j Knowledge Graph (Phase 5+) ─────────────────────
# Credentials must come from environment variables.
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
# Storage backend: "auto" (tries Neo4j, falls back to NetworkX), "neo4j", or "networkx"
GRAPH_STORAGE_BACKEND = os.getenv("GRAPH_STORAGE_BACKEND", "auto").lower().strip()

# ── Hybrid Retrieval (Phase 8+) ──────────────────────────
# Fusion method: "weighted" (weighted linear combination) or "rrf" (Reciprocal Rank Fusion)
HYBRID_FUSION_METHOD = os.getenv("HYBRID_FUSION_METHOD", "weighted").lower().strip()
HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.40"))
HYBRID_KEYWORD_WEIGHT = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.25"))
HYBRID_GRAPH_WEIGHT = float(os.getenv("HYBRID_GRAPH_WEIGHT", "0.35"))
HYBRID_RRF_K = int(os.getenv("HYBRID_RRF_K", "60"))
HYBRID_FETCH_K = int(os.getenv("HYBRID_FETCH_K", "10"))

# ── Reranking (Phase 9+) ─────────────────────────────────
# Controls whether candidates are reranked before prompt construction.
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower().strip() in {"true", "1", "yes"}
# Backend: "semantic" (using existing embedding model singleton), "cross_encoder", or "none"
RERANKER_BACKEND = os.getenv("RERANKER_BACKEND", "semantic").lower().strip()
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANKER_MIN_SCORE = float(os.getenv("RERANKER_MIN_SCORE", "0.0"))
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", "3"))


# ── Configuration Consistency & Security Audit (Phase 11) ─

def validate_config() -> dict[str, Any]:
    """
    Perform a security, consistency, and sanity audit on loaded configuration.
    Returns an audit report dictionary containing findings and status.
    """
    findings: list[str] = []
    warnings: list[str] = []

    # 1. JWT Security Audit
    is_default_secret = JWT_SECRET_KEY == "dev-secret-change-in-production"
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    if is_default_secret:
        if is_prod:
            findings.append("CRITICAL: Using default JWT_SECRET_KEY in production environment!")
        else:
            warnings.append("Using default JWT_SECRET_KEY in development environment.")

    # 2. Database URL Audit
    if not DATABASE_URL:
        findings.append("DATABASE_URL is not configured.")

    # 3. AI / LLM Audit
    if LLM_PROVIDER == "groq" and not GROQ_API_KEY:
        warnings.append("GROQ_API_KEY is not set while LLM_PROVIDER is 'groq'.")

    # 4. RAG Mode Validation
    valid_modes = {"dense", "vector", "keyword", "bm25", "graph", "hybrid"}
    if RAG_MODE not in valid_modes:
        findings.append(f"Invalid RAG_MODE: '{RAG_MODE}'. Expected one of {sorted(valid_modes)}.")

    # 5. Hybrid Weights Validation
    if HYBRID_FUSION_METHOD == "weighted":
        total_weight = HYBRID_VECTOR_WEIGHT + HYBRID_KEYWORD_WEIGHT + HYBRID_GRAPH_WEIGHT
        if abs(total_weight - 1.0) > 0.05:
            warnings.append(f"Hybrid retrieval weights do not sum close to 1.0 (sum={round(total_weight, 3)}).")

    # 6. Storage Backend Validation
    valid_backends = {"auto", "neo4j", "networkx"}
    if GRAPH_STORAGE_BACKEND not in valid_backends:
        findings.append(f"Invalid GRAPH_STORAGE_BACKEND: '{GRAPH_STORAGE_BACKEND}'. Expected one of {sorted(valid_backends)}.")

    # 7. Reranker Backend Validation
    valid_rerankers = {"semantic", "cross_encoder", "none", "passthrough"}
    if RERANKER_BACKEND not in valid_rerankers:
        findings.append(f"Invalid RERANKER_BACKEND: '{RERANKER_BACKEND}'. Expected one of {sorted(valid_rerankers)}.")

    is_valid = len(findings) == 0
    return {
        "is_valid": is_valid,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "rag_mode": RAG_MODE,
        "graph_backend": GRAPH_STORAGE_BACKEND,
        "reranker_backend": RERANKER_BACKEND,
        "reranker_enabled": RERANKER_ENABLED,
        "findings": findings,
        "warnings": warnings,
    }


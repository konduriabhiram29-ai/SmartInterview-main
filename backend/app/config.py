"""
SmartInterview — Application Configuration
Loads all settings from the project-root .env file.
"""

import os
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
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "1440"))

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

CHROMA_DB_DIR = str(PROJECT_ROOT / "chroma_db")
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


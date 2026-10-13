import sys

# Fix Windows terminal encoding for UTF-8 LLM outputs
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, resumes, interviews, users, job_descriptions
from app.routers.chat import router as chat_router, ws_router as chat_ws_router

app = FastAPI(
    title="SmartInterview API",
    description="AI-powered Technical Mock Interview Platform",
    version="8.0.0",
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register existing routers
app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(job_descriptions.router)
app.include_router(interviews.router)
app.include_router(users.router)

# Register new chat routers
app.include_router(chat_router)
app.include_router(chat_ws_router)


# ── Startup: create chat tables if they don't exist ─────────────────────────

@app.on_event("startup")
async def startup():
    """
    Create all new chat tables on startup (non-destructive).
    Existing tables are untouched.
    """
    import logging
    logger = logging.getLogger(__name__)

    from app.database import engine
    from app.models.chat import (
        ChatGroup, ChatGroupMember, ChatMessage,
        GroupInterviewShare, GroupInterviewAttempt,
    )
    from app.database import Base

    # Import all models so Base metadata is fully populated
    import app.models  # noqa: F401

    try:
        # checkfirst=True means: only create tables that don't exist
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Chat tables created/verified successfully.")
    except Exception as exc:
        logger.error("Failed to create chat tables: %s", exc)

    # Initialize Redis connection
    from app.services.redis_service import get_redis
    await get_redis()

    # Verify knowledge graph initialization (guarantees readiness before requests)
    try:
        from app.rag.graph_store import ensure_graph_initialized
        g_store = ensure_graph_initialized()
        stats = g_store.get_stats()
        logger.info(
            "Knowledge graph store ready: backend=%s, nodes=%d, edges=%d",
            stats.get("backend"),
            stats.get("total_nodes", 0),
            stats.get("total_edges", 0),
        )
    except Exception as exc:
        logger.warning("Knowledge graph store startup verification warning: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    from app.services.redis_service import close_redis
    await close_redis()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "SmartInterview API"}


@app.get("/api/knowledge-stats")
def get_knowledge_stats():
    import json
    import os
    from app.config import PROJECT_ROOT, CHROMA_DB_DIR
    import chromadb

    stats_path = os.path.join(str(PROJECT_ROOT), "data", "knowledge_stats.json")
    stats = {}
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception:
            pass

    # Inspect live collections in ChromaDB
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        collections = client.list_collections()
        col_stats = {}
        for c in collections:
            col_stats[c.name] = c.count()
        stats["chroma_live_collections"] = col_stats
    except Exception as e:
        stats["chroma_live_error"] = str(e)

    return stats

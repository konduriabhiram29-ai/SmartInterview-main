"""
SmartInterview — Retriever Factory (Phase 1)

Selects the active retrieval strategy based on the RAG_MODE environment
variable.  This is the single point of dispatch for all retrieval —
question_service.py calls get_retriever() and gets back a BaseRetriever
subclass without knowing which one.

RAG_MODE values
---------------
dense        — VectorRetriever only (DEFAULT, existing system, unchanged)
keyword      — KeywordRetriever only (available from Phase 7)
graph        — GraphRetriever only (available from Phase 6)
hybrid       — HybridRetriever combining all three (available from Phase 8)

If RAG_MODE is not set or is unrecognised, the factory logs a warning
and falls back to 'dense' to guarantee the existing system always works.

IMPORTANT: In Phase 1 only 'dense' is implemented.
           Requesting any other mode raises a clear NotImplementedError.
           This will be resolved progressively as each phase is completed.
"""

from __future__ import annotations
import logging
from typing import List, Optional, TYPE_CHECKING

from app.config import RAG_MODE
from app.rag.base_retriever import BaseRetriever

if TYPE_CHECKING:
    pass  # avoid circular imports; concrete classes are imported inside functions

logger = logging.getLogger(__name__)

# Modes that are currently implemented (grows as phases complete)
_IMPLEMENTED_MODES = {"dense", "graph", "keyword", "hybrid"}


def get_retriever(
    embedding_model=None,
    chroma_collection=None,
    build_rag_query_fn=None,
    *,
    mode: Optional[str] = None,
) -> BaseRetriever:
    """
    Return the appropriate BaseRetriever for the current RAG_MODE.

    Parameters
    ----------
    embedding_model     : SentenceTransformer singleton (required for 'dense')
    chroma_collection   : ChromaDB collection singleton (required for 'dense')
    build_rag_query_fn  : The existing build_rag_query() function from
                          generate_question.py (required for 'dense')
    mode                : Override the env-var RAG_MODE for this call only.
                          If None, reads from app.config.RAG_MODE.

    Returns
    -------
    BaseRetriever subclass appropriate for the selected mode.

    Raises
    ------
    NotImplementedError : If a mode is requested that is not yet implemented.
    """
    effective_mode = (mode or RAG_MODE or "dense").lower().strip()

    if effective_mode not in _IMPLEMENTED_MODES:
        logger.warning(
            "[RetrieverFactory] Unrecognised RAG_MODE='%s'. Falling back to 'dense'.",
            effective_mode,
        )
        effective_mode = "dense"

    if effective_mode == "dense":
        from app.rag.vector_retriever import VectorRetriever

        if embedding_model is None or chroma_collection is None or build_rag_query_fn is None:
            raise ValueError(
                "VectorRetriever requires embedding_model, chroma_collection, "
                "and build_rag_query_fn to be provided."
            )
        logger.debug("[RetrieverFactory] Creating VectorRetriever (RAG_MODE=dense)")
        return VectorRetriever(
            embedding_model=embedding_model,
            collection=chroma_collection,
            build_rag_query_fn=build_rag_query_fn,
        )

    if effective_mode == "graph":
        from app.rag.graph_retriever import GraphRetriever
        from app.rag.graph_store import get_graph_store

        logger.debug("[RetrieverFactory] Creating GraphRetriever (RAG_MODE=graph)")
        return GraphRetriever(graph_store=get_graph_store())

    if effective_mode == "keyword":
        from app.rag.keyword_retriever import KeywordRetriever

        logger.debug("[RetrieverFactory] Creating KeywordRetriever (RAG_MODE=keyword)")
        return KeywordRetriever()

    if effective_mode == "hybrid":
        from app.rag.hybrid_retriever import HybridRetriever
        from app.rag.keyword_retriever import KeywordRetriever
        from app.rag.graph_retriever import GraphRetriever
        from app.rag.graph_store import get_graph_store

        vector_retriever = None
        if embedding_model is not None and chroma_collection is not None and build_rag_query_fn is not None:
            from app.rag.vector_retriever import VectorRetriever
            vector_retriever = VectorRetriever(
                embedding_model=embedding_model,
                collection=chroma_collection,
                build_rag_query_fn=build_rag_query_fn,
            )

        keyword_retriever = KeywordRetriever()
        graph_retriever = GraphRetriever(graph_store=get_graph_store())

        logger.debug("[RetrieverFactory] Creating HybridRetriever (RAG_MODE=hybrid)")
        return HybridRetriever(
            vector_retriever=vector_retriever,
            keyword_retriever=keyword_retriever,
            graph_retriever=graph_retriever,
        )

    # This line is unreachable — kept as a safety net
    raise NotImplementedError(f"RAG_MODE='{effective_mode}' has no factory implementation.")


def get_implemented_modes() -> List[str]:
    """Return the list of currently implemented RAG modes."""
    return sorted(_IMPLEMENTED_MODES)

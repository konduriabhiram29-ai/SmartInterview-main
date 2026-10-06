"""
SmartInterview — Vector Retriever (Phase 1)

Wraps the existing ChromaDB + SentenceTransformer dense retrieval that was
previously implemented inline inside scripts/generate_question.py.

This class is a ZERO-BEHAVIOUR-CHANGE wrapper.  The existing system worked
exactly like this — this file just gives it a clean class boundary so that:
  1. question_service.py can call retriever.retrieve() instead of
     retrieve_rag_context() directly.
  2. HybridRetriever (Phase 8) can include it as one leg of fusion.
  3. Tests can verify it in isolation.

The actual retrieval logic (query construction, ChromaDB filter, embedding)
is UNCHANGED from generate_question.py's retrieve_rag_context() and
build_rag_query().  Both functions are still imported and reused here.
"""

from __future__ import annotations
import logging
from typing import List, Optional

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult

logger = logging.getLogger(__name__)


class VectorRetriever(BaseRetriever):
    """
    Dense vector retrieval using ChromaDB + all-MiniLM-L6-v2.

    This is the EXISTING RAG pipeline, unchanged in behaviour.

    It accepts the already-initialised singletons from question_service.py
    so that the embedding model and ChromaDB collection are loaded only once
    across the application lifetime.

    Parameters
    ----------
    embedding_model : SentenceTransformer instance (singleton from question_service)
    collection      : ChromaDB collection (singleton from question_service)
    build_rag_query : callable — the existing build_rag_query() from generate_question.py
    """

    def __init__(self, embedding_model, collection, build_rag_query_fn):
        self._embedding_model = embedding_model
        self._collection = collection
        self._build_rag_query = build_rag_query_fn

    def retrieve(
        self,
        query: str,
        skill: str,
        domains: Optional[List[str]] = None,
        top_k: int = 3,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Retrieve top-k chunks from ChromaDB using dense vector search.

        Uses domain-filtered search when domains are provided,
        falls back to unfiltered search otherwise.

        This is a line-for-line equivalent of the original retrieve_rag_context()
        from scripts/generate_question.py — it produces identical results.
        """
        # Allow callers to override the pre-built query
        effective_query = query or self._build_rag_query(skill, domains or [])

        try:
            query_embedding = self._embedding_model.encode(
                effective_query, convert_to_numpy=True
            ).tolist()
        except Exception as e:
            logger.error("[VectorRetriever] Embedding failed: %s", e)
            return []

        # Build ChromaDB where-filter (same logic as original)
        where_filter = None
        if domains:
            if len(domains) == 1:
                where_filter = {"domain": domains[0]}
            else:
                where_filter = {"$or": [{"domain": d} for d in domains]}

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error("[VectorRetriever] ChromaDB query failed: %s", e)
            return []

        retrieval_results: List[RetrievalResult] = []
        if results.get("ids") and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                doc = results["documents"][0][i]
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                dist = (
                    results["distances"][0][i]
                    if results.get("distances") and results["distances"][0]
                    else None
                )
                retrieval_results.append(
                    RetrievalResult.from_chroma_row(
                        chunk_id=chunk_id,
                        document=doc,
                        metadata=meta,
                        distance=dist,
                    )
                )

        logger.debug(
            "[VectorRetriever] skill=%s domains=%s top_k=%d → %d results",
            skill,
            domains,
            top_k,
            len(retrieval_results),
        )
        return retrieval_results


class SyllabusVectorRetriever(BaseRetriever):
    """
    Variant of VectorRetriever that queries a temporary syllabus collection.

    Used by generate_syllabus_question() — behaviour is identical to the
    existing inline query in question_service.py.

    Parameters
    ----------
    embedding_model : SentenceTransformer singleton
    syllabus_id     : The temp_syllabus_<id> collection identifier
    chroma_db_dir   : Path to the ChromaDB persistent directory
    """

    def __init__(self, embedding_model, syllabus_id: str, chroma_db_dir: str):
        self._embedding_model = embedding_model
        self._syllabus_id = syllabus_id
        self._chroma_db_dir = chroma_db_dir
        self._collection = None  # loaded lazily

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=self._chroma_db_dir)
            collection_name = f"temp_syllabus_{self._syllabus_id}"
            self._collection = client.get_collection(name=collection_name)
        return self._collection

    def retrieve(
        self,
        query: str,
        skill: str,
        domains: Optional[List[str]] = None,
        top_k: int = 3,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Retrieve from temporary syllabus ChromaDB collection.
        Behaviour is identical to generate_syllabus_question()'s inline retrieval.
        """
        try:
            collection = self._get_collection()
        except Exception as e:
            logger.error(
                "[SyllabusVectorRetriever] Collection not found for %s: %s",
                self._syllabus_id,
                e,
            )
            return []

        try:
            query_embedding = self._embedding_model.encode(
                query, convert_to_numpy=True
            ).tolist()
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas"],
            )
        except Exception as e:
            logger.error("[SyllabusVectorRetriever] Query failed: %s", e)
            return []

        retrieval_results: List[RetrievalResult] = []
        if results.get("ids") and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                doc = results["documents"][0][i]
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                retrieval_results.append(
                    RetrievalResult(
                        chunk_id=chunk_id,
                        text=doc,
                        domain=meta.get("domain", "Syllabus"),
                        concept=skill,
                        source=meta.get("source", ""),
                        source_url="",
                        retriever="syllabus_vector",
                        metadata=meta,
                    )
                )

        return retrieval_results

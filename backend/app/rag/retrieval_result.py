"""
SmartInterview — RAG Retrieval Result

Defines the uniform output contract shared by ALL retriever strategies
(VectorRetriever, KeywordRetriever, GraphRetriever).

Every retriever must return a list[RetrievalResult]. This allows the
HybridRetriever (Phase 8) and the reranker (Phase 9) to combine results
from multiple retrievers without knowing their internal implementation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetrievalResult:
    """
    Uniform output from any retrieval strategy.

    Fields
    ------
    chunk_id        : Unique identifier of the knowledge chunk (from ChromaDB / JSON)
    text            : Full text of the retrieved chunk
    domain          : Canonical knowledge-base domain (e.g. 'dbms', 'oop')
    concept         : Concept name within the domain (e.g. 'Normalization')
    source          : Source document name (e.g. 'wikipedia', syllabus filename)
    source_url      : URL of the source if available
    vector_score    : Cosine similarity distance from ChromaDB (lower = closer).
                      None if this result did not come from vector retrieval.
    keyword_score   : BM25 relevance score. None if not from keyword retrieval.
    graph_score     : Graph relevance score. None if not from graph retrieval.
    final_score     : Fused/weighted score used for ranking. Set by HybridRetriever.
    retriever       : Which retriever produced this result ('vector', 'keyword', 'graph')
    metadata        : Any extra metadata from the source retriever
    """
    chunk_id: str
    text: str
    domain: str
    concept: str
    source: str = ""
    source_url: str = ""
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    graph_score: Optional[float] = None
    final_score: float = 0.0
    retriever: str = "unknown"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to a plain dict for prompt building and DB storage."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "domain": self.domain,
            "concept": self.concept,
            "source": self.source,
            "source_url": self.source_url,
            "vector_score": self.vector_score,
            "keyword_score": self.keyword_score,
            "graph_score": self.graph_score,
            "final_score": self.final_score,
            "retriever": self.retriever,
        }

    @classmethod
    def from_chroma_row(
        cls,
        chunk_id: str,
        document: str,
        metadata: dict,
        distance: Optional[float] = None,
    ) -> "RetrievalResult":
        """
        Build a RetrievalResult from a raw ChromaDB query row.
        This mirrors the existing dict shape produced by retrieve_rag_context().
        """
        return cls(
            chunk_id=chunk_id,
            text=document,
            domain=metadata.get("domain", ""),
            concept=metadata.get("concept", ""),
            source=metadata.get("source", ""),
            source_url=metadata.get("source_url", ""),
            vector_score=distance,
            retriever="vector",
            metadata=metadata,
        )

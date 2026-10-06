"""
SmartInterview — Base Retriever (Abstract Contract)

All retriever implementations (VectorRetriever, KeywordRetriever,
GraphRetriever) MUST subclass BaseRetriever and implement retrieve().

This enforces a uniform interface so that:
  - question_service.py calls retrieve() without knowing the strategy
  - HybridRetriever (Phase 8) can call each independently and fuse results
  - Tests can verify any retriever against the same expected interface
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from app.rag.retrieval_result import RetrievalResult


class BaseRetriever(ABC):
    """
    Abstract base class for all SmartInterview retrieval strategies.

    Subclasses
    ----------
    VectorRetriever   — dense ChromaDB retrieval (Phase 1, existing system)
    KeywordRetriever  — BM25 keyword search (Phase 7)
    GraphRetriever    — Neo4j knowledge graph traversal (Phase 6)
    """

    @abstractmethod
    def retrieve(
        self,
        query: str,
        skill: str,
        domains: Optional[List[str]] = None,
        top_k: int = 3,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant knowledge chunks for a given query and skill.

        Parameters
        ----------
        query   : The semantic query string (already constructed by the caller)
        skill   : The resume skill being questioned (e.g. 'Python', 'SQL')
        domains : Optional list of canonical KB domains to filter by
                  (e.g. ['dbms', 'oop']).  None = no filter.
        top_k   : Maximum number of results to return
        **kwargs: Extra strategy-specific parameters (e.g. syllabus_id for vector)

        Returns
        -------
        List[RetrievalResult] — ordered by relevance (best first)
        """

    @property
    def name(self) -> str:
        """Human-readable retriever name for logging and metadata."""
        return self.__class__.__name__

    def __repr__(self) -> str:
        return f"<{self.name}>"

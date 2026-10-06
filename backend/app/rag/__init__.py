"""
SmartInterview — RAG Package

This package contains all retrieval strategy implementations for the
Hybrid Graph RAG system.

Retriever hierarchy:
    BaseRetriever  (abstract contract)
     ├── VectorRetriever   (existing ChromaDB dense retrieval — DEFAULT)
     ├── KeywordRetriever  (BM25 — Phase 7)
     └── GraphRetriever    (Neo4j knowledge graph — Phase 6)

The retriever_factory module selects the active strategy based on
the RAG_MODE environment variable.
"""

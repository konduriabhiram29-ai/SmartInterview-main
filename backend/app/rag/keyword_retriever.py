"""
SmartInterview — Keyword Retriever (Phase 7)

Implements BM25Okapi keyword retrieval over the canonical SmartInterview knowledge base:
  1. Searches the same 402 knowledge chunks used by Dense Vector and Graph RAG.
  2. Preserves domain-filtered retrieval when domains parameter is specified.
  3. Computes BM25 relevance scores and extracts matched search terms.
  4. Returns uniform List[RetrievalResult] with keyword_score, matched_terms, and provenance.
"""

from __future__ import annotations

import re
import os
import json
import logging
from typing import List, Optional, Dict, Set, Tuple, Any

from rank_bm25 import BM25Okapi

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.graph_builder import _processed_dir, _output_path

logger = logging.getLogger(__name__)


def _tokenize_text(text: str) -> List[str]:
    """
    Tokenize text into lower-case terms while splitting snake_case and kebab-case.
    Preserves technical programming terms and acronyms (e.g. 'b+', 'c++').
    """
    if not text or not isinstance(text, str):
        return []
    cleaned = text.lower().replace("-", " ").replace("_", " ").replace("/", " ")
    raw_tokens = re.findall(r"[a-z0-9][a-z0-9+#]*", cleaned)
    tokens: List[str] = []
    for t in raw_tokens:
        tokens.append(t)
        if "+" in t or "#" in t:
            stripped = re.sub(r"[+#]", "", t)
            if stripped:
                tokens.append(stripped)
    return tokens


class KeywordRetriever(BaseRetriever):
    """
    BM25-based keyword retriever over the technical knowledge chunks.
    """

    def __init__(self, chunks: Optional[List[dict]] = None):
        self._chunks: List[dict] = []
        self._chunk_by_id: Dict[str, dict] = {}
        self._domain_chunk_indices: Dict[str, List[int]] = {}
        self._bm25_global: Optional[BM25Okapi] = None
        self._tokenized_corpus: List[List[str]] = []

        if chunks is not None:
            self._load_chunks_data(chunks)
        else:
            self._load_from_storage()

    def _load_chunks_data(self, chunks: List[dict]) -> None:
        """Load and index an explicit list of chunk dicts."""
        self._chunks = chunks
        self._chunk_by_id = {c["id"]: c for c in chunks}
        self._domain_chunk_indices = {}
        self._tokenized_corpus = []

        for idx, chunk in enumerate(self._chunks):
            did = chunk.get("domain", chunk.get("domain_id", ""))
            self._domain_chunk_indices.setdefault(did, []).append(idx)
            text = chunk.get("text", "")
            tokens = _tokenize_text(text)
            self._tokenized_corpus.append(tokens)

        if self._tokenized_corpus:
            self._bm25_global = BM25Okapi(self._tokenized_corpus)
            logger.info("[KeywordRetriever] Indexed %d knowledge chunks.", len(self._chunks))

    def _load_from_storage(self) -> None:
        """Load full canonical chunks using CanonicalChunkResolver."""
        from app.rag.canonical_resolver import get_canonical_resolver
        resolver = get_canonical_resolver()
        canonical_chunks = resolver.get_all_chunks()
        if canonical_chunks:
            chunk_nodes = [
                {
                    "id": c.chunk_id,
                    "domain": c.domain,
                    "concept": c.concept,
                    "text": c.text,
                    "source": c.source,
                    "source_url": c.source_url,
                }
                for c in canonical_chunks
            ]
            self._load_chunks_data(chunk_nodes)
            return

        # Fallback to data/processed if resolver had no items
        proc_dir = _processed_dir()
        loaded = []
        if os.path.isdir(proc_dir):
            import glob
            for fpath in glob.glob(os.path.join(proc_dir, "**", "*_chunks.json"), recursive=True):
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        raw_list = json.load(fp)
                    for item in raw_list:
                        loaded.append({
                            "id": item.get("chunk_id", ""),
                            "domain": item.get("domain", ""),
                            "concept": item.get("concept", ""),
                            "text": item.get("text", ""),
                            "source": item.get("source", "knowledge_base"),
                            "source_url": item.get("source_url", ""),
                        })
                except Exception as e:
                    logger.debug("Failed reading %s: %s", fpath, e)

        self._load_chunks_data(loaded)

    def retrieve(
        self,
        query: str,
        skill: str,
        domains: Optional[List[str]] = None,
        top_k: int = 3,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Execute BM25 keyword retrieval.

        Parameters
        ----------
        query   : Search query text
        skill   : Skill context (e.g. 'Python', 'SQL')
        domains : List of domain strings to filter by (e.g. ['dbms'])
        top_k   : Number of chunks to retrieve
        """
        import time
        start_time = time.perf_counter()

        if query is None or not isinstance(query, str) or not query.strip():
            logger.debug("[KeywordRetriever] Empty or non-string query; returning empty.")
            return []

        if top_k <= 0:
            return []

        if not self._bm25_global or not self._chunks:
            logger.warning("[KeywordRetriever] Empty corpus or index; returning empty.")
            return []

        query_tokens = _tokenize_text(query)
        if not query_tokens:
            return []

        # Determine target chunk indices based on domain filter (case-insensitive & stripped)
        if domains:
            allowed_indices = set()
            for did in domains:
                if isinstance(did, str):
                    allowed_indices.update(self._domain_chunk_indices.get(did.lower().strip(), []))
        else:
            allowed_indices = set(range(len(self._chunks)))

        if not allowed_indices:
            return []

        # Compute raw BM25 scores
        raw_scores = self._bm25_global.get_scores(query_tokens)

        # Filter and rank
        scored_candidates: List[Tuple[float, int, List[str]]] = []
        query_token_set = set(query_tokens)

        for idx in allowed_indices:
            score = float(raw_scores[idx])
            if score > 0.0:
                chunk_tokens_set = set(self._tokenized_corpus[idx])
                matched = sorted(list(query_token_set.intersection(chunk_tokens_set)))
                scored_candidates.append((score, idx, matched))

        # Sort descending by BM25 score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Normalize scores: min-max normalization against maximum score
        max_score = scored_candidates[0][0] if scored_candidates else 1.0
        if max_score <= 0.0:
            max_score = 1.0

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        self._last_latency_ms = elapsed_ms

        results: List[RetrievalResult] = []
        seen_chunk_ids: Set[str] = set()

        for raw_score, idx, matched_terms in scored_candidates:
            chunk = self._chunks[idx]
            cid = chunk["id"]
            if cid in seen_chunk_ids:
                continue
            seen_chunk_ids.add(cid)

            norm_score = round(raw_score / max_score, 4)

            res = RetrievalResult(
                chunk_id=cid,
                text=chunk.get("text", ""),
                domain=chunk.get("domain", ""),
                concept=chunk.get("concept", ""),
                source=chunk.get("source", "knowledge_base"),
                source_url=chunk.get("source_url", ""),
                vector_score=None,
                keyword_score=norm_score,
                graph_score=None,
                final_score=norm_score,
                retriever="keyword",
                metadata={
                    "bm25_raw_score": round(raw_score, 4),
                    "matched_terms": matched_terms,
                    "matched_term_count": len(matched_terms),
                    "latency_ms": elapsed_ms,
                    "is_full_text": True,
                    "canonical_resolved": True,
                    "char_count": len(chunk.get("text", "")),
                },
            )
            results.append(res)
            if len(results) >= top_k:
                break

        return results

    def get_stats(self) -> dict:
        """Return index statistics."""
        return {
            "total_chunks": len(self._chunks),
            "domains_indexed": sorted(list(self._domain_chunk_indices.keys())),
            "vocab_terms": len(self._bm25_global.idf) if self._bm25_global else 0,
            "last_latency_ms": getattr(self, "_last_latency_ms", None),
        }

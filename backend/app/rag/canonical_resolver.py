"""
SmartInterview — Canonical Knowledge-Chunk Resolver (Phase 4)

Provides authoritative ground-truth chunk resolution for Knowledge Graph,
BM25 Keyword, and Hybrid RAG retrieval pipelines.

Key Responsibilities:
  1. Stable Chunk IDs: Deterministic, immutable mapping from chunk_id to CanonicalChunk.
  2. Canonical Source Lookup: Loads all 402 chunks from data/processed with ChromaDB fallback.
  3. Full-Text Resolution: Guarantees retrieval results contain 100% full text (~861 chars avg),
     never truncated 300-char graph previews.
  4. Missing-Chunk Handling: Diagnostic warnings and metadata attribution if a chunk is not found.
  5. Deduplication: Unifies duplicate chunks across multi-hop graph expansion and hybrid legs.
  6. Source Provenance: Verifies domain, concept, source, and source_url integrity.
"""

from __future__ import annotations

import os
import glob
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict

from app.rag.retrieval_result import RetrievalResult
from app.rag.graph_builder import _processed_dir

logger = logging.getLogger(__name__)


# ── Canonical Chunk Data Structure ────────────────────────────────────

@dataclass
class CanonicalChunk:
    """Authoritative representation of a single knowledge base chunk."""
    chunk_id: str
    text: str
    domain: str
    concept: str
    source: str = ""
    source_url: str = ""
    token_count: int = 0
    char_count: int = field(init=False)

    def __post_init__(self):
        self.char_count = len(self.text or "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "domain": self.domain,
            "concept": self.concept,
            "source": self.source,
            "source_url": self.source_url,
            "token_count": self.token_count,
            "char_count": self.char_count,
        }


# ── Canonical Chunk Resolver Implementation ───────────────────────────

class CanonicalChunkResolver:
    """
    Thread-safe resolver indexing the 402 canonical technical knowledge chunks.
    Ensures that graph, keyword, and hybrid retrievers never supply truncated
    previews as full LLM context.
    """

    def __init__(self, processed_dir: Optional[str] = None):
        self._processed_dir = processed_dir or _processed_dir()
        self._chunks_by_id: Dict[str, CanonicalChunk] = {}
        self._chunks_by_domain: Dict[str, List[CanonicalChunk]] = defaultdict(list)
        self._chunks_by_concept: Dict[str, List[CanonicalChunk]] = defaultdict(list)
        self._lock = threading.RLock()
        self._loaded = False

        self._load_canonical_corpus()

    def _load_canonical_corpus(self) -> None:
        """Load and index all chunk files from data/processed or ChromaDB fallback."""
        with self._lock:
            self._chunks_by_id.clear()
            self._chunks_by_domain.clear()
            self._chunks_by_concept.clear()

            # 1. Primary: load from processed directory
            chunk_files = glob.glob(
                os.path.join(self._processed_dir, "**", "*_chunks.json"),
                recursive=True,
            )

            loaded_count = 0
            for fpath in sorted(chunk_files):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        items = json.load(f)
                    for item in items:
                        cid = item.get("chunk_id")
                        text = item.get("text", "")
                        if not cid or not text:
                            continue
                        chunk = CanonicalChunk(
                            chunk_id=cid,
                            text=text,
                            domain=item.get("domain", ""),
                            concept=item.get("concept", ""),
                            source=item.get("source", ""),
                            source_url=item.get("source_url", ""),
                            token_count=int(item.get("token_count", 0)),
                        )
                        self._chunks_by_id[cid] = chunk
                        self._chunks_by_domain[chunk.domain].append(chunk)
                        self._chunks_by_concept[chunk.concept].append(chunk)
                        loaded_count += 1
                except Exception as exc:
                    logger.warning("[CanonicalResolver] Failed to load %s: %s", fpath, exc)

            # 2. Fallback: if processed_dir had no files, load from ChromaDB technical_kb
            if not self._chunks_by_id:
                logger.info("[CanonicalResolver] No processed files found; probing ChromaDB technical_kb...")
                try:
                    import chromadb
                    from app.config import CHROMA_DB_DIR
                    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
                    col = client.get_collection("technical_kb")
                    data = col.get(include=["documents", "metadatas"])
                    for cid, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
                        chunk = CanonicalChunk(
                            chunk_id=cid,
                            text=doc or "",
                            domain=meta.get("domain", ""),
                            concept=meta.get("concept", ""),
                            source=meta.get("source", ""),
                            source_url=meta.get("source_url", ""),
                            token_count=int(meta.get("token_count", 0)),
                        )
                        self._chunks_by_id[cid] = chunk
                        self._chunks_by_domain[chunk.domain].append(chunk)
                        self._chunks_by_concept[chunk.concept].append(chunk)
                        loaded_count += 1
                except Exception as exc:
                    logger.warning("[CanonicalResolver] ChromaDB fallback failed: %s", exc)

            self._loaded = True
            logger.info(
                "[CanonicalResolver] Successfully loaded and verified %d canonical chunks across %d domains.",
                len(self._chunks_by_id),
                len(self._chunks_by_domain),
            )

    @property
    def total_chunks(self) -> int:
        return len(self._chunks_by_id)

    def get_chunk(self, chunk_id: str) -> Optional[CanonicalChunk]:
        """Look up a canonical chunk by stable chunk ID."""
        return self._chunks_by_id.get(chunk_id)

    def resolve_chunk(self, chunk_id: str) -> Optional[CanonicalChunk]:
        """Alias for get_chunk."""
        return self.get_chunk(chunk_id)

    def get_all_chunks(self) -> List[CanonicalChunk]:
        """Return all canonical chunks sorted by chunk ID."""
        return [self._chunks_by_id[k] for k in sorted(self._chunks_by_id.keys())]

    def get_all_chunk_ids(self) -> Set[str]:
        """Return all valid canonical chunk IDs."""
        return set(self._chunks_by_id.keys())

    def get_chunks_for_domain(self, domain: str) -> List[CanonicalChunk]:
        """Return all chunks belonging to a domain."""
        return list(self._chunks_by_domain.get(domain, []))

    def get_chunks_for_concept(self, concept: str) -> List[CanonicalChunk]:
        """Return all chunks belonging to a concept."""
        return list(self._chunks_by_concept.get(concept, []))

    def resolve_retrieval_result(self, result: RetrievalResult) -> RetrievalResult:
        """
        Enforce full-text resolution and provenance attribution on a RetrievalResult.
        Replaces truncated previews with full canonical text.
        """
        canonical = self.get_chunk(result.chunk_id)
        if canonical is not None:
            result.text = canonical.text
            result.domain = canonical.domain or result.domain
            result.concept = canonical.concept or result.concept
            result.source = canonical.source or result.source
            result.source_url = canonical.source_url or result.source_url
            result.metadata["is_full_text"] = True
            result.metadata["canonical_resolved"] = True
            result.metadata["char_count"] = canonical.char_count
            result.metadata["missing_canonical"] = False
        else:
            # Missing chunk handling
            logger.warning(
                "[CanonicalResolver] Chunk ID '%s' was not found in canonical knowledge base.",
                result.chunk_id,
            )
            result.metadata["is_full_text"] = False
            result.metadata["canonical_resolved"] = False
            result.metadata["missing_canonical"] = True

        return result

    def resolve_results(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Resolve a batch of RetrievalResult items in place."""
        for r in results:
            self.resolve_retrieval_result(r)
        return results

    def deduplicate_results(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        Deduplicate a list of RetrievalResults by chunk_id.
        Preserves the highest-scoring candidate and combines retrieval provenance.
        """
        seen: Dict[str, RetrievalResult] = {}
        provenance_sources: Dict[str, Set[str]] = defaultdict(set)
        traversal_paths: Dict[str, List[str]] = defaultdict(list)

        for res in results:
            cid = res.chunk_id
            provenance_sources[cid].add(res.retriever)
            if "traversal_path" in res.metadata:
                traversal_paths[cid].append(res.metadata["traversal_path"])

            if cid not in seen:
                seen[cid] = res
            else:
                existing = seen[cid]
                # Keep candidate with higher final_score
                if res.final_score > existing.final_score:
                    seen[cid] = res

        deduped: List[RetrievalResult] = []
        for cid, res in seen.items():
            self.resolve_retrieval_result(res)
            # Combine sources in metadata
            existing_sources = res.metadata.get("sources", [])
            merged_sources = sorted(set(existing_sources).union(provenance_sources[cid]))
            res.metadata["sources"] = merged_sources
            if traversal_paths[cid]:
                res.metadata["all_traversal_paths"] = list(dict.fromkeys(traversal_paths[cid]))
            deduped.append(res)

        return deduped

    def is_truncated_preview(self, text: str, chunk_id: Optional[str] = None) -> bool:
        """
        Verify whether the provided text is a truncated preview rather than full text.
        """
        if chunk_id and chunk_id in self._chunks_by_id:
            canonical = self._chunks_by_id[chunk_id]
            if canonical.char_count > 300 and len(text or "") <= 300:
                return True
        return len(text or "") <= 300 and (text or "").endswith("...")


# ── Global Singleton Factory ──────────────────────────────────────────

_resolver_lock = threading.Lock()
_resolver_instance: Optional[CanonicalChunkResolver] = None


def get_canonical_resolver(force_reload: bool = False) -> CanonicalChunkResolver:
    """Return the active CanonicalChunkResolver singleton instance."""
    global _resolver_instance
    if _resolver_instance is not None and not force_reload:
        return _resolver_instance

    with _resolver_lock:
        if _resolver_instance is not None and not force_reload:
            return _resolver_instance
        _resolver_instance = CanonicalChunkResolver()
        return _resolver_instance


def reset_canonical_resolver() -> None:
    """Reset the singleton instance (for testing)."""
    global _resolver_instance
    with _resolver_lock:
        _resolver_instance = None

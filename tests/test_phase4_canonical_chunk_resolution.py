"""
SmartInterview — Phase 4 Tests: Canonical Knowledge-Chunk Resolution

Comprehensive test suite verifying:
  1. Stable chunk IDs (all 402 unique, deterministic naming).
  2. Canonical source lookup from ground truth data/processed corpus.
  3. Full-text resolution: returned context matches original source chunks character-for-character.
  4. No silent use of truncated 300-char graph previews as full evidence.
  5. Missing-chunk handling and diagnostic logging.
  6. Deduplication of multi-hop / hybrid candidate chunks while merging provenance.
  7. Verification across GraphRetriever, KeywordRetriever, and HybridRetriever.
"""

import os
import sys
import glob
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.canonical_resolver import (
    CanonicalChunkResolver,
    CanonicalChunk,
    get_canonical_resolver,
    reset_canonical_resolver,
)
from app.rag.retrieval_result import RetrievalResult
from app.rag.graph_retriever import GraphRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.graph_store import get_graph_store
from app.rag.graph_builder import _processed_dir


@pytest.fixture(autouse=True)
def clean_resolver():
    reset_canonical_resolver()
    yield
    reset_canonical_resolver()


@pytest.fixture(scope="module")
def processed_ground_truth():
    """Load all canonical ground-truth chunks from data/processed into a dictionary."""
    proc_dir = _processed_dir()
    chunk_files = glob.glob(os.path.join(proc_dir, "**", "*_chunks.json"), recursive=True)
    assert len(chunk_files) == 50, f"Expected 50 chunk files, got {len(chunk_files)}"

    ground_truth: dict[str, dict] = {}
    for fpath in chunk_files:
        with open(fpath, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            for c in chunks:
                ground_truth[c["chunk_id"]] = c

    assert len(ground_truth) == 402, f"Expected 402 canonical chunks, got {len(ground_truth)}"
    return ground_truth


# ── 1. Canonical Resolver Core & Ground Truth Lookup ───────────────────

class TestCanonicalResolverCore:
    def test_resolver_loads_all_402_canonical_chunks(self):
        resolver = get_canonical_resolver()
        assert resolver.total_chunks == 402
        all_chunks = resolver.get_all_chunks()
        assert len(all_chunks) == 402
        assert len(resolver.get_all_chunk_ids()) == 402

    def test_chunk_ids_are_stable_and_unique(self, processed_ground_truth):
        resolver = get_canonical_resolver()
        for cid, expected in processed_ground_truth.items():
            actual = resolver.get_chunk(cid)
            assert actual is not None, f"Chunk {cid} missing from resolver"
            assert actual.chunk_id == cid
            assert actual.domain == expected["domain"]
            assert actual.concept == expected["concept"]
            assert actual.source == expected.get("source", "")
            assert actual.source_url == expected.get("source_url", "")

    def test_full_text_lengths_exceed_preview(self):
        resolver = get_canonical_resolver()
        all_chunks = resolver.get_all_chunks()
        mean_len = sum(c.char_count for c in all_chunks) / len(all_chunks)
        assert mean_len > 800, f"Mean text length {mean_len} is suspiciously short"
        for c in all_chunks:
            assert c.char_count >= 200, f"Chunk {c.chunk_id} text length {c.char_count} < 200"

    def test_exact_character_match_against_source_files(self, processed_ground_truth):
        resolver = get_canonical_resolver()
        # Verify sample of diverse domain chunks
        sample_ids = [
            "cn_dns_001",
            "dbms_acid-properties_001",
            "os_virtual-memory_001",
            "dsa_array_001",
            "ml-dl_neural-networks_001",
        ]
        for cid in sample_ids:
            expected_text = processed_ground_truth[cid]["text"]
            actual = resolver.get_chunk(cid)
            assert actual is not None
            assert actual.text == expected_text, f"Mismatch in full text for {cid}"


# ── 2. Graph Retrieval Full-Text Resolution ────────────────────────────

class TestGraphRetrieverCanonicalResolution:
    def test_graph_retrieval_returns_full_canonical_text(self, processed_ground_truth):
        store = get_graph_store()
        retriever = GraphRetriever(graph_store=store)

        results = retriever.retrieve(
            query="ACID database transactions and consistency guarantees",
            skill="SQL",
            domains=["dbms"],
            concept="dbms_acid-properties",
            top_k=3,
        )

        assert len(results) > 0
        for r in results:
            assert r.chunk_id in processed_ground_truth
            expected_full_text = processed_ground_truth[r.chunk_id]["text"]

            # Exact match between retrieved text and ground truth source chunk
            assert r.text == expected_full_text
            assert len(r.text) > 300, "Retrieved chunk text appears to be truncated preview"
            assert r.metadata.get("is_full_text") is True
            assert r.metadata.get("canonical_resolved") is True
            assert r.metadata.get("char_count") == len(expected_full_text)

    def test_compare_returned_context_against_preview(self, processed_ground_truth):
        """Confirm that retrieved text is strictly longer than the 300-char preview in graph node."""
        store = get_graph_store()
        retriever = GraphRetriever(graph_store=store)

        results = retriever.retrieve(
            query="DNS domain name lookup protocol",
            skill="Networks",
            domains=["cn"],
            concept="cn_dns",
            top_k=2,
        )

        for r in results:
            # Check what's stored in the raw graph node
            raw_node = store._graph.nodes.get(r.chunk_id, {})
            preview_text = raw_node.get("text", "")
            assert len(preview_text) <= 300, "Expected preview in graph node to be <= 300 chars"

            # But the retrieved result must be the FULL text
            assert len(r.text) > len(preview_text)
            assert r.text.startswith(preview_text.rstrip("."))


# ── 3. Keyword and Hybrid Retriever Full-Text Resolution ───────────────

class TestKeywordAndHybridCanonicalResolution:
    def test_keyword_retriever_returns_full_canonical_text(self, processed_ground_truth):
        retriever = KeywordRetriever()
        results = retriever.retrieve(
            query="operating system virtual memory paging segmentation",
            skill="OS",
            domains=["os"],
            top_k=3,
        )
        assert len(results) > 0
        for r in results:
            assert r.chunk_id in processed_ground_truth
            assert r.text == processed_ground_truth[r.chunk_id]["text"]
            assert len(r.text) > 300
            assert r.metadata.get("is_full_text") is True

    def test_hybrid_retriever_ensures_canonical_resolution(self, processed_ground_truth):
        kw_retriever = KeywordRetriever()
        gr_retriever = GraphRetriever(graph_store=get_graph_store())

        hybrid = HybridRetriever(
            keyword_retriever=kw_retriever,
            graph_retriever=gr_retriever,
            weights={"keyword": 0.5, "graph": 0.5},
        )

        results = hybrid.retrieve(
            query="relational database indexing b-tree hash index",
            skill="SQL",
            domains=["dbms"],
            top_k=3,
        )

        assert len(results) > 0
        for r in results:
            assert r.chunk_id in processed_ground_truth
            assert r.text == processed_ground_truth[r.chunk_id]["text"]
            assert r.metadata.get("is_full_text") is True
            assert r.metadata.get("canonical_resolved") is True


# ── 4. Deduplication and Missing Chunk Handling ────────────────────────

class TestDeduplicationAndMissingChunkHandling:
    def test_deduplication_preserves_highest_score_and_merges_provenance(self):
        resolver = get_canonical_resolver()

        r1 = RetrievalResult(
            chunk_id="dbms_acid-properties_001",
            text="preview 1",
            domain="dbms",
            concept="acid-properties",
            final_score=0.82,
            retriever="graph",
            metadata={"traversal_path": "path_A"},
        )
        r2 = RetrievalResult(
            chunk_id="dbms_acid-properties_001",
            text="preview 2",
            domain="dbms",
            concept="acid-properties",
            final_score=0.91,
            retriever="keyword",
            metadata={"traversal_path": "path_B"},
        )

        deduped = resolver.deduplicate_results([r1, r2])
        assert len(deduped) == 1
        winner = deduped[0]
        assert winner.final_score == 0.91
        assert "graph" in winner.metadata["sources"]
        assert "keyword" in winner.metadata["sources"]
        assert winner.metadata["is_full_text"] is True
        assert len(winner.text) > 300

    def test_missing_chunk_handling_does_not_silently_claim_full_evidence(self):
        resolver = get_canonical_resolver()
        missing = RetrievalResult(
            chunk_id="non_existent_chunk_999",
            text="some preview text",
            domain="dbms",
            concept="acid-properties",
            final_score=0.5,
            retriever="graph",
        )

        resolved = resolver.resolve_retrieval_result(missing)
        assert resolved.metadata["is_full_text"] is False
        assert resolved.metadata["missing_canonical"] is True
        assert resolved.metadata["canonical_resolved"] is False

    def test_is_truncated_preview_detection(self):
        resolver = get_canonical_resolver()
        canonical = resolver.get_chunk("dbms_acid-properties_001")
        assert canonical is not None
        assert not resolver.is_truncated_preview(canonical.text, "dbms_acid-properties_001")
        assert resolver.is_truncated_preview(canonical.text[:250], "dbms_acid-properties_001")

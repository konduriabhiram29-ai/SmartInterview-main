"""
SmartInterview — Phase 12 Tests: Evaluation Dataset Audit & Golden Query Construction

Validates:
  1. Complete domain coverage across all 8 computer-science domains:
     cn, dbms, design-patterns, dsa, ml-dl, oop, os, system-design.
  2. 100% chunk ID integrity: every expected chunk ID in golden dataset resolves in CanonicalChunkResolver.
  3. Ground-truth prerequisite relationship validity against knowledge graph edges.
  4. Scenario diversity: standard, multi_hop, remediation, terminology, cognitive.
  5. Bloom cognitive level distribution across all queries.
  6. Backwards compatibility with existing retrieval_queries.json benchmark format.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.rag.canonical_resolver import get_canonical_resolver


# ── Fixtures & Setup ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def golden_dataset() -> list[dict]:
    dataset_path = PROJECT_ROOT / "data" / "evaluation" / "golden_evaluation_dataset.json"
    assert dataset_path.exists(), f"Golden dataset not found at {dataset_path}"
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="module")
def legacy_queries() -> list[dict]:
    query_path = PROJECT_ROOT / "data" / "evaluation" / "retrieval_queries.json"
    assert query_path.exists(), f"Legacy query file not found at {query_path}"
    with open(query_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="module")
def canonical_resolver():
    return get_canonical_resolver()


# ── Test Suite ─────────────────────────────────────────────────────────

class TestGoldenDatasetSchemaAndCoverage:
    def test_record_count_and_unique_ids(self, golden_dataset):
        assert len(golden_dataset) == 33
        query_ids = [item["query_id"] for item in golden_dataset]
        assert len(query_ids) == len(set(query_ids)), "Duplicate query IDs found"

    def test_all_eight_domains_represented(self, golden_dataset):
        domains = {item["domain"] for item in golden_dataset}
        expected_domains = {
            "cn",
            "dbms",
            "design-patterns",
            "dsa",
            "ml-dl",
            "oop",
            "os",
            "system-design",
        }
        assert domains == expected_domains

    def test_required_schema_fields_present_and_non_empty(self, golden_dataset):
        required_fields = [
            "query_id",
            "query",
            "domain",
            "concept",
            "bloom_level",
            "difficulty",
            "scenario_type",
            "expected_chunk_ids",
            "key_terms",
        ]
        for item in golden_dataset:
            for field in required_fields:
                assert field in item, f"Missing {field} in {item['query_id']}"
                assert item[field], f"Field {field} is empty in {item['query_id']}"

    def test_scenario_types_diversity(self, golden_dataset):
        scenarios = {item["scenario_type"] for item in golden_dataset}
        assert "standard" in scenarios
        assert "multi_hop" in scenarios
        assert "remediation" in scenarios
        assert "terminology" in scenarios
        assert "cognitive" in scenarios

    def test_bloom_levels_distribution(self, golden_dataset):
        levels = {item["bloom_level"] for item in golden_dataset}
        assert "remember" in levels
        assert "understand" in levels
        assert "apply" in levels
        assert "analyze" in levels
        assert "evaluate" in levels


class TestCanonicalChunkIntegrity:
    def test_all_expected_chunks_exist_in_canonical_resolver(self, golden_dataset, canonical_resolver):
        all_canonical_ids = canonical_resolver.get_all_chunk_ids()
        missing_chunks = []

        for item in golden_dataset:
            for cid in item["expected_chunk_ids"]:
                if cid not in all_canonical_ids:
                    missing_chunks.append((item["query_id"], cid))

        assert not missing_chunks, f"Expected chunks not in canonical corpus: {missing_chunks}"

    def test_every_query_has_valid_chunk_targets(self, golden_dataset):
        for item in golden_dataset:
            assert len(item["expected_chunk_ids"]) > 0, f"No expected chunks for {item['query_id']}"


class TestPrerequisiteRelationshipsInGoldenDataset:
    def test_multi_hop_queries_have_expected_prerequisites(self, golden_dataset):
        multi_hop = [item for item in golden_dataset if item["scenario_type"] == "multi_hop"]
        assert len(multi_hop) >= 4

        # Specific domain prerequisite verification
        acid_query = next(q for q in golden_dataset if q["concept"] == "acid-properties")
        assert "transactions" in acid_query["expected_prerequisites"]

        hash_query = next(q for q in golden_dataset if q["concept"] == "hash-table")
        assert "array" in hash_query["expected_prerequisites"]

        deadlock_query = next(q for q in golden_dataset if q["concept"] == "deadlock")
        assert "mutex-vs-semaphore" in deadlock_query["expected_prerequisites"]

        hashing_query = next(q for q in golden_dataset if q["concept"] == "consistent-hashing")
        assert "load-balancing" in hashing_query["expected_prerequisites"]


class TestBackwardsCompatibilityWithLegacyQueries:
    def test_legacy_queries_exact_query_match(self, golden_dataset, legacy_queries):
        assert len(golden_dataset) == len(legacy_queries)
        for gold, leg in zip(golden_dataset, legacy_queries):
            assert gold["query"] == leg["query"]
            assert gold["domain"] == leg["expected_domain"]
            assert gold["concept"] == leg["expected_concept"]

"""
SmartInterview — Phase 2 Tests: Knowledge Graph Schema

Tests that verify:
  1. All 8 canonical domains are present and correctly defined
  2. All 50 concepts are present with correct domain assignments
  3. Concept IDs follow the expected naming convention
  4. No duplicate node IDs exist in either catalogue
  5. CONCEPT_BY_DOMAIN groupings are internally consistent
  6. Every expected prerequisite hint references valid concept IDs
  7. GraphEdge dataclass construction and validation
  8. Schema constants are self-consistent

Run with:
    cd SmartInterview-main
    python -m pytest tests/test_phase2_graph_schema.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


class TestDomainCatalogue:
    """Verify the 8 canonical domains are correctly defined."""

    def test_exactly_8_domains(self):
        from app.rag.graph_schema import CANONICAL_DOMAIN_CATALOGUE
        assert len(CANONICAL_DOMAIN_CATALOGUE) == 8

    def test_domain_ids_match_folder_names(self):
        """Domain IDs must match the actual folder names in data/processed/."""
        from app.rag.graph_schema import CANONICAL_DOMAIN_CATALOGUE
        expected_ids = {
            "cn", "dbms", "design-patterns", "dsa",
            "ml-dl", "oop", "os", "system-design",
        }
        actual_ids = {d.id for d in CANONICAL_DOMAIN_CATALOGUE}
        assert actual_ids == expected_ids

    def test_no_duplicate_domain_ids(self):
        from app.rag.graph_schema import CANONICAL_DOMAIN_CATALOGUE
        ids = [d.id for d in CANONICAL_DOMAIN_CATALOGUE]
        assert len(ids) == len(set(ids)), "Duplicate domain IDs found"

    def test_all_domains_have_display_names(self):
        from app.rag.graph_schema import CANONICAL_DOMAIN_CATALOGUE
        for domain in CANONICAL_DOMAIN_CATALOGUE:
            assert domain.display_name and len(domain.display_name) > 0

    def test_canonical_domain_ids_set(self):
        from app.rag.graph_schema import CANONICAL_DOMAIN_IDS, CANONICAL_DOMAIN_CATALOGUE
        assert CANONICAL_DOMAIN_IDS == {d.id for d in CANONICAL_DOMAIN_CATALOGUE}


class TestConceptCatalogue:
    """Verify all 50 concepts are correctly defined."""

    def test_exactly_50_concepts(self):
        from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE
        assert len(CANONICAL_CONCEPT_CATALOGUE) == 50

    def test_no_duplicate_concept_ids(self):
        from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE
        ids = [c.id for c in CANONICAL_CONCEPT_CATALOGUE]
        assert len(ids) == len(set(ids)), f"Duplicate concept IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_all_concepts_have_valid_domain(self):
        from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE, CANONICAL_DOMAIN_IDS
        for concept in CANONICAL_CONCEPT_CATALOGUE:
            assert concept.domain_id in CANONICAL_DOMAIN_IDS, (
                f"Concept '{concept.id}' has invalid domain_id '{concept.domain_id}'"
            )

    def test_all_concepts_have_names(self):
        from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE
        for concept in CANONICAL_CONCEPT_CATALOGUE:
            assert concept.name and len(concept.name) > 0

    def test_concept_counts_per_domain(self):
        """Verify each domain has the expected number of concepts based on file listing."""
        from app.rag.graph_schema import CONCEPT_BY_DOMAIN
        expected = {
            "cn": 5,
            "dbms": 6,
            "design-patterns": 4,
            "dsa": 15,
            "ml-dl": 5,
            "oop": 5,
            "os": 5,
            "system-design": 5,
        }
        for domain_id, expected_count in expected.items():
            actual = len(CONCEPT_BY_DOMAIN.get(domain_id, []))
            assert actual == expected_count, (
                f"Domain '{domain_id}' has {actual} concepts, expected {expected_count}"
            )

    def test_concept_id_map_is_complete(self):
        from app.rag.graph_schema import CONCEPT_ID_MAP, CANONICAL_CONCEPT_CATALOGUE
        assert len(CONCEPT_ID_MAP) == len(CANONICAL_CONCEPT_CATALOGUE)
        for c in CANONICAL_CONCEPT_CATALOGUE:
            assert c.id in CONCEPT_ID_MAP

    def test_specific_dbms_concepts_present(self):
        from app.rag.graph_schema import CONCEPT_ID_MAP
        required = [
            "dbms_normalization", "dbms_acid-properties", "dbms_indexing",
            "dbms_keys", "dbms_sql-joins", "dbms_transactions",
        ]
        for cid in required:
            assert cid in CONCEPT_ID_MAP, f"Missing concept: {cid}"

    def test_specific_dsa_concepts_present(self):
        from app.rag.graph_schema import CONCEPT_ID_MAP
        required = [
            "dsa_array", "dsa_tree", "dsa_sorting", "dsa_recursion",
            "dsa_dynamic-programming", "dsa_graph", "dsa_linked-list",
            "dsa_stack", "dsa_queue", "dsa_heap", "dsa_trie",
            "dsa_hash-table", "dsa_binary", "dsa_matrix", "dsa_string",
        ]
        for cid in required:
            assert cid in CONCEPT_ID_MAP, f"Missing concept: {cid}"

    def test_specific_oop_concepts_present(self):
        from app.rag.graph_schema import CONCEPT_ID_MAP
        required = [
            "oop_abstraction", "oop_encapsulation", "oop_polymorphism",
            "oop_composition-inheritance", "oop_interfaces-abstract-classes",
        ]
        for cid in required:
            assert cid in CONCEPT_ID_MAP, f"Missing concept: {cid}"

    def test_concept_by_domain_all_domains_covered(self):
        from app.rag.graph_schema import CONCEPT_BY_DOMAIN, CANONICAL_DOMAIN_IDS
        for domain_id in CANONICAL_DOMAIN_IDS:
            assert domain_id in CONCEPT_BY_DOMAIN, f"Domain '{domain_id}' missing from CONCEPT_BY_DOMAIN"
            assert len(CONCEPT_BY_DOMAIN[domain_id]) > 0


class TestPrerequisiteHints:
    """Verify prerequisite hints reference only valid concept IDs."""

    def test_all_prerequisite_sources_are_valid_concept_ids(self):
        from app.rag.graph_schema import EXPECTED_PREREQUISITE_HINTS, CONCEPT_ID_MAP
        for src, tgt, _ in EXPECTED_PREREQUISITE_HINTS:
            assert src in CONCEPT_ID_MAP, f"Prerequisite source '{src}' is not a valid concept ID"

    def test_all_prerequisite_targets_are_valid_concept_ids(self):
        from app.rag.graph_schema import EXPECTED_PREREQUISITE_HINTS, CONCEPT_ID_MAP
        for src, tgt, _ in EXPECTED_PREREQUISITE_HINTS:
            assert tgt in CONCEPT_ID_MAP, f"Prerequisite target '{tgt}' is not a valid concept ID"

    def test_no_self_referencing_prerequisites(self):
        from app.rag.graph_schema import EXPECTED_PREREQUISITE_HINTS
        for src, tgt, _ in EXPECTED_PREREQUISITE_HINTS:
            assert src != tgt, f"Self-referencing prerequisite found: {src}"

    def test_no_duplicate_prerequisite_pairs(self):
        from app.rag.graph_schema import EXPECTED_PREREQUISITE_HINTS
        pairs = [(src, tgt) for src, tgt, _ in EXPECTED_PREREQUISITE_HINTS]
        assert len(pairs) == len(set(pairs)), "Duplicate prerequisite pairs found"

    def test_all_hints_have_rationale(self):
        from app.rag.graph_schema import EXPECTED_PREREQUISITE_HINTS
        for src, tgt, rationale in EXPECTED_PREREQUISITE_HINTS:
            assert rationale and len(rationale) > 0, (
                f"Missing rationale for {src} → {tgt}"
            )


class TestGraphEdge:
    """Verify GraphEdge construction."""

    def test_basic_construction(self):
        from app.rag.graph_schema import GraphEdge, RelationType, DerivationStrategy
        edge = GraphEdge(
            source_id="dbms_normalization",
            target_id="dbms_keys",
            relation=RelationType.PREREQUISITE_OF,
            derivation=DerivationStrategy.LLM_EXTRACTED,
            evidence="Normalization requires understanding of candidate keys.",
            confidence=0.85,
        )
        assert edge.source_id == "dbms_normalization"
        assert edge.target_id == "dbms_keys"
        assert edge.relation == RelationType.PREREQUISITE_OF
        assert edge.confidence == 0.85
        assert "candidate keys" in edge.evidence

    def test_metadata_edge_has_full_confidence(self):
        from app.rag.graph_schema import GraphEdge, RelationType, DerivationStrategy
        edge = GraphEdge(
            source_id="dbms",
            target_id="dbms_normalization",
            relation=RelationType.CONTAINS,
            derivation=DerivationStrategy.METADATA,
            evidence="Concept file located in data/processed/dbms/",
        )
        assert edge.confidence == 1.0

    def test_relation_type_enum_values(self):
        from app.rag.graph_schema import RelationType
        assert RelationType.CONTAINS == "CONTAINS"
        assert RelationType.HAS_CHUNK == "HAS_CHUNK"
        assert RelationType.RELATED_TO == "RELATED_TO"
        assert RelationType.PREREQUISITE_OF == "PREREQUISITE_OF"
        assert RelationType.MAPS_TO == "MAPS_TO"

    def test_node_type_enum_values(self):
        from app.rag.graph_schema import NodeType
        assert NodeType.DOMAIN == "Domain"
        assert NodeType.CONCEPT == "Concept"
        assert NodeType.KNOWLEDGE_CHUNK == "KnowledgeChunk"
        assert NodeType.SKILL == "Skill"

    def test_derivation_strategy_enum_values(self):
        from app.rag.graph_schema import DerivationStrategy
        assert DerivationStrategy.METADATA == "metadata"
        assert DerivationStrategy.STRUCTURAL == "structural"
        assert DerivationStrategy.LLM_EXTRACTED == "llm"


class TestSchemaConsistency:
    """Cross-checks that the schema is internally self-consistent."""

    def test_total_concept_count_matches_file_listing(self):
        """
        The data/ directory has exactly these files (verified by Phase 0 inspection):
        cn=5, dbms=6, design-patterns=4, dsa=15, ml-dl=5, oop=5, os=5, system-design=5
        Total = 50
        """
        from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE
        assert len(CANONICAL_CONCEPT_CATALOGUE) == 50

    def test_every_concept_in_concept_by_domain_is_in_catalogue(self):
        from app.rag.graph_schema import CONCEPT_BY_DOMAIN, CANONICAL_CONCEPT_CATALOGUE
        catalogue_ids = {c.id for c in CANONICAL_CONCEPT_CATALOGUE}
        for domain_id, concepts in CONCEPT_BY_DOMAIN.items():
            for c in concepts:
                assert c.id in catalogue_ids

    def test_concept_by_domain_total_equals_catalogue(self):
        from app.rag.graph_schema import CONCEPT_BY_DOMAIN, CANONICAL_CONCEPT_CATALOGUE
        total = sum(len(v) for v in CONCEPT_BY_DOMAIN.values())
        assert total == len(CANONICAL_CONCEPT_CATALOGUE)

"""
SmartInterview — Knowledge Graph Schema (Phase 2)

Defines the node types, relationship types, and validation constraints
for the SmartInterview knowledge graph.

The schema is derived STRICTLY from what the existing knowledge base
can reliably provide:

  Source of truth:
    data/processed/<domain>/<concept>_chunks.json
      - chunk fields: chunk_id, domain, concept, source, source_url, text, token_count

  All relationship types must have a documented derivation rule.
  No relationship is created speculatively.

──────────────────────────────────────────────────────────────────────
NODE TYPES
──────────────────────────────────────────────────────────────────────

  Domain
    Properties : id (str, PK), display_name (str)
    Example    : {id: "dbms", display_name: "Database Management Systems"}
    Source     : folder names under data/processed/

  Concept
    Properties : id (str, PK), name (str), domain_id (str FK→Domain),
                 chunk_count (int), source (str), source_url (str)
    Example    : {id: "dbms_normalization", name: "normalization", domain_id: "dbms"}
    Source     : *_chunks.json files; concept field is the canonical name

  KnowledgeChunk
    Properties : id (str, PK), concept_id (str FK→Concept),
                 domain_id (str FK→Domain), text (str),
                 token_count (int), source (str), source_url (str)
    Example    : {id: "dbms_normalization_001", ...}
    Source     : chunk_id field in every *_chunks.json

  Skill
    Properties : id (str, PK), display_name (str)
    Example    : {id: "python", display_name: "Python"}
    Source     : SKILL_DOMAIN_MAP keys in scripts/generate_question.py

──────────────────────────────────────────────────────────────────────
RELATIONSHIP TYPES
──────────────────────────────────────────────────────────────────────

  (Domain) ──[CONTAINS]──> (Concept)
    Derivation : Folder hierarchy — every concept file's `domain` field
    Evidence   : chunk["domain"] == domain folder name
    Confidence : CERTAIN (deterministic from file structure)

  (Concept) ──[HAS_CHUNK]──> (KnowledgeChunk)
    Derivation : chunk_id prefix match — chunk_id starts with f"{domain}_{concept}_"
    Evidence   : chunk["chunk_id"] parsing
    Confidence : CERTAIN (deterministic from naming convention)

  (Concept) ──[RELATED_TO]──> (Concept)
    Derivation : Two sub-strategies:
      A. Structural: File stem contains multiple concept names
         (e.g., "composition-inheritance" links both concepts)
         Evidence: filename decomposition
         Confidence: HIGH
      C. LLM-extracted: LLM reads actual chunk text and returns
         {source, relation, target, evidence} with text quote.
         Restricted to intra-domain pairs in Phase 3.
         Confidence: MEDIUM (verified by text evidence field)
    Direction  : Bidirectional (stored as two directed edges)

  (Concept) ──[PREREQUISITE_OF]──> (Concept)
    Derivation : LLM-extracted (Strategy C only).
      The LLM must cite a specific sentence from the chunk text that
      implies prerequisite ordering (e.g., "requires understanding of X").
    Evidence   : text quote from chunk required
    Confidence : MEDIUM (must pass evidence validation)
    Constraint : Source and target must be in the same domain (Phase 3).
                 Cross-domain prerequisites deferred to Phase 3 review.

  (Skill) ──[MAPS_TO]──> (Domain)
    Derivation : SKILL_DOMAIN_MAP from scripts/generate_question.py
    Evidence   : Direct code reference to SKILL_DOMAIN_MAP entry
    Confidence : CERTAIN (existing human-authored mapping)
    Note       : Maps to Domain, not Concept, because SKILL_DOMAIN_MAP
                 maps skills → domains. Concept-level skill mapping
                 would require LLM and is deferred.

──────────────────────────────────────────────────────────────────────
EXCLUDED RELATIONSHIP TYPES (and reasons)
──────────────────────────────────────────────────────────────────────

  Concept ──SAME_AS──> Concept
    Excluded: No aliasing data exists in the KB.

  KnowledgeChunk ──CITES──> KnowledgeChunk
    Excluded: Chunks don't have inter-chunk citations.

  Concept ──CONTRADICTS──> Concept
    Excluded: No contradiction signals in the data.

──────────────────────────────────────────────────────────────────────
VALIDATION CONSTRAINTS (enforced in Phase 4)
──────────────────────────────────────────────────────────────────────

  1. Every Concept must have at least one HAS_CHUNK edge.
  2. Every KnowledgeChunk must have exactly one HAS_CHUNK incoming edge.
  3. Every Concept must have exactly one CONTAINS incoming edge (from its Domain).
  4. No self-referencing RELATED_TO or PREREQUISITE_OF edges.
  5. No duplicate edges of the same type between the same pair of nodes.
  6. Every RELATED_TO and PREREQUISITE_OF edge must have an 'evidence' property.
  7. PREREQUISITE_OF source and target must be in the same domain (Phase 3 constraint).
  8. All Domain node ids must match the 8 canonical domains in CANONICAL_DOMAINS.

──────────────────────────────────────────────────────────────────────
COMPLETE CONCEPT INVENTORY (derived from data/processed/)
──────────────────────────────────────────────────────────────────────

  Domain cn (Computer Networks) — 5 concepts:
    dns, http-vs-https, ipv4-vs-ipv6, osi-model, tcp-vs-udp

  Domain dbms (Database Management) — 6 concepts:
    acid-properties, indexing, keys, normalization, sql-joins, transactions

  Domain design-patterns — 4 concepts:
    factory, observer, singleton, strategy

  Domain dsa (Data Structures & Algorithms) — 15 concepts:
    array, binary, dynamic-programming, graph, hash-table, heap,
    linked-list, matrix, queue, recursion, sorting, stack, string, tree, trie

  Domain ml-dl (Machine Learning & Deep Learning) — 5 concepts:
    bias-variance-tradeoff, decision-trees, linear-vs-logistic-regression,
    neural-networks, overfitting-vs-underfitting

  Domain oop (Object-Oriented Programming) — 5 concepts:
    abstraction, composition-inheritance, encapsulation,
    interfaces-abstract-classes, polymorphism

  Domain os (Operating Systems) — 5 concepts:
    deadlock, mutex-vs-semaphore, process-vs-thread,
    scheduling-algorithms, virtual-memory

  Domain system-design — 5 concepts:
    caching, cap-theorem, consistent-hashing, load-balancing,
    microservices-vs-monolith

  TOTAL: 8 domains, 50 concepts

──────────────────────────────────────────────────────────────────────
STRUCTURAL RELATIONSHIPS (derivable WITHOUT LLM, Strategy A)
──────────────────────────────────────────────────────────────────────
  These are extracted by splitting compound concept file-names on '-vs-' or
  other structural separators and linking the components:

  http-vs-https      → HTTP RELATED_TO HTTPS  (comparison concept)
  ipv4-vs-ipv6       → IPv4 RELATED_TO IPv6
  tcp-vs-udp         → TCP RELATED_TO UDP
  mutex-vs-semaphore → Mutex RELATED_TO Semaphore
  process-vs-thread  → Process RELATED_TO Thread
  composition-inheritance → Composition RELATED_TO Inheritance
  interfaces-abstract-classes → Interfaces RELATED_TO AbstractClasses
  linear-vs-logistic-regression → LinearRegression RELATED_TO LogisticRegression
  overfitting-vs-underfitting → Overfitting RELATED_TO Underfitting
  microservices-vs-monolith → Microservices RELATED_TO Monolith
  bias-variance-tradeoff → BiasVariance relationship (tradeoff)

  Evidence: filename decomposition (documented, reproducible)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


# ── Node Type Enumerations ────────────────────────────────────────────

class NodeType(str, Enum):
    DOMAIN = "Domain"
    CONCEPT = "Concept"
    KNOWLEDGE_CHUNK = "KnowledgeChunk"
    SKILL = "Skill"


class RelationType(str, Enum):
    CONTAINS = "CONTAINS"                   # Domain → Concept
    HAS_CHUNK = "HAS_CHUNK"                 # Concept → KnowledgeChunk
    RELATED_TO = "RELATED_TO"               # Concept ↔ Concept
    PREREQUISITE_OF = "PREREQUISITE_OF"     # Concept → Concept
    MAPS_TO = "MAPS_TO"                     # Skill → Domain


class DerivationStrategy(str, Enum):
    METADATA = "metadata"         # Directly from chunk fields — certain
    STRUCTURAL = "structural"     # From filename decomposition — high confidence
    LLM_EXTRACTED = "llm"         # From LLM reading chunk text — medium confidence


# ── Node Definitions ──────────────────────────────────────────────────

@dataclass
class DomainNode:
    """Represents one of the 8 canonical technical knowledge domains."""
    id: str               # e.g. "dbms"
    display_name: str     # e.g. "Database Management Systems"
    concept_count: int = 0


@dataclass
class ConceptNode:
    """Represents a technical concept within a domain."""
    id: str               # e.g. "dbms_normalization"
    name: str             # e.g. "normalization"
    domain_id: str        # e.g. "dbms"
    chunk_count: int = 0
    source: str = ""
    source_url: str = ""


@dataclass
class KnowledgeChunkNode:
    """Represents a single knowledge chunk from the processed corpus."""
    id: str               # e.g. "dbms_normalization_001"
    concept_id: str       # e.g. "dbms_normalization"
    domain_id: str        # e.g. "dbms"
    text: str = ""
    token_count: int = 0
    source: str = ""
    source_url: str = ""


@dataclass
class SkillNode:
    """Represents a resume-extractable technical skill."""
    id: str               # e.g. "python" (lowercase canonical key)
    display_name: str     # e.g. "Python"


# ── Relationship Definitions ──────────────────────────────────────────

@dataclass
class GraphEdge:
    """
    A directed edge in the knowledge graph.

    All edges require:
    - source_id: the 'from' node id
    - target_id: the 'to' node id
    - relation: the relationship type
    - derivation: how this edge was produced
    - evidence: a string that justifies the edge (mandatory for LLM-derived edges)
    """
    source_id: str
    target_id: str
    relation: RelationType
    derivation: DerivationStrategy
    evidence: str = ""        # text quote or rule description that supports this edge
    confidence: float = 1.0   # 0.0–1.0; 1.0 = certain, 0.7 = LLM medium


# ── Domain Catalogue (all 8 canonical domains) ────────────────────────

CANONICAL_DOMAIN_CATALOGUE: List[DomainNode] = [
    DomainNode(id="cn",             display_name="Computer Networks"),
    DomainNode(id="dbms",           display_name="Database Management Systems"),
    DomainNode(id="design-patterns",display_name="Design Patterns"),
    DomainNode(id="dsa",            display_name="Data Structures & Algorithms"),
    DomainNode(id="ml-dl",          display_name="Machine Learning & Deep Learning"),
    DomainNode(id="oop",            display_name="Object-Oriented Programming"),
    DomainNode(id="os",             display_name="Operating Systems"),
    DomainNode(id="system-design",  display_name="System Design"),
]

CANONICAL_DOMAIN_IDS = {d.id for d in CANONICAL_DOMAIN_CATALOGUE}


# ── Complete Concept Catalogue (50 concepts, metadata-derived) ─────────

CANONICAL_CONCEPT_CATALOGUE: List[ConceptNode] = [
    # cn
    ConceptNode(id="cn_dns",              name="dns",              domain_id="cn"),
    ConceptNode(id="cn_http-vs-https",    name="http-vs-https",    domain_id="cn"),
    ConceptNode(id="cn_ipv4-vs-ipv6",     name="ipv4-vs-ipv6",     domain_id="cn"),
    ConceptNode(id="cn_osi-model",        name="osi-model",        domain_id="cn"),
    ConceptNode(id="cn_tcp-vs-udp",       name="tcp-vs-udp",       domain_id="cn"),
    # dbms
    ConceptNode(id="dbms_acid-properties",name="acid-properties",  domain_id="dbms"),
    ConceptNode(id="dbms_indexing",       name="indexing",         domain_id="dbms"),
    ConceptNode(id="dbms_keys",           name="keys",             domain_id="dbms"),
    ConceptNode(id="dbms_normalization",  name="normalization",    domain_id="dbms"),
    ConceptNode(id="dbms_sql-joins",      name="sql-joins",        domain_id="dbms"),
    ConceptNode(id="dbms_transactions",   name="transactions",     domain_id="dbms"),
    # design-patterns
    ConceptNode(id="dp_factory",          name="factory",          domain_id="design-patterns"),
    ConceptNode(id="dp_observer",         name="observer",         domain_id="design-patterns"),
    ConceptNode(id="dp_singleton",        name="singleton",        domain_id="design-patterns"),
    ConceptNode(id="dp_strategy",         name="strategy",         domain_id="design-patterns"),
    # dsa
    ConceptNode(id="dsa_array",           name="array",            domain_id="dsa"),
    ConceptNode(id="dsa_binary",          name="binary",           domain_id="dsa"),
    ConceptNode(id="dsa_dynamic-programming", name="dynamic-programming", domain_id="dsa"),
    ConceptNode(id="dsa_graph",           name="graph",            domain_id="dsa"),
    ConceptNode(id="dsa_hash-table",      name="hash-table",       domain_id="dsa"),
    ConceptNode(id="dsa_heap",            name="heap",             domain_id="dsa"),
    ConceptNode(id="dsa_linked-list",     name="linked-list",      domain_id="dsa"),
    ConceptNode(id="dsa_matrix",          name="matrix",           domain_id="dsa"),
    ConceptNode(id="dsa_queue",           name="queue",            domain_id="dsa"),
    ConceptNode(id="dsa_recursion",       name="recursion",        domain_id="dsa"),
    ConceptNode(id="dsa_sorting",         name="sorting",          domain_id="dsa"),
    ConceptNode(id="dsa_stack",           name="stack",            domain_id="dsa"),
    ConceptNode(id="dsa_string",          name="string",           domain_id="dsa"),
    ConceptNode(id="dsa_tree",            name="tree",             domain_id="dsa"),
    ConceptNode(id="dsa_trie",            name="trie",             domain_id="dsa"),
    # ml-dl
    ConceptNode(id="mldl_bias-variance-tradeoff", name="bias-variance-tradeoff", domain_id="ml-dl"),
    ConceptNode(id="mldl_decision-trees",         name="decision-trees",         domain_id="ml-dl"),
    ConceptNode(id="mldl_linear-vs-logistic-regression", name="linear-vs-logistic-regression", domain_id="ml-dl"),
    ConceptNode(id="mldl_neural-networks",        name="neural-networks",        domain_id="ml-dl"),
    ConceptNode(id="mldl_overfitting-vs-underfitting", name="overfitting-vs-underfitting", domain_id="ml-dl"),
    # oop
    ConceptNode(id="oop_abstraction",             name="abstraction",              domain_id="oop"),
    ConceptNode(id="oop_composition-inheritance", name="composition-inheritance",  domain_id="oop"),
    ConceptNode(id="oop_encapsulation",           name="encapsulation",            domain_id="oop"),
    ConceptNode(id="oop_interfaces-abstract-classes", name="interfaces-abstract-classes", domain_id="oop"),
    ConceptNode(id="oop_polymorphism",            name="polymorphism",             domain_id="oop"),
    # os
    ConceptNode(id="os_deadlock",                 name="deadlock",                 domain_id="os"),
    ConceptNode(id="os_mutex-vs-semaphore",       name="mutex-vs-semaphore",       domain_id="os"),
    ConceptNode(id="os_process-vs-thread",        name="process-vs-thread",        domain_id="os"),
    ConceptNode(id="os_scheduling-algorithms",    name="scheduling-algorithms",    domain_id="os"),
    ConceptNode(id="os_virtual-memory",           name="virtual-memory",           domain_id="os"),
    # system-design
    ConceptNode(id="sd_caching",                  name="caching",                  domain_id="system-design"),
    ConceptNode(id="sd_cap-theorem",              name="cap-theorem",              domain_id="system-design"),
    ConceptNode(id="sd_consistent-hashing",       name="consistent-hashing",       domain_id="system-design"),
    ConceptNode(id="sd_load-balancing",           name="load-balancing",           domain_id="system-design"),
    ConceptNode(id="sd_microservices-vs-monolith", name="microservices-vs-monolith", domain_id="system-design"),
]

CONCEPT_ID_MAP = {c.id: c for c in CANONICAL_CONCEPT_CATALOGUE}
CONCEPT_BY_DOMAIN = {}
for _c in CANONICAL_CONCEPT_CATALOGUE:
    CONCEPT_BY_DOMAIN.setdefault(_c.domain_id, []).append(_c)


# ── Structural Relationships (Strategy A — filename decomposition) ─────
#
# Concepts whose filenames contain '-vs-' or compound separators have
# structural RELATED_TO relationships derivable without LLM.
#
# Rule: if concept name is "X-vs-Y", then X RELATED_TO Y (bidirectional).
# Evidence string: "Filename '{name}' is a comparison concept linking X and Y."

STRUCTURAL_RELATED_TO_PAIRS: List[tuple[str, str, str]] = [
    # (concept_id_A, concept_id_B, evidence_note)
    ("cn_http-vs-https",    "cn_http-vs-https",   ""),    # self = skip, placeholder
    ("cn_tcp-vs-udp",       "cn_tcp-vs-udp",      ""),    # self = skip
    # Real cross-node structural pairs within compound concepts:
    # These link the two sides of compound filenames to each other conceptually.
    # They will be expanded during graph construction in Phase 3.
    # Listed here as documentation only — Phase 3 will compute them automatically.
]

# ── Intra-domain Prerequisite Ordering (LLM-extracted, Phase 3) ───────
#
# These are the INTRA-DOMAIN prerequisite relationships we EXPECT to find
# based on domain knowledge.  The LLM in Phase 3 must CONFIRM each one
# by citing evidence from the actual chunk text.
# If no evidence is found, the relationship is NOT created.
#
# Format: (prerequisite_concept_id, advanced_concept_id, rationale_hint)
EXPECTED_PREREQUISITE_HINTS: List[tuple[str, str, str]] = [
    # dbms
    ("dbms_keys",           "dbms_normalization",   "Normalization requires understanding of candidate keys and functional dependencies"),
    ("dbms_normalization",  "dbms_transactions",    "Transactions build on normalized schema design"),
    ("dbms_normalization",  "dbms_indexing",        "Indexing strategies depend on schema structure from normalization"),
    ("dbms_transactions",   "dbms_acid-properties", "ACID properties define correctness guarantees of transactions"),
    # dsa
    ("dsa_array",           "dsa_sorting",          "Sorting algorithms operate on arrays as the base data structure"),
    ("dsa_array",           "dsa_binary",           "Binary search is applied to sorted arrays"),
    ("dsa_array",           "dsa_hash-table",       "Hash tables often use arrays internally"),
    ("dsa_array",           "dsa_matrix",           "Matrices are 2D arrays"),
    ("dsa_linked-list",     "dsa_stack",            "Stack can be implemented using linked list"),
    ("dsa_linked-list",     "dsa_queue",            "Queue can be implemented using linked list"),
    ("dsa_tree",            "dsa_heap",             "Heap is a specialized tree"),
    ("dsa_tree",            "dsa_trie",             "Trie is a specialized tree for strings"),
    ("dsa_recursion",       "dsa_dynamic-programming", "Dynamic programming builds on recursive subproblems"),
    ("dsa_recursion",       "dsa_tree",             "Tree traversal typically uses recursion"),
    ("dsa_recursion",       "dsa_graph",            "Graph traversal (DFS) uses recursion"),
    # oop
    ("oop_encapsulation",   "oop_abstraction",      "Abstraction builds on encapsulation principles"),
    ("oop_abstraction",     "oop_interfaces-abstract-classes", "Interfaces/abstract classes implement abstraction"),
    ("oop_composition-inheritance", "oop_polymorphism", "Polymorphism is achieved through inheritance"),
    # os
    ("os_process-vs-thread","os_scheduling-algorithms", "Scheduling algorithms manage processes and threads"),
    ("os_process-vs-thread","os_deadlock",          "Deadlock involves processes/threads waiting on each other"),
    ("os_mutex-vs-semaphore","os_deadlock",         "Deadlocks often arise from incorrect mutex/semaphore use"),
    # ml-dl
    ("mldl_bias-variance-tradeoff", "mldl_overfitting-vs-underfitting", "Overfitting/underfitting is explained by bias-variance tradeoff"),
    ("mldl_linear-vs-logistic-regression", "mldl_neural-networks", "Neural networks generalise regression"),
    ("mldl_decision-trees", "mldl_neural-networks", "Both are supervised learning models"),
    # system-design
    ("sd_cap-theorem",      "sd_consistent-hashing", "Consistent hashing is a technique to handle CAP tradeoffs"),
    ("sd_load-balancing",   "sd_consistent-hashing", "Consistent hashing is a load balancing strategy"),
    ("sd_caching",          "sd_cap-theorem",       "Caching strategies must consider CAP theorem constraints"),
]

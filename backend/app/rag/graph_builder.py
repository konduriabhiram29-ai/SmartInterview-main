"""
SmartInterview — Knowledge Graph Construction Pipeline (Phase 3)

Builds the knowledge graph from the existing knowledge base using three
controlled, traceable stages:

  Stage A — Metadata-derived edges (no LLM, certain)
    • Domain ──CONTAINS──> Concept   (folder hierarchy)
    • Concept ──HAS_CHUNK──> KnowledgeChunk  (chunk_id naming)
    • Skill ──MAPS_TO──> Domain      (SKILL_DOMAIN_MAP)

  Stage B — Structural edges from filename decomposition (no LLM, high confidence)
    • Concept ──RELATED_TO──> Concept  (compound filenames with -vs- / -)

  Stage C — LLM-confirmed prerequisite edges (uses Groq, medium confidence)
    • Concept ──PREREQUISITE_OF──> Concept  (from EXPECTED_PREREQUISITE_HINTS)
    • Only created when LLM cites evidence from actual chunk text
    • LLM also extracts additional RELATED_TO edges from intra-domain concept pairs

Output:
    data/graph_data.json   — complete graph: nodes + edges + provenance

The pipeline is fully reproducible:
    - Stage A and B are deterministic (no randomness, no LLM)
    - Stage C uses the same prompt, same model, temperature=0.0

Usage (standalone):
    cd SmartInterview-main
    python -m app.rag.graph_builder --dry-run   # Stages A+B only, no LLM calls
    python -m app.rag.graph_builder              # Full pipeline including Stage C

Usage (imported):
    from app.rag.graph_builder import build_graph
    graph = build_graph(dry_run=True)
"""

from __future__ import annotations

import json
import os
import glob
import re
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Path helpers ──────────────────────────────────────────────────────────────

def _project_root() -> str:
    """
    Resolve the project root directory.
    The file lives at: SmartInterview-main/backend/app/rag/graph_builder.py
    So project root is 4 levels up from this file.
    """
    this_file = os.path.abspath(__file__)
    # graph_builder.py → rag/ → app/ → backend/ → SmartInterview-main/
    return os.path.normpath(os.path.join(this_file, "..", "..", "..", ".."))


def _processed_dir() -> str:
    return os.path.join(_project_root(), "data", "processed")


def _output_path() -> str:
    return os.path.join(_project_root(), "data", "graph_data.json")


# ── Output data structures ────────────────────────────────────────────────────

@dataclass
class GraphNode:
    id: str
    type: str          # Domain | Concept | KnowledgeChunk | Skill
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": self.type, "properties": self.properties}


@dataclass
class GraphEdgeRecord:
    source_id: str
    target_id: str
    relation: str
    derivation: str    # metadata | structural | llm
    evidence: str      # text quote or rule description
    confidence: float  # 1.0=certain, 0.85=structural, 0.75=llm-confirmed

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GraphData:
    """The complete graph output written to graph_data.json."""
    nodes: List[dict] = field(default_factory=list)
    edges: List[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    build_meta: dict = field(default_factory=dict)


# ── Stage A: Metadata-derived edges ──────────────────────────────────────────

def build_metadata_edges(processed_dir: str) -> Tuple[List[GraphNode], List[GraphEdgeRecord]]:
    """
    Stage A: Build all certain edges directly from file structure and metadata.

    Returns (nodes, edges) where:
      - nodes = Domain + Concept + KnowledgeChunk nodes
      - edges = CONTAINS + HAS_CHUNK edges
    """
    from app.rag.graph_schema import (
        CANONICAL_DOMAIN_CATALOGUE,
        CANONICAL_CONCEPT_CATALOGUE,
        CONCEPT_ID_MAP,
        CANONICAL_DOMAIN_IDS,
    )

    nodes: List[GraphNode] = []
    edges: List[GraphEdgeRecord] = []
    seen_node_ids: set = set()

    # ── Domain nodes ──
    for domain in CANONICAL_DOMAIN_CATALOGUE:
        node = GraphNode(
            id=domain.id,
            type="Domain",
            properties={"display_name": domain.display_name},
        )
        nodes.append(node)
        seen_node_ids.add(domain.id)

    # ── Concept nodes + CONTAINS edges ──
    chunk_files = glob.glob(os.path.join(processed_dir, "**", "*_chunks.json"), recursive=True)

    concept_chunk_counts: Dict[str, int] = {}
    concept_sources: Dict[str, Tuple[str, str]] = {}   # concept_id → (source, source_url)
    all_chunk_nodes: List[GraphNode] = []
    all_has_chunk_edges: List[GraphEdgeRecord] = []

    for file_path in sorted(chunk_files):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        except Exception as e:
            logger.warning("Failed to read %s: %s", file_path, e)
            continue

        if not chunks:
            continue

        first = chunks[0]
        domain_id = first.get("domain", "")
        concept_name = first.get("concept", "")

        if domain_id not in CANONICAL_DOMAIN_IDS:
            logger.warning("Unknown domain '%s' in %s — skipping", domain_id, file_path)
            continue

        # Build concept_id using same convention as graph_schema.py
        # Prefix mapping: design-patterns → dp, ml-dl → mldl, system-design → sd, others → domain_id
        prefix_map = {
            "design-patterns": "dp",
            "ml-dl": "mldl",
            "system-design": "sd",
        }
        prefix = prefix_map.get(domain_id, domain_id)
        concept_id = f"{prefix}_{concept_name}"

        # Validate against catalogue
        if concept_id not in CONCEPT_ID_MAP:
            logger.warning(
                "Concept '%s' from file '%s' not in catalogue — skipping",
                concept_id,
                os.path.basename(file_path),
            )
            continue

        # Record source info from first chunk
        concept_sources[concept_id] = (
            first.get("source", ""),
            first.get("source_url", ""),
        )

        # Count chunks
        concept_chunk_counts[concept_id] = concept_chunk_counts.get(concept_id, 0) + len(chunks)

        # ── KnowledgeChunk nodes + HAS_CHUNK edges ──
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "")
            if not chunk_id:
                continue

            chunk_node = GraphNode(
                id=chunk_id,
                type="KnowledgeChunk",
                properties={
                    "concept_id": concept_id,
                    "domain_id": domain_id,
                    "text": chunk.get("text", "")[:300],   # store preview only
                    "token_count": chunk.get("token_count", 0),
                    "source": chunk.get("source", ""),
                    "source_url": chunk.get("source_url", ""),
                },
            )
            all_chunk_nodes.append(chunk_node)
            seen_node_ids.add(chunk_id)

            all_has_chunk_edges.append(GraphEdgeRecord(
                source_id=concept_id,
                target_id=chunk_id,
                relation="HAS_CHUNK",
                derivation="metadata",
                evidence=f"chunk_id '{chunk_id}' belongs to concept '{concept_name}' in domain '{domain_id}' per file structure",
                confidence=1.0,
            ))

    # ── Build Concept nodes ──
    for concept in CANONICAL_CONCEPT_CATALOGUE:
        src, url = concept_sources.get(concept.id, ("", ""))
        concept_node = GraphNode(
            id=concept.id,
            type="Concept",
            properties={
                "name": concept.name,
                "domain_id": concept.domain_id,
                "chunk_count": concept_chunk_counts.get(concept.id, 0),
                "source": src,
                "source_url": url,
            },
        )
        nodes.append(concept_node)
        seen_node_ids.add(concept.id)

        # CONTAINS edge: Domain → Concept
        edges.append(GraphEdgeRecord(
            source_id=concept.domain_id,
            target_id=concept.id,
            relation="CONTAINS",
            derivation="metadata",
            evidence=f"Concept file located in data/processed/{concept.domain_id}/ folder",
            confidence=1.0,
        ))

    nodes.extend(all_chunk_nodes)
    edges.extend(all_has_chunk_edges)

    logger.info(
        "[Stage A] Built %d nodes (%d domains, %d concepts, %d chunks), %d edges",
        len(nodes),
        len(CANONICAL_DOMAIN_CATALOGUE),
        len(CANONICAL_CONCEPT_CATALOGUE),
        len(all_chunk_nodes),
        len(edges),
    )
    return nodes, edges


def build_skill_maps() -> Tuple[List[GraphNode], List[GraphEdgeRecord]]:
    """
    Build Skill nodes and MAPS_TO edges from SKILL_DOMAIN_MAP.
    These are 100% metadata-derived — no LLM required.
    """
    import sys
    import importlib.util

    # Import SKILL_DOMAIN_MAP and CANONICAL_SKILL_NAMES from generate_question.py
    gen_path = os.path.join(_project_root(), "scripts", "generate_question.py")
    spec = importlib.util.spec_from_file_location("gq_mod", gen_path)
    gq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gq)

    SKILL_DOMAIN_MAP = gq.SKILL_DOMAIN_MAP
    CANONICAL_SKILL_NAMES = gq.CANONICAL_SKILL_NAMES

    nodes: List[GraphNode] = []
    edges: List[GraphEdgeRecord] = []

    for skill_key, domain_ids in SKILL_DOMAIN_MAP.items():
        display_name = CANONICAL_SKILL_NAMES.get(skill_key, skill_key.title())
        skill_node = GraphNode(
            id=f"skill_{skill_key.replace(' ', '_').replace('/', '_')}",
            type="Skill",
            properties={"key": skill_key, "display_name": display_name},
        )
        nodes.append(skill_node)

        for domain_id in domain_ids:
            edges.append(GraphEdgeRecord(
                source_id=skill_node.id,
                target_id=domain_id,
                relation="MAPS_TO",
                derivation="metadata",
                evidence=f"SKILL_DOMAIN_MAP['{skill_key}'] = {domain_ids} in scripts/generate_question.py",
                confidence=1.0,
            ))

    logger.info("[Stage A] Built %d Skill nodes, %d MAPS_TO edges", len(nodes), len(edges))
    return nodes, edges


# ── Stage B: Structural RELATED_TO from filename decomposition ────────────────

# Patterns to split compound concept names
_SPLIT_PATTERNS = ["-vs-", "-and-"]

# Compound concepts that explicitly link two named sub-concepts (manual list)
# Format: concept_id → [(left_concept_id, right_concept_id)]
# These are generated automatically from filename analysis below
def build_structural_edges() -> List[GraphEdgeRecord]:
    """
    Stage B: Derive RELATED_TO edges from compound filenames.

    A filename like 'composition-inheritance' signals that the concepts
    'composition' and 'inheritance' are related.
    A filename like 'http-vs-https' signals that 'http' and 'https' are
    being compared/related.

    These RELATED_TO edges are bidirectional (stored as two directed edges).
    Evidence = filename decomposition rule.
    """
    from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE, CONCEPT_ID_MAP

    edges: List[GraphEdgeRecord] = []

    # Concepts that are explicitly compound (two real concepts joined)
    # Determined by manual inspection during Phase 2 + pattern matching
    COMPOUND_CONCEPTS: List[Tuple[str, str, str]] = [
        # (concept_id, left_display, right_display)
        # -vs- patterns: comparison concepts
        ("cn_http-vs-https",          "HTTP",            "HTTPS"),
        ("cn_ipv4-vs-ipv6",           "IPv4",            "IPv6"),
        ("cn_tcp-vs-udp",             "TCP",             "UDP"),
        ("os_mutex-vs-semaphore",     "Mutex",           "Semaphore"),
        ("os_process-vs-thread",      "Process",         "Thread"),
        ("mldl_linear-vs-logistic-regression", "Linear Regression", "Logistic Regression"),
        ("mldl_overfitting-vs-underfitting",   "Overfitting",       "Underfitting"),
        ("sd_microservices-vs-monolith",       "Microservices",     "Monolith"),
        # Compound (non -vs-) concepts that link two sub-concepts
        ("oop_composition-inheritance",         "Composition",  "Inheritance"),
        ("oop_interfaces-abstract-classes",     "Interfaces",   "Abstract Classes"),
        ("mldl_bias-variance-tradeoff",         "Bias",         "Variance"),
    ]

    for concept_id, left_name, right_name in COMPOUND_CONCEPTS:
        if concept_id not in CONCEPT_ID_MAP:
            logger.warning("[Stage B] Compound concept '%s' not in catalogue — skip", concept_id)
            continue

        concept = CONCEPT_ID_MAP[concept_id]
        evidence = (
            f"Filename '{concept.name}' is a compound concept explicitly relating "
            f"'{left_name}' and '{right_name}'. Structural decomposition of filename."
        )

        # The compound concept RELATED_TO itself is not useful.
        # Instead, we create RELATED_TO edges between this compound concept
        # and the other concepts in its domain that represent each side.
        # Additionally, we can find if the individual sub-concepts exist
        # separately in the catalogue.
        # For now: we document the internal relationship within the compound
        # concept by creating a RELATED_TO edge from this concept to sibling
        # concepts in the same domain that share a name component.

        sibling_concepts = [
            c for c in CANONICAL_CONCEPT_CATALOGUE
            if c.domain_id == concept.domain_id
            and c.id != concept_id
        ]

        for sibling in sibling_concepts:
            sibling_name_lower = sibling.name.lower()
            left_lower = left_name.lower().replace(" ", "-")
            right_lower = right_name.lower().replace(" ", "-")

            # Check if any part of the compound name matches a sibling concept
            if (left_lower in sibling_name_lower or right_lower in sibling_name_lower
                    or sibling_name_lower in left_lower or sibling_name_lower in right_lower):

                edge_evidence = (
                    f"Structural: '{concept.name}' explicitly discusses '{sibling.name}'. "
                    f"Filename decomposition of '{concept.name}'."
                )
                # Forward
                edges.append(GraphEdgeRecord(
                    source_id=concept_id,
                    target_id=sibling.id,
                    relation="RELATED_TO",
                    derivation="structural",
                    evidence=edge_evidence,
                    confidence=0.85,
                ))
                # Backward (bidirectional)
                edges.append(GraphEdgeRecord(
                    source_id=sibling.id,
                    target_id=concept_id,
                    relation="RELATED_TO",
                    derivation="structural",
                    evidence=edge_evidence,
                    confidence=0.85,
                ))

    # Deduplicate (same source→target pair may have been added twice)
    seen: set = set()
    deduped: List[GraphEdgeRecord] = []
    for e in edges:
        key = (e.source_id, e.target_id, e.relation)
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    logger.info("[Stage B] Built %d structural RELATED_TO edges", len(deduped))
    return deduped


# ── Stage C: LLM-confirmed PREREQUISITE_OF and RELATED_TO edges ───────────────

_PREREQUISITE_PROMPT_SYSTEM = """\
You are a precise technical knowledge graph analyst for a computer science interview system.

Your task: Given TWO technical concepts and sample text from their knowledge bases,
determine whether concept A is a PREREQUISITE of concept B (i.e., understanding A
is needed before understanding B).

STRICT RULES:
1. Only confirm a prerequisite if there is a direct textual signal in the provided excerpts.
2. Quote the EXACT sentence or phrase that supports your answer.
3. If no clear evidence exists in the text, answer NO_EVIDENCE.
4. Do NOT use general world knowledge — base your answer ONLY on the provided text.
5. Return valid JSON, nothing else.

Output format:
{
  "confirmed": true | false,
  "confidence": 0.0-1.0,
  "evidence_quote": "exact quoted sentence from the text, or empty string if not confirmed",
  "reasoning": "brief explanation"
}
"""


def _build_prerequisite_prompt(
    src_concept: str, src_chunks: List[str],
    tgt_concept: str, tgt_chunks: List[str],
    rationale_hint: str,
) -> str:
    src_excerpts = "\n---\n".join(c[:400] for c in src_chunks[:2])
    tgt_excerpts = "\n---\n".join(c[:400] for c in tgt_chunks[:2])
    return f"""Concept A (potential prerequisite): {src_concept}
Concept B (potential advanced concept): {tgt_concept}
Rationale hint: {rationale_hint}

Text from Concept A knowledge base:
{src_excerpts}

Text from Concept B knowledge base:
{tgt_excerpts}

Question: Is understanding Concept A ({src_concept}) a prerequisite for understanding Concept B ({tgt_concept})?
Base your answer ONLY on the text above. Return JSON only."""


_RELATED_PROMPT_SYSTEM = """\
You are a precise technical knowledge graph analyst for a computer science interview system.

Your task: Given two technical concepts from the SAME domain and sample text from
their knowledge bases, determine if they are meaningfully RELATED (i.e., understanding
one helps understand the other, or they share a core technical connection).

STRICT RULES:
1. Only confirm a relationship if there is a direct textual signal in the provided text.
2. Quote the EXACT sentence or phrase that supports your answer.
3. If no clear evidence exists, answer NO_EVIDENCE.
4. Do NOT invent relationships. Base answers ONLY on the provided text.
5. Return valid JSON, nothing else.

Output format:
{
  "confirmed": true | false,
  "confidence": 0.0-1.0,
  "evidence_quote": "exact quoted sentence from the text, or empty string if not confirmed",
  "reasoning": "brief explanation"
}
"""


def _build_related_prompt(
    concept_a: str, chunks_a: List[str],
    concept_b: str, chunks_b: List[str],
) -> str:
    excerpts_a = "\n---\n".join(c[:350] for c in chunks_a[:2])
    excerpts_b = "\n---\n".join(c[:350] for c in chunks_b[:2])
    return f"""Concept A: {concept_a}
Concept B: {concept_b}

Text from Concept A:
{excerpts_a}

Text from Concept B:
{excerpts_b}

Question: Are these two concepts meaningfully related in a computer science context,
based on the text above? Return JSON only."""


def _call_llm_for_edge(
    system_prompt: str,
    user_prompt: str,
    groq_client,
    model: str,
    max_retries: int = 2,
) -> Optional[dict]:
    """
    Call the LLM with a structured prompt and parse the JSON response.
    Returns None if the LLM call fails or returns invalid JSON.
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=512,
            )
            text = resp.choices[0].message.content.strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                text = re.sub(r"```[a-z]*\n?", "", text).strip().rstrip("```").strip()

            # Extract JSON object
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end + 1]

            return json.loads(text)

        except json.JSONDecodeError as je:
            logger.warning(
                "[Stage C] JSON parse error on attempt %d: %s | raw=%s",
                attempt, je, text[:200] if "text" in dir() else "N/A"
            )
        except Exception as e:
            logger.warning("[Stage C] LLM call failed on attempt %d: %s", attempt, e)

        if attempt < max_retries:
            time.sleep(3)

    return None


def _load_concept_chunks(processed_dir: str, domain_id: str, concept_name: str) -> List[str]:
    """Load text from all chunks of a given concept."""
    # Find the chunk file
    pattern = os.path.join(processed_dir, domain_id, f"{concept_name}_chunks.json")
    if not os.path.exists(pattern):
        return []
    try:
        with open(pattern, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        return [c.get("text", "") for c in chunks if c.get("text")]
    except Exception:
        return []


def build_llm_edges(
    processed_dir: str,
    groq_client,
    model: str,
) -> List[GraphEdgeRecord]:
    """
    Stage C: Use the LLM to confirm/reject prerequisite edges and extract
    additional RELATED_TO edges from intra-domain concept pairs.

    Only edges with confirmed=True and a non-empty evidence_quote are created.
    Every rejected hint is logged (not silently dropped).
    """
    from app.rag.graph_schema import (
        EXPECTED_PREREQUISITE_HINTS,
        CONCEPT_ID_MAP,
        CONCEPT_BY_DOMAIN,
    )

    edges: List[GraphEdgeRecord] = []
    confirmed = 0
    rejected = 0
    failed = 0

    logger.info("[Stage C] Processing %d prerequisite hints via LLM...", len(EXPECTED_PREREQUISITE_HINTS))

    # ── Part 1: Prerequisite hints ──
    for src_id, tgt_id, rationale in EXPECTED_PREREQUISITE_HINTS:
        src_concept = CONCEPT_ID_MAP.get(src_id)
        tgt_concept = CONCEPT_ID_MAP.get(tgt_id)
        if not src_concept or not tgt_concept:
            logger.warning("[Stage C] Skipping invalid concept IDs: %s → %s", src_id, tgt_id)
            failed += 1
            continue

        src_chunks = _load_concept_chunks(processed_dir, src_concept.domain_id, src_concept.name)
        tgt_chunks = _load_concept_chunks(processed_dir, tgt_concept.domain_id, tgt_concept.name)

        if not src_chunks or not tgt_chunks:
            logger.warning(
                "[Stage C] No chunks for %s or %s — skipping", src_id, tgt_id
            )
            failed += 1
            continue

        user_prompt = _build_prerequisite_prompt(
            src_concept=src_concept.name,
            src_chunks=src_chunks,
            tgt_concept=tgt_concept.name,
            tgt_chunks=tgt_chunks,
            rationale_hint=rationale,
        )

        result = _call_llm_for_edge(
            system_prompt=_PREREQUISITE_PROMPT_SYSTEM,
            user_prompt=user_prompt,
            groq_client=groq_client,
            model=model,
        )

        if result is None:
            logger.warning("[Stage C] LLM call failed for %s → %s", src_id, tgt_id)
            failed += 1
            continue

        if result.get("confirmed") and result.get("evidence_quote", "").strip():
            edges.append(GraphEdgeRecord(
                source_id=src_id,
                target_id=tgt_id,
                relation="PREREQUISITE_OF",
                derivation="llm",
                evidence=result["evidence_quote"],
                confidence=float(result.get("confidence", 0.75)),
            ))
            confirmed += 1
            logger.info(
                "[Stage C] CONFIRMED PREREQUISITE: %s → %s (conf=%.2f)",
                src_id, tgt_id, result.get("confidence", 0.75),
            )
        else:
            rejected += 1
            logger.info(
                "[Stage C] REJECTED prerequisite: %s → %s | reason=%s",
                src_id, tgt_id, result.get("reasoning", "no evidence"),
            )

        # Rate limit: 1 call per 2 seconds to respect Groq limits
        time.sleep(2)

    logger.info(
        "[Stage C] Prerequisites: %d confirmed, %d rejected, %d failed",
        confirmed, rejected, failed,
    )

    # ── Part 2: Additional intra-domain RELATED_TO edges ──
    # For each domain, find pairs of concepts that are likely related
    # (but not yet covered by structural edges) and ask the LLM.
    # We only check pairs within the same domain to keep this bounded.
    # We limit to pairs where both concepts have at least 2 chunks.

    INTRA_DOMAIN_RELATED_PAIRS: List[Tuple[str, str]] = [
        # dbms intra-domain pairs worth checking
        ("dbms_transactions",   "dbms_acid-properties"),
        ("dbms_indexing",       "dbms_sql-joins"),
        ("dbms_keys",           "dbms_sql-joins"),
        # dsa intra-domain pairs
        ("dsa_tree",            "dsa_graph"),
        ("dsa_array",           "dsa_string"),
        ("dsa_sorting",         "dsa_binary"),
        ("dsa_stack",           "dsa_recursion"),
        ("dsa_heap",            "dsa_sorting"),
        # oop intra-domain
        ("oop_abstraction",     "oop_encapsulation"),
        ("oop_polymorphism",    "oop_interfaces-abstract-classes"),
        # os intra-domain
        ("os_deadlock",         "os_scheduling-algorithms"),
        # system-design
        ("sd_caching",          "sd_consistent-hashing"),
        ("sd_load-balancing",   "sd_cap-theorem"),
        # ml-dl
        ("mldl_decision-trees", "mldl_neural-networks"),
        ("mldl_bias-variance-tradeoff", "mldl_decision-trees"),
    ]

    related_confirmed = 0
    related_rejected = 0

    logger.info(
        "[Stage C] Processing %d intra-domain RELATED_TO pairs via LLM...",
        len(INTRA_DOMAIN_RELATED_PAIRS),
    )

    for src_id, tgt_id in INTRA_DOMAIN_RELATED_PAIRS:
        src_concept = CONCEPT_ID_MAP.get(src_id)
        tgt_concept = CONCEPT_ID_MAP.get(tgt_id)
        if not src_concept or not tgt_concept:
            continue

        src_chunks = _load_concept_chunks(processed_dir, src_concept.domain_id, src_concept.name)
        tgt_chunks = _load_concept_chunks(processed_dir, tgt_concept.domain_id, tgt_concept.name)
        if not src_chunks or not tgt_chunks:
            continue

        user_prompt = _build_related_prompt(
            concept_a=src_concept.name, chunks_a=src_chunks,
            concept_b=tgt_concept.name, chunks_b=tgt_chunks,
        )

        result = _call_llm_for_edge(
            system_prompt=_RELATED_PROMPT_SYSTEM,
            user_prompt=user_prompt,
            groq_client=groq_client,
            model=model,
        )

        if result and result.get("confirmed") and result.get("evidence_quote", "").strip():
            # Bidirectional
            for s, t in [(src_id, tgt_id), (tgt_id, src_id)]:
                edges.append(GraphEdgeRecord(
                    source_id=s,
                    target_id=t,
                    relation="RELATED_TO",
                    derivation="llm",
                    evidence=result["evidence_quote"],
                    confidence=float(result.get("confidence", 0.75)),
                ))
            related_confirmed += 1
            logger.info("[Stage C] CONFIRMED RELATED_TO: %s ↔ %s", src_id, tgt_id)
        else:
            related_rejected += 1
            logger.info("[Stage C] REJECTED RELATED_TO: %s ↔ %s", src_id, tgt_id)

        time.sleep(2)

    logger.info(
        "[Stage C] RELATED_TO: %d confirmed, %d rejected",
        related_confirmed, related_rejected,
    )

    return edges


# ── Graph deduplication ───────────────────────────────────────────────────────

def deduplicate_edges(edges: List[GraphEdgeRecord]) -> List[GraphEdgeRecord]:
    """Remove exact duplicate (source, target, relation) triples, keeping higher confidence."""
    best: Dict[Tuple[str, str, str], GraphEdgeRecord] = {}
    for e in edges:
        key = (e.source_id, e.target_id, e.relation)
        if key not in best or e.confidence > best[key].confidence:
            best[key] = e
    result = list(best.values())
    dropped = len(edges) - len(result)
    if dropped:
        logger.info("[Dedup] Removed %d duplicate edges", dropped)
    return result


# ── Main build function ───────────────────────────────────────────────────────

def build_graph(dry_run: bool = False, output_path: Optional[str] = None) -> dict:
    """
    Run the complete graph construction pipeline.

    Parameters
    ----------
    dry_run     : If True, skip Stage C (no LLM calls). Stages A+B only.
    output_path : Override the default output path (data/graph_data.json).

    Returns
    -------
    dict — the complete GraphData as a serialisable dict.
    """
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

    processed = _processed_dir()
    out_path = output_path or _output_path()

    logger.info("=" * 60)
    logger.info("SmartInterview — Knowledge Graph Construction Pipeline")
    logger.info("=" * 60)
    logger.info("processed_dir : %s", processed)
    logger.info("output_path   : %s", out_path)
    logger.info("dry_run       : %s", dry_run)

    all_nodes: List[GraphNode] = []
    all_edges: List[GraphEdgeRecord] = []

    # ── Stage A ──
    logger.info("\n[Stage A] Building metadata-derived nodes and edges...")
    meta_nodes, meta_edges = build_metadata_edges(processed)
    skill_nodes, skill_edges = build_skill_maps()
    all_nodes.extend(meta_nodes)
    all_nodes.extend(skill_nodes)
    all_edges.extend(meta_edges)
    all_edges.extend(skill_edges)

    # ── Stage B ──
    logger.info("\n[Stage B] Building structural RELATED_TO edges from filenames...")
    structural_edges = build_structural_edges()
    all_edges.extend(structural_edges)

    # ── Stage C ──
    llm_edges: List[GraphEdgeRecord] = []
    if not dry_run:
        logger.info("\n[Stage C] Building LLM-confirmed prerequisite and related edges...")
        try:
            from app.services.question_service import get_groq_client, get_groq_model_name
            groq_client = get_groq_client()
            model = get_groq_model_name()
            llm_edges = build_llm_edges(processed, groq_client, model)
        except Exception as e:
            logger.error("[Stage C] Failed to run LLM extraction: %s", e)
            logger.warning("[Stage C] Continuing without LLM edges.")
    else:
        logger.info("\n[Stage C] Skipped (dry_run=True)")

    all_edges.extend(llm_edges)

    # ── Deduplication ──
    all_edges = deduplicate_edges(all_edges)

    # ── Self-reference check ──
    self_refs = [e for e in all_edges if e.source_id == e.target_id]
    if self_refs:
        logger.warning("Removing %d self-referencing edges", len(self_refs))
        all_edges = [e for e in all_edges if e.source_id != e.target_id]

    # ── Build stats ──
    node_types: Dict[str, int] = {}
    for n in all_nodes:
        node_types[n.type] = node_types.get(n.type, 0) + 1

    edge_types: Dict[str, int] = {}
    edge_by_derivation: Dict[str, int] = {}
    for e in all_edges:
        edge_types[e.relation] = edge_types.get(e.relation, 0) + 1
        edge_by_derivation[e.derivation] = edge_by_derivation.get(e.derivation, 0) + 1

    stats = {
        "total_nodes": len(all_nodes),
        "total_edges": len(all_edges),
        "node_types": node_types,
        "edge_types": edge_types,
        "edge_by_derivation": edge_by_derivation,
    }

    build_meta = {
        "dry_run": dry_run,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stages_run": ["A", "B"] + ([] if dry_run else ["C"]),
    }

    graph_data = {
        "nodes": [n.to_dict() for n in all_nodes],
        "edges": [e.to_dict() for e in all_edges],
        "stats": stats,
        "build_meta": build_meta,
    }

    # ── Write output ──
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)

    logger.info("\n" + "=" * 60)
    logger.info("GRAPH CONSTRUCTION COMPLETE")
    logger.info("=" * 60)
    logger.info("Total nodes  : %d", stats["total_nodes"])
    logger.info("  Domain     : %d", node_types.get("Domain", 0))
    logger.info("  Concept    : %d", node_types.get("Concept", 0))
    logger.info("  Chunk      : %d", node_types.get("KnowledgeChunk", 0))
    logger.info("  Skill      : %d", node_types.get("Skill", 0))
    logger.info("Total edges  : %d", stats["total_edges"])
    for rel, count in sorted(edge_types.items()):
        logger.info("  %-20s : %d", rel, count)
    logger.info("By derivation:")
    for deriv, count in sorted(edge_by_derivation.items()):
        logger.info("  %-12s : %d", deriv, count)
    logger.info("Output       : %s", out_path)
    logger.info("=" * 60)

    return graph_data


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SmartInterview — Knowledge Graph Construction Pipeline"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run only Stages A+B (no LLM calls). Outputs a partial graph.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Override output path for graph_data.json",
    )
    args = parser.parse_args()

    result = build_graph(dry_run=args.dry_run, output_path=args.output)

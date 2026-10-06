"""
SmartInterview — Knowledge Graph Retriever (Phase 6)

Implements relationship-aware graph retrieval combining:
  1. Seed Concept Identification:
     - Explicit concept name or ID
     - Weak topic targeting
     - Skill-to-domain-to-concept graph resolution
     - Query lexical matching against concept catalogue
  2. Multi-Hop Graph Traversal:
     - Prerequisite discovery (Concept P ──PREREQUISITE_OF──> Seed)
     - Dependent discovery (Seed ──PREREQUISITE_OF──> Concept D)
     - Related concept traversal (Seed ──RELATED_TO──> Concept R)
     - Weak-topic foundational reinforcement (prerequisite remediation)
  3. Bloom's Taxonomy Adaptation:
     - Remember / Understand: boosts foundational prerequisites and core definitions
     - Apply: balanced practical application context
     - Analyze / Evaluate / Create: boosts related tradeoff concepts and dependent systems
  4. Context Scoring & Ranking:
     - Combines graph proximity, relationship type, Bloom modifier, and query relevance.
     - Produces uniform List[RetrievalResult] with rich graph traversal provenance.
"""

from __future__ import annotations

import re
import math
import logging
from typing import List, Optional, Dict, Set, Tuple, Any
from collections import defaultdict

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.graph_store import BaseGraphStore, get_graph_store
from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE

logger = logging.getLogger(__name__)


# ── Bloom Taxonomy Weight Modifiers ───────────────────────────────────

_BLOOM_WEIGHTS: Dict[str, Dict[str, float]] = {
    "remember":   {"seed": 1.0, "prerequisite": 0.95, "related": 0.40, "dependent": 0.30},
    "understand": {"seed": 1.0, "prerequisite": 0.90, "related": 0.50, "dependent": 0.40},
    "apply":      {"seed": 1.0, "prerequisite": 0.70, "related": 0.75, "dependent": 0.60},
    "analyze":    {"seed": 0.9, "prerequisite": 0.50, "related": 1.00, "dependent": 0.85},
    "evaluate":   {"seed": 0.85, "prerequisite": 0.45, "related": 1.00, "dependent": 0.90},
    "create":     {"seed": 0.80, "prerequisite": 0.40, "related": 1.00, "dependent": 0.95},
}

_DEFAULT_BLOOM_WEIGHTS = {"seed": 1.0, "prerequisite": 0.80, "related": 0.70, "dependent": 0.60}


# ── Tokenizer / Lexical Helper ────────────────────────────────────────

def _tokenize(text: str) -> Set[str]:
    """Extract lowercase alpha tokens for matching."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _token_overlap_score(query_tokens: Set[str], chunk_text: str) -> float:
    """Compute normalized token overlap score between query and chunk."""
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(chunk_text[:1200])
    if not chunk_tokens:
        return 0.0
    common = query_tokens.intersection(chunk_tokens)
    return len(common) / (len(query_tokens) + 2)


# ── Graph Retriever Implementation ───────────────────────────────────

class GraphRetriever(BaseRetriever):
    """
    Knowledge Graph-driven retriever. Traverses semantic concept networks,
    prerequisite chains, and related concept links to provide relationship-aware context.
    """

    def __init__(self, graph_store: Optional[BaseGraphStore] = None):
        self.graph_store = graph_store or get_graph_store()
        self._concept_catalogue = {c.id: c for c in CANONICAL_CONCEPT_CATALOGUE}
        self._concept_names = {c.name.lower(): c.id for c in CANONICAL_CONCEPT_CATALOGUE}

    def retrieve(
        self,
        query: str,
        skill: str,
        domains: Optional[List[str]] = None,
        top_k: int = 3,
        concept: Optional[str] = None,
        weak_topic: Optional[str] = None,
        bloom_level: Optional[str] = None,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Execute relationship-aware graph retrieval.

        Parameters
        ----------
        query       : Semantic question or query string
        skill       : Target candidate skill (e.g. 'Python', 'SQL', 'DBMS')
        domains     : Canonical domain filter list (e.g. ['dbms'])
        top_k       : Maximum number of chunks to return
        concept     : Explicit concept name or ID to anchor on (optional)
        weak_topic  : Candidate's identified weak topic for remediation (optional)
        bloom_level : Target cognitive Bloom level (e.g. 'Analyze', 'Remember')
        """
        query_tokens = _tokenize(query)

        # 1. Resolve seed concepts
        seed_concept_ids = self._identify_seed_concepts(
            query=query,
            query_tokens=query_tokens,
            skill=skill,
            domains=domains,
            explicit_concept=concept,
            weak_topic=weak_topic,
        )

        if not seed_concept_ids:
            logger.debug("[GraphRetriever] No seed concepts identified for query '%s'", query)
            return []

        # 2. Graph expansion (Prerequisites, Related, Dependents, Weak-Topic Remediation)
        expanded_nodes = self._expand_graph(
            seed_concept_ids=seed_concept_ids,
            weak_topic=weak_topic,
            bloom_level=bloom_level,
            domains=domains,
        )

        # 3. Retrieve chunks and score
        candidate_chunks = self._score_chunks(
            expanded_nodes=expanded_nodes,
            query_tokens=query_tokens,
            bloom_level=bloom_level,
        )

        # 4. Sort and diversify across concepts
        candidate_chunks.sort(key=lambda x: x.final_score, reverse=True)

        if len(expanded_nodes) > 1 and top_k > 1:
            # Concept-diverse selection: prevent a single concept from crowding out prerequisite/related concepts
            max_per_concept = max(1, math.ceil(top_k / 2))
            concept_counts: Dict[str, int] = defaultdict(int)
            diversified: List[RetrievalResult] = []
            remaining: List[RetrievalResult] = []

            for chunk in candidate_chunks:
                cid = chunk.metadata.get("concept_id", "")
                if concept_counts[cid] < max_per_concept:
                    diversified.append(chunk)
                    concept_counts[cid] += 1
                else:
                    remaining.append(chunk)

            if len(diversified) < top_k:
                diversified.extend(remaining[:(top_k - len(diversified))])

            results = diversified[:top_k]
        else:
            results = candidate_chunks[:top_k]

        logger.debug(
            "[GraphRetriever] Retrieved %d chunks (seeds=%s, bloom=%s, weak=%s)",
            len(results),
            seed_concept_ids,
            bloom_level,
            weak_topic,
        )
        return results

    # ── Internal Helpers ──────────────────────────────────────────────

    def _identify_seed_concepts(
        self,
        query: str,
        query_tokens: Set[str],
        skill: str,
        domains: Optional[List[str]],
        explicit_concept: Optional[str],
        weak_topic: Optional[str],
    ) -> List[str]:
        """Identify anchor concept IDs from inputs and query analysis."""
        seed_ids: List[str] = []
        domain_set = set(domains) if domains else None

        # 1. Explicit concept parameter
        if explicit_concept:
            resolved = self._resolve_concept_id(explicit_concept)
            if resolved:
                seed_ids.append(resolved)

        # 2. Weak topic parameter
        if weak_topic:
            resolved_weak = self._resolve_concept_id(weak_topic)
            if resolved_weak and resolved_weak not in seed_ids:
                seed_ids.append(resolved_weak)

        # 3. Textual matching against concept catalogue
        query_lower = query.lower()
        scored_matches: List[Tuple[float, str]] = []

        for cid, cobj in self._concept_catalogue.items():
            if domain_set and cobj.domain_id not in domain_set:
                continue

            cname = cobj.name.lower()
            cname_clean = cname.replace("-vs-", " ").replace("-", " ")
            c_tokens = _tokenize(cname_clean)

            score = 0.0
            # Exact phrase match
            if cname in query_lower or cname_clean in query_lower:
                score += 3.0
            # Token overlap
            overlap = query_tokens.intersection(c_tokens)
            if overlap:
                score += len(overlap) * 1.0

            if score > 0.0:
                scored_matches.append((score, cid))

        scored_matches.sort(key=lambda x: x[0], reverse=True)
        for _, cid in scored_matches[:3]:
            if cid not in seed_ids:
                seed_ids.append(cid)

        # 4. Fallback to skill concepts if still empty
        if not seed_ids and skill:
            skill_concepts = self.graph_store.get_concepts_by_skill(skill)
            if domain_set:
                skill_concepts = [c for c in skill_concepts if c.get("domain_id") in domain_set]
            for sc in skill_concepts[:2]:
                if sc["id"] not in seed_ids:
                    seed_ids.append(sc["id"])

        return seed_ids

    def _resolve_concept_id(self, name_or_id: str) -> Optional[str]:
        """Resolve a freeform concept name or ID to canonical ID."""
        cleaned = name_or_id.lower().strip()
        if cleaned in self._concept_catalogue:
            return cleaned
        if cleaned in self._concept_names:
            return self._concept_names[cleaned]
        # Search by name match
        for cid, c in self._concept_catalogue.items():
            if c.name.lower() == cleaned or cleaned in c.name.lower():
                return cid
        return None

    def _expand_graph(
        self,
        seed_concept_ids: List[str],
        weak_topic: Optional[str],
        bloom_level: Optional[str],
        domains: Optional[List[str]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Perform 1-hop traversal to discover prerequisites, related concepts,
        and dependents.
        """
        domain_set = set(domains) if domains else None
        expanded: Dict[str, Dict[str, Any]] = {}

        for seed_id in seed_concept_ids:
            seed_node = self.graph_store.get_concept(seed_id)
            if not seed_node:
                continue

            expanded[seed_id] = {
                "node": seed_node,
                "role": "seed",
                "traversal_path": f"anchor({seed_id})",
                "remediation": False,
                "confidence": 1.0,
                "evidence": "",
            }

            # 1. Prerequisite traversal (P ──PREREQUISITE_OF──> Seed)
            prereqs = self.graph_store.get_prerequisites(seed_id)
            for p in prereqs:
                pid = p["id"]
                if domain_set and p.get("domain_id") not in domain_set:
                    continue
                if pid not in expanded:
                    is_remediation = (weak_topic is not None and (
                        seed_id == weak_topic or seed_node.get("name") == weak_topic
                    ))
                    expanded[pid] = {
                        "node": p,
                        "role": "prerequisite",
                        "traversal_path": f"{pid} --PREREQUISITE_OF--> {seed_id}",
                        "remediation": is_remediation,
                        "confidence": float(p.get("edge", {}).get("confidence", 0.8)),
                        "evidence": p.get("edge", {}).get("evidence", ""),
                    }

            # 2. Related concepts traversal (Seed ──RELATED_TO──> R)
            related = self.graph_store.get_related_concepts(seed_id)
            for r in related:
                rid = r["id"]
                if domain_set and r.get("domain_id") not in domain_set:
                    continue
                if rid not in expanded:
                    expanded[rid] = {
                        "node": r,
                        "role": "related",
                        "traversal_path": f"{seed_id} --RELATED_TO--> {rid}",
                        "remediation": False,
                        "confidence": float(r.get("edge", {}).get("confidence", 0.85)),
                        "evidence": r.get("edge", {}).get("evidence", ""),
                    }

            # 3. Dependents traversal (Seed ──PREREQUISITE_OF──> D)
            dependents = self.graph_store.get_dependents(seed_id)
            for d in dependents:
                did = d["id"]
                if domain_set and d.get("domain_id") not in domain_set:
                    continue
                if did not in expanded:
                    expanded[did] = {
                        "node": d,
                        "role": "dependent",
                        "traversal_path": f"{seed_id} --PREREQUISITE_OF--> {did}",
                        "remediation": False,
                        "confidence": float(d.get("edge", {}).get("confidence", 0.75)),
                        "evidence": d.get("edge", {}).get("evidence", ""),
                    }

        return expanded

    def _score_chunks(
        self,
        expanded_nodes: Dict[str, Dict[str, Any]],
        query_tokens: Set[str],
        bloom_level: Optional[str],
    ) -> List[RetrievalResult]:
        """
        Fetch chunks attached to expanded nodes and compute relationship-aware scores.
        """
        bloom_key = (bloom_level or "understand").lower().strip()
        bloom_mod = _BLOOM_WEIGHTS.get(bloom_key, _DEFAULT_BLOOM_WEIGHTS)

        results: List[RetrievalResult] = []

        for cid, meta in expanded_nodes.items():
            role = meta["role"]
            is_remediation = meta["remediation"]
            edge_conf = meta["confidence"]
            traversal_path = meta["traversal_path"]
            concept_node = meta["node"]

            # Role base multiplier
            role_weight = bloom_mod.get(role, 0.70)
            if is_remediation:
                # Remediation boost for addressing candidate weaknesses
                role_weight *= 1.35

            chunks = self.graph_store.get_chunks_for_concept(cid)
            for chunk in chunks:
                chunk_text = chunk.get("text", "")
                lexical_sim = _token_overlap_score(query_tokens, chunk_text)

                # Composite score: 65% Graph Proximity/Provenance + 35% Lexical Relevance
                graph_proximity = role_weight * edge_conf
                final_score = (0.65 * graph_proximity) + (0.35 * lexical_sim)

                res = RetrievalResult(
                    chunk_id=chunk["id"],
                    text=chunk_text,
                    domain=chunk.get("domain_id") or concept_node.get("domain_id", ""),
                    concept=concept_node.get("name", cid),
                    source=chunk.get("source", "knowledge_base"),
                    source_url=chunk.get("source_url", ""),
                    vector_score=None,
                    keyword_score=None,
                    graph_score=round(final_score, 4),
                    final_score=round(final_score, 4),
                    retriever="graph",
                    metadata={
                        "concept_id": cid,
                        "role": role,
                        "remediation": is_remediation,
                        "traversal_path": traversal_path,
                        "confidence": edge_conf,
                        "bloom_level": bloom_level or "unspecified",
                        "evidence": meta.get("evidence", ""),
                    },
                )
                results.append(res)

        return results

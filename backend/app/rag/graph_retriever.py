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
import time
import logging
from typing import List, Optional, Dict, Set, Tuple, Any
from collections import defaultdict

from app.rag.base_retriever import BaseRetriever
from app.rag.retrieval_result import RetrievalResult
from app.rag.graph_store import BaseGraphStore, get_graph_store
from app.rag.graph_schema import CANONICAL_CONCEPT_CATALOGUE
from app.rag.canonical_resolver import get_canonical_resolver, CanonicalChunkResolver

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
    if not text or not isinstance(text, str):
        return set()
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
    Resolves chunks to canonical full text (Phase 4).
    """

    def __init__(
        self,
        graph_store: Optional[BaseGraphStore] = None,
        chunk_resolver: Optional[CanonicalChunkResolver] = None,
    ):
        self.graph_store = graph_store or get_graph_store()
        self._resolver = chunk_resolver or get_canonical_resolver()
        self._concept_catalogue = {c.id: c for c in CANONICAL_CONCEPT_CATALOGUE}
        self._concept_names = {c.name.lower(): c.id for c in CANONICAL_CONCEPT_CATALOGUE}

    def get_stats(self) -> Dict[str, Any]:
        """Return operational statistics about the graph retriever and underlying store."""
        store_stats = self.graph_store.get_stats()
        return {
            "retriever": self.name,
            "catalogue_concepts_count": len(self._concept_catalogue),
            "store_stats": store_stats,
            "canonical_resolver_indexed": getattr(self._resolver, "is_indexed", True),
        }

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
        **kwargs    : Optional extra parameters (weak_topics list, concept_name, max_hops)
        """
        start_time = time.perf_counter()

        if top_k <= 0:
            return []

        # Sanitize query
        query_str = "" if query is None else (query if isinstance(query, str) else str(query))
        query_tokens = _tokenize(query_str)

        # Normalize domain filter
        domains_clean = (
            [d.lower().strip() for d in domains if d and isinstance(d, str)]
            if domains
            else None
        )

        # Support alias kwargs: concept_name, concept
        effective_concept = concept or kwargs.get("concept") or kwargs.get("concept_name")

        # Support weak_topics list in kwargs alongside singular weak_topic
        weak_topics_list: List[str] = []
        if weak_topic:
            weak_topics_list.append(weak_topic)
        if "weak_topics" in kwargs:
            raw_wts = kwargs["weak_topics"]
            if isinstance(raw_wts, list):
                for wt in raw_wts:
                    if wt and isinstance(wt, str) and wt not in weak_topics_list:
                        weak_topics_list.append(wt)
            elif isinstance(raw_wts, str) and raw_wts and raw_wts not in weak_topics_list:
                weak_topics_list.append(raw_wts)

        # Normalize bloom_level
        effective_bloom = bloom_level or kwargs.get("bloom_level")
        bloom_str = None
        if effective_bloom:
            bloom_str = (
                effective_bloom.id
                if hasattr(effective_bloom, "id")
                else str(effective_bloom).lower().strip()
            )
            bloom_str = bloom_str.replace("bloom_", "").replace("level_", "").strip()

        # Configurable traversal hops (default 1)
        max_hops = int(kwargs.get("max_hops", 1))

        # 1. Resolve seed concepts
        seed_concept_ids = self._identify_seed_concepts(
            query=query_str,
            query_tokens=query_tokens,
            skill=skill,
            domains=domains_clean,
            explicit_concept=effective_concept,
            weak_topics=weak_topics_list,
        )

        if not seed_concept_ids:
            logger.debug("[GraphRetriever] No seed concepts identified for query '%s'", query_str)
            return []

        # 2. Graph expansion (Prerequisites, Related, Dependents, Weak-Topic Remediation)
        expanded_nodes = self._expand_graph(
            seed_concept_ids=seed_concept_ids,
            weak_topics=weak_topics_list,
            bloom_level=bloom_str,
            domains=domains_clean,
            max_hops=max_hops,
        )

        # 3. Retrieve chunks and score
        candidate_chunks = self._score_chunks(
            expanded_nodes=expanded_nodes,
            query_tokens=query_tokens,
            bloom_level=bloom_str,
        )

        # 4. Deduplicate across multi-path expansion and sort
        candidate_chunks = self._resolver.deduplicate_results(candidate_chunks)
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

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        for r in results:
            r.metadata["latency_ms"] = round(elapsed_ms, 2)

        logger.debug(
            "[GraphRetriever] Retrieved %d chunks (seeds=%s, bloom=%s, weak=%s, latency=%.2fms)",
            len(results),
            seed_concept_ids,
            bloom_str,
            weak_topics_list,
            elapsed_ms,
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
        weak_topics: List[str],
    ) -> List[str]:
        """Identify anchor concept IDs from inputs and query analysis."""
        seed_ids: List[str] = []
        domain_set = set(domains) if domains else None

        # 1. Explicit concept parameter
        if explicit_concept:
            resolved = self._resolve_concept_id(explicit_concept)
            if resolved and resolved not in seed_ids:
                if domain_set:
                    cobj = self._concept_catalogue.get(resolved)
                    if cobj and cobj.domain_id.lower().strip() in domain_set:
                        seed_ids.append(resolved)
                else:
                    seed_ids.append(resolved)

        # 2. Weak topic parameters
        for wt in weak_topics:
            resolved_weak = self._resolve_concept_id(wt)
            if resolved_weak and resolved_weak not in seed_ids:
                if domain_set:
                    cobj = self._concept_catalogue.get(resolved_weak)
                    if cobj and cobj.domain_id.lower().strip() in domain_set:
                        seed_ids.append(resolved_weak)
                else:
                    seed_ids.append(resolved_weak)

        # 3. Textual matching against concept catalogue
        query_lower = query.lower()
        if query_lower.strip():
            scored_matches: List[Tuple[float, str]] = []

            for cid, cobj in self._concept_catalogue.items():
                if domain_set and cobj.domain_id.lower().strip() not in domain_set:
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
                skill_concepts = [
                    c for c in skill_concepts
                    if c.get("domain_id", "").lower().strip() in domain_set
                ]
            for sc in skill_concepts[:2]:
                if sc["id"] not in seed_ids:
                    seed_ids.append(sc["id"])

        return seed_ids

    def _resolve_concept_id(self, name_or_id: str) -> Optional[str]:
        """Resolve a freeform concept name or ID to canonical ID."""
        if not name_or_id or not isinstance(name_or_id, str):
            return None
        cleaned = name_or_id.lower().strip()
        if not cleaned:
            return None

        # 1. Exact catalog ID
        if cleaned in self._concept_catalogue:
            return cleaned

        # 2. Exact concept name
        if cleaned in self._concept_names:
            return self._concept_names[cleaned]

        # 3. Normalized comparison (stripping hyphens, underscores, dots, slashes)
        normalized = re.sub(r"[-_./\s]+", " ", cleaned).strip()
        for cid, c in self._concept_catalogue.items():
            c_norm = re.sub(r"[-_./\s]+", " ", c.name.lower()).strip()
            cid_norm = re.sub(r"[-_./\s]+", " ", cid.lower()).strip()
            if c_norm == normalized or cid_norm == normalized:
                return cid

        # 4. Substring / partial match
        for cid, c in self._concept_catalogue.items():
            c_norm = re.sub(r"[-_./\s]+", " ", c.name.lower()).strip()
            if normalized in c_norm or c_norm in normalized:
                return cid

        return None

    def _expand_graph(
        self,
        seed_concept_ids: List[str],
        weak_topics: List[str],
        bloom_level: Optional[str],
        domains: Optional[List[str]],
        max_hops: int = 1,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Perform relationship-aware traversal to discover prerequisites, related concepts,
        dependents, and weak-topic remediation paths. Supports multi-hop traversal.
        """
        domain_set = set(domains) if domains else None
        expanded: Dict[str, Dict[str, Any]] = {}

        # Resolve all weak topic anchors
        resolved_weak_ids: Set[str] = set()
        for wt in weak_topics:
            rwt = self._resolve_concept_id(wt)
            if rwt:
                resolved_weak_ids.add(rwt)

        for seed_id in seed_concept_ids:
            seed_node = self.graph_store.get_concept(seed_id)
            if not seed_node:
                continue
            if domain_set and seed_node.get("domain_id", "").lower().strip() not in domain_set:
                continue

            expanded[seed_id] = {
                "node": seed_node,
                "role": "seed",
                "traversal_path": f"anchor({seed_id})",
                "remediation": False,
                "confidence": 1.0,
                "evidence": "",
            }

            # Seed is a weak topic target
            is_seed_weak = (
                seed_id in resolved_weak_ids
                or seed_node.get("name") in weak_topics
                or any(wt.lower().strip() == seed_id.lower().strip() for wt in weak_topics)
            )

            # 1. Prerequisite traversal (P ──PREREQUISITE_OF──> Seed)
            prereqs = self.graph_store.get_prerequisites(seed_id)
            for p in prereqs:
                pid = p["id"]
                if domain_set and p.get("domain_id", "").lower().strip() not in domain_set:
                    continue
                if pid not in expanded:
                    p_conf = float(p.get("edge", {}).get("confidence", 0.8))
                    expanded[pid] = {
                        "node": p,
                        "role": "prerequisite",
                        "traversal_path": f"{pid} --PREREQUISITE_OF--> {seed_id}",
                        "remediation": is_seed_weak,
                        "confidence": p_conf,
                        "evidence": p.get("edge", {}).get("evidence", ""),
                    }

                    # Optional 2-hop prerequisite chain
                    if max_hops >= 2:
                        p2_prereqs = self.graph_store.get_prerequisites(pid)
                        for p2 in p2_prereqs:
                            p2_id = p2["id"]
                            if domain_set and p2.get("domain_id", "").lower().strip() not in domain_set:
                                continue
                            if p2_id not in expanded:
                                p2_conf = round(p_conf * float(p2.get("edge", {}).get("confidence", 0.8)) * 0.9, 3)
                                expanded[p2_id] = {
                                    "node": p2,
                                    "role": "prerequisite",
                                    "traversal_path": f"{p2_id} --PREREQUISITE_OF--> {pid} --PREREQUISITE_OF--> {seed_id}",
                                    "remediation": is_seed_weak,
                                    "confidence": p2_conf,
                                    "evidence": p2.get("edge", {}).get("evidence", ""),
                                }

            # 2. Related concepts traversal (Seed ──RELATED_TO──> R)
            related = self.graph_store.get_related_concepts(seed_id)
            for r in related:
                rid = r["id"]
                if domain_set and r.get("domain_id", "").lower().strip() not in domain_set:
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
                if domain_set and d.get("domain_id", "").lower().strip() not in domain_set:
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
                chunk_id = chunk["id"]
                canonical = self._resolver.resolve_chunk(chunk_id)

                if canonical is not None:
                    chunk_text = canonical.text
                    chunk_domain = canonical.domain or chunk.get("domain_id") or concept_node.get("domain_id", "")
                    chunk_concept = canonical.concept or concept_node.get("name", cid)
                    chunk_source = canonical.source or chunk.get("source", "knowledge_base")
                    chunk_source_url = canonical.source_url or chunk.get("source_url", "")
                    is_full_text = True
                    missing_canonical = False
                else:
                    logger.warning("[GraphRetriever] Missing canonical chunk for ID %s", chunk_id)
                    chunk_text = chunk.get("text", "")
                    chunk_domain = chunk.get("domain_id") or concept_node.get("domain_id", "")
                    chunk_concept = concept_node.get("name", cid)
                    chunk_source = chunk.get("source", "knowledge_base")
                    chunk_source_url = chunk.get("source_url", "")
                    is_full_text = False
                    missing_canonical = True

                lexical_sim = _token_overlap_score(query_tokens, chunk_text)

                # Composite score: 65% Graph Proximity/Provenance + 35% Lexical Relevance
                graph_proximity = role_weight * edge_conf
                final_score = (0.65 * graph_proximity) + (0.35 * lexical_sim)

                res = RetrievalResult(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    domain=chunk_domain,
                    concept=chunk_concept,
                    source=chunk_source,
                    source_url=chunk_source_url,
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
                        "is_full_text": is_full_text,
                        "canonical_resolved": is_full_text,
                        "missing_canonical": missing_canonical,
                        "char_count": len(chunk_text),
                    },
                )
                results.append(res)

        return results

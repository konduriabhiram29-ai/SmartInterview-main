"""
SmartInterview — Knowledge Graph Validation Engine (Phase 4)

Provides comprehensive structural, semantic, and topological integrity checks
on the generated knowledge graph (data/graph_data.json) prior to ingestion
into graph storage (Phase 5) or retrieval (Phase 6).

Checks performed:
  1. Node uniqueness (no duplicate IDs)
  2. Edge uniqueness (no duplicate source/target/relation triples)
  3. Supported node types (Domain, Concept, KnowledgeChunk, Skill)
  4. Supported relationship types (CONTAINS, HAS_CHUNK, MAPS_TO, PREREQUISITE_OF, RELATED_TO)
  5. Supported derivation strategies (metadata, structural, llm)
  6. Endpoint existence (no dangling source_id or target_id)
  7. No self-referencing relationships (source_id != target_id)
  8. Domain consistency (every Concept belongs to a canonical Domain; Chunks match Concept domain)
  9. Orphan concept check (every Concept is reachable via CONTAINS)
 10. Orphan chunk check (every KnowledgeChunk is reachable via HAS_CHUNK)
 11. Evidence verification (every LLM/inferred relationship has non-empty evidence quote and valid confidence)
 12. Prerequisite DAG acyclicity (PREREQUISITE_OF edges must form a Directed Acyclic Graph)
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

from app.rag.graph_schema import (
    NodeType,
    RelationType,
    DerivationStrategy,
    CANONICAL_DOMAIN_IDS,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    severity: str        # "ERROR" or "WARNING"
    check: str           # Name of the check
    message: str         # Detailed explanation
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    """Consolidated report produced by the validation engine."""
    is_valid: bool
    total_nodes: int
    total_edges: int
    node_types: Dict[str, int]
    edge_types: Dict[str, int]
    edge_by_derivation: Dict[str, int]
    issues: List[ValidationIssue]
    orphan_concepts: List[str]
    orphan_chunks: List[str]
    invalid_edges: List[dict]
    prerequisite_acyclic: bool

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def format_text_report(self) -> str:
        """Format report into the standardized text presentation."""
        lines = []
        lines.append("=" * 60)
        lines.append("SMARTINTERVIEW — KNOWLEDGE GRAPH VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append("Nodes:")
        lines.append(f"  Total nodes     : {self.total_nodes}")
        for ntype, count in sorted(self.node_types.items()):
            lines.append(f"  {ntype:<16}: {count}")
        lines.append("")
        lines.append("Edges:")
        lines.append(f"  Total edges     : {self.total_edges}")
        for rtype, count in sorted(self.edge_types.items()):
            lines.append(f"  {rtype:<16}: {count}")
        lines.append("")
        lines.append("By Derivation:")
        for deriv, count in sorted(self.edge_by_derivation.items()):
            lines.append(f"  {deriv:<16}: {count}")
        lines.append("")
        lines.append("Integrity Summary:")
        lines.append(f"  Invalid edges   : {len(self.invalid_edges)}")
        lines.append(f"  Orphan concepts : {len(self.orphan_concepts)}")
        lines.append(f"  Orphan chunks   : {len(self.orphan_chunks)}")
        lines.append(f"  Prereq DAG Acyclic: {self.prerequisite_acyclic}")
        lines.append(f"  Total Errors    : {self.error_count}")
        lines.append(f"  Total Warnings  : {self.warning_count}")
        lines.append("")
        if self.issues:
            lines.append("Issues Details:")
            for idx, issue in enumerate(self.issues, 1):
                lines.append(f"  [{issue.severity}] #{idx} ({issue.check}): {issue.message}")
            lines.append("")
        lines.append("Status: " + ("PASS (VALID GRAPH) [OK]" if self.is_valid else "FAIL (STRUCTURAL ISSUES DETECTED) [ERROR]"))
        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "node_types": self.node_types,
            "edge_types": self.edge_types,
            "edge_by_derivation": self.edge_by_derivation,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "orphan_concepts_count": len(self.orphan_concepts),
            "orphan_chunks_count": len(self.orphan_chunks),
            "invalid_edges_count": len(self.invalid_edges),
            "prerequisite_acyclic": self.prerequisite_acyclic,
            "issues": [i.to_dict() for i in self.issues],
        }


# ── Individual Validation Checks ──────────────────────────────────────

def check_node_uniqueness(nodes: List[dict]) -> Tuple[Set[str], List[ValidationIssue]]:
    """Verify all node IDs are globally unique."""
    issues = []
    seen = set()
    duplicates = set()

    for n in nodes:
        nid = n.get("id")
        if not nid:
            issues.append(ValidationIssue(
                severity="ERROR",
                check="node_uniqueness",
                message="Node missing 'id' attribute",
                context={"node": n},
            ))
            continue
        if nid in seen:
            duplicates.add(nid)
        seen.add(nid)

    for dup in duplicates:
        issues.append(ValidationIssue(
            severity="ERROR",
            check="node_uniqueness",
            message=f"Duplicate node ID detected: '{dup}'",
            context={"id": dup},
        ))

    return seen, issues


def check_node_types(nodes: List[dict]) -> Tuple[Dict[str, int], List[ValidationIssue]]:
    """Verify that all node types match the supported schema."""
    issues = []
    valid_types = {t.value for t in NodeType}
    counts: Dict[str, int] = defaultdict(int)

    for n in nodes:
        ntype = n.get("type")
        if not ntype or ntype not in valid_types:
            issues.append(ValidationIssue(
                severity="ERROR",
                check="node_types",
                message=f"Invalid or missing node type: '{ntype}' for node '{n.get('id')}'",
                context={"node": n},
            ))
        else:
            counts[ntype] += 1

    return dict(counts), issues


def check_edge_uniqueness(edges: List[dict]) -> List[ValidationIssue]:
    """Verify no duplicate (source_id, target_id, relation) triples exist."""
    issues = []
    seen = set()
    duplicates = []

    for e in edges:
        triple = (e.get("source_id"), e.get("target_id"), e.get("relation"))
        if triple in seen:
            duplicates.append(triple)
        seen.add(triple)

    for src, tgt, rel in duplicates:
        issues.append(ValidationIssue(
            severity="ERROR",
            check="edge_uniqueness",
            message=f"Duplicate edge detected: ({src} -> {tgt}, relation={rel})",
            context={"source_id": src, "target_id": tgt, "relation": rel},
        ))

    return issues


def check_no_self_loops(edges: List[dict]) -> Tuple[List[dict], List[ValidationIssue]]:
    """Ensure no edge has source_id == target_id."""
    issues = []
    invalid = []

    for e in edges:
        if e.get("source_id") == e.get("target_id"):
            invalid.append(e)
            issues.append(ValidationIssue(
                severity="ERROR",
                check="self_loops",
                message=f"Self-referencing edge: '{e.get('source_id')}' -> '{e.get('target_id')}' ({e.get('relation')})",
                context=e,
            ))

    return invalid, issues


def check_endpoints_exist(
    nodes: Dict[str, dict],
    edges: List[dict],
) -> Tuple[List[dict], List[ValidationIssue]]:
    """Verify that every edge's source and target exist in the node set."""
    issues = []
    invalid = []

    for e in edges:
        src = e.get("source_id")
        tgt = e.get("target_id")
        if src not in nodes:
            invalid.append(e)
            issues.append(ValidationIssue(
                severity="ERROR",
                check="dangling_endpoints",
                message=f"Edge source '{src}' does not exist in nodes set",
                context=e,
            ))
        if tgt not in nodes:
            invalid.append(e)
            issues.append(ValidationIssue(
                severity="ERROR",
                check="dangling_endpoints",
                message=f"Edge target '{tgt}' does not exist in nodes set",
                context=e,
            ))

    return invalid, issues


def check_relationship_types_and_derivations(
    edges: List[dict],
) -> Tuple[Dict[str, int], Dict[str, int], List[ValidationIssue]]:
    """Verify edge relations and derivations conform to schema enums."""
    issues = []
    valid_relations = {r.value for r in RelationType}
    valid_derivations = {d.value for d in DerivationStrategy}

    rel_counts: Dict[str, int] = defaultdict(int)
    deriv_counts: Dict[str, int] = defaultdict(int)

    for e in edges:
        rel = e.get("relation")
        deriv = e.get("derivation")

        if not rel or rel not in valid_relations:
            issues.append(ValidationIssue(
                severity="ERROR",
                check="relationship_types",
                message=f"Invalid relation type '{rel}' in edge from {e.get('source_id')} to {e.get('target_id')}",
                context=e,
            ))
        else:
            rel_counts[rel] += 1

        if not deriv or deriv not in valid_derivations:
            issues.append(ValidationIssue(
                severity="ERROR",
                check="derivation_types",
                message=f"Invalid derivation strategy '{deriv}' in edge from {e.get('source_id')} to {e.get('target_id')}",
                context=e,
            ))
        else:
            deriv_counts[deriv] += 1

    return dict(rel_counts), dict(deriv_counts), issues


def check_evidence_requirements(edges: List[dict]) -> List[ValidationIssue]:
    """Verify all LLM and structural edges have mandatory evidence quotes and valid confidence."""
    issues = []

    for e in edges:
        deriv = e.get("derivation")
        evidence = e.get("evidence", "")
        conf = e.get("confidence")

        # Confidence range check
        if conf is None or not (0.0 < float(conf) <= 1.0):
            issues.append(ValidationIssue(
                severity="ERROR",
                check="confidence_range",
                message=f"Edge confidence '{conf}' out of valid range (0.0, 1.0]",
                context=e,
            ))

        # Evidence required for LLM and structural edges
        if deriv in ("llm", "structural"):
            if not isinstance(evidence, str) or not evidence.strip():
                issues.append(ValidationIssue(
                    severity="ERROR",
                    check="evidence_required",
                    message=f"Edge derived via '{deriv}' lacks mandatory evidence text",
                    context=e,
                ))

    return issues


def check_domain_consistency(
    nodes: Dict[str, dict],
    edges: List[dict],
) -> List[ValidationIssue]:
    """Verify domain membership and chunk domain alignment."""
    issues = []

    concept_to_domain: Dict[str, str] = {}
    for e in edges:
        if e.get("relation") == "CONTAINS":
            concept_to_domain[e.get("target_id")] = e.get("source_id")

    # Check that domain IDs in CONTAINS are valid canonical domain IDs
    for cid, did in concept_to_domain.items():
        if did not in CANONICAL_DOMAIN_IDS:
            issues.append(ValidationIssue(
                severity="ERROR",
                check="domain_consistency",
                message=f"Concept '{cid}' contained by non-canonical domain '{did}'",
                context={"concept_id": cid, "domain_id": did},
            ))

    # Check KnowledgeChunk domain alignment
    for e in edges:
        if e.get("relation") == "HAS_CHUNK":
            cid = e.get("source_id")
            chunk_id = e.get("target_id")
            expected_domain = concept_to_domain.get(cid)
            chunk_node = nodes.get(chunk_id, {})
            actual_domain = chunk_node.get("properties", {}).get("domain_id")

            if expected_domain and actual_domain and expected_domain != actual_domain:
                issues.append(ValidationIssue(
                    severity="ERROR",
                    check="domain_consistency",
                    message=(
                        f"Chunk '{chunk_id}' has domain '{actual_domain}' but its parent "
                        f"concept '{cid}' belongs to domain '{expected_domain}'"
                    ),
                    context={"chunk_id": chunk_id, "chunk_domain": actual_domain, "concept_domain": expected_domain},
                ))

    return issues


def check_orphan_concepts(
    nodes: Dict[str, dict],
    edges: List[dict],
) -> Tuple[List[str], List[ValidationIssue]]:
    """Verify that every Concept is reachable from a Domain via CONTAINS."""
    issues = []
    concept_ids = {nid for nid, n in nodes.items() if n.get("type") == "Concept"}
    contained_concepts = {
        e.get("target_id") for e in edges if e.get("relation") == "CONTAINS"
    }

    orphans = sorted(list(concept_ids - contained_concepts))
    for cid in orphans:
        issues.append(ValidationIssue(
            severity="ERROR",
            check="orphan_concepts",
            message=f"Concept '{cid}' is orphaned (no incoming CONTAINS edge from any domain)",
            context={"concept_id": cid},
        ))

    return orphans, issues


def check_orphan_chunks(
    nodes: Dict[str, dict],
    edges: List[dict],
) -> Tuple[List[str], List[ValidationIssue]]:
    """Verify that every KnowledgeChunk is attached to a Concept via HAS_CHUNK."""
    issues = []
    chunk_ids = {nid for nid, n in nodes.items() if n.get("type") == "KnowledgeChunk"}
    linked_chunks = {
        e.get("target_id") for e in edges if e.get("relation") == "HAS_CHUNK"
    }

    orphans = sorted(list(chunk_ids - linked_chunks))
    for ch_id in orphans:
        issues.append(ValidationIssue(
            severity="ERROR",
            check="orphan_chunks",
            message=f"KnowledgeChunk '{ch_id}' is orphaned (no incoming HAS_CHUNK edge from any concept)",
            context={"chunk_id": ch_id},
        ))

    return orphans, issues


def check_prerequisite_acyclicity(edges: List[dict]) -> Tuple[bool, List[ValidationIssue]]:
    """
    Verify that the PREREQUISITE_OF subgraph contains NO directed cycles.
    A prerequisite graph MUST be a Directed Acyclic Graph (DAG) for valid learning trajectories.
    """
    issues = []
    adj: Dict[str, List[str]] = defaultdict(list)

    for e in edges:
        if e.get("relation") == "PREREQUISITE_OF":
            adj[e.get("source_id")].append(e.get("target_id"))

    # Cycle detection using 3-color DFS
    # 0 = unvisited, 1 = visiting (in recursion stack), 2 = visited
    state: Dict[str, int] = {}
    cycle_detected = False
    cycle_paths: List[List[str]] = []

    def dfs(node: str, current_path: List[str]):
        nonlocal cycle_detected
        state[node] = 1
        current_path.append(node)

        for neighbor in adj.get(node, []):
            if state.get(neighbor, 0) == 1:
                # Cycle found!
                cycle_detected = True
                cycle_start_idx = current_path.index(neighbor)
                cycle_paths.append(current_path[cycle_start_idx:] + [neighbor])
            elif state.get(neighbor, 0) == 0:
                dfs(neighbor, current_path)

        current_path.pop()
        state[node] = 2

    for n in list(adj.keys()):
        if state.get(n, 0) == 0:
            dfs(n, [])

    if cycle_detected:
        for cpath in cycle_paths:
            cycle_str = " -> ".join(cpath)
            issues.append(ValidationIssue(
                severity="ERROR",
                check="prerequisite_acyclicity",
                message=f"Cycle detected in prerequisite graph: {cycle_str}",
                context={"cycle_path": cpath},
            ))

    return not cycle_detected, issues


# ── Primary Validation Entry Point ────────────────────────────────────

def validate_graph(graph_data: dict) -> ValidationReport:
    """
    Run all validation checks on graph_data and produce a ValidationReport.
    """
    raw_nodes = graph_data.get("nodes", [])
    raw_edges = graph_data.get("edges", [])

    all_issues: List[ValidationIssue] = []
    invalid_edges_accum: List[dict] = []

    # 1. Node uniqueness
    seen_node_ids, node_uniq_issues = check_node_uniqueness(raw_nodes)
    all_issues.extend(node_uniq_issues)

    # 2. Node types
    node_types, ntype_issues = check_node_types(raw_nodes)
    all_issues.extend(ntype_issues)

    # Fast node lookup
    nodes_map = {n["id"]: n for n in raw_nodes if "id" in n}

    # 3. Edge uniqueness
    edge_uniq_issues = check_edge_uniqueness(raw_edges)
    all_issues.extend(edge_uniq_issues)

    # 4. Self loops
    self_loop_edges, self_loop_issues = check_no_self_loops(raw_edges)
    all_issues.extend(self_loop_issues)
    invalid_edges_accum.extend(self_loop_edges)

    # 5. Endpoint existence
    dangling_edges, endpoint_issues = check_endpoints_exist(nodes_map, raw_edges)
    all_issues.extend(endpoint_issues)
    invalid_edges_accum.extend(dangling_edges)

    # 6. Relationship types and derivations
    edge_types, edge_derivs, rel_issues = check_relationship_types_and_derivations(raw_edges)
    all_issues.extend(rel_issues)

    # 7. Evidence and confidence
    evidence_issues = check_evidence_requirements(raw_edges)
    all_issues.extend(evidence_issues)

    # 8. Domain consistency
    domain_issues = check_domain_consistency(nodes_map, raw_edges)
    all_issues.extend(domain_issues)

    # 9. Orphan concepts
    orphan_concepts, orphan_c_issues = check_orphan_concepts(nodes_map, raw_edges)
    all_issues.extend(orphan_c_issues)

    # 10. Orphan chunks
    orphan_chunks, orphan_ch_issues = check_orphan_chunks(nodes_map, raw_edges)
    all_issues.extend(orphan_ch_issues)

    # 11. Prerequisite acyclicity
    is_acyclic, cycle_issues = check_prerequisite_acyclicity(raw_edges)
    all_issues.extend(cycle_issues)

    error_count = sum(1 for i in all_issues if i.severity == "ERROR")
    is_valid = (error_count == 0)

    # Deduplicate invalid edges accumulator by identity
    seen_invalid = set()
    deduped_invalid_edges = []
    for ie in invalid_edges_accum:
        k = (ie.get("source_id"), ie.get("target_id"), ie.get("relation"))
        if k not in seen_invalid:
            seen_invalid.add(k)
            deduped_invalid_edges.append(ie)

    return ValidationReport(
        is_valid=is_valid,
        total_nodes=len(raw_nodes),
        total_edges=len(raw_edges),
        node_types=node_types,
        edge_types=edge_types,
        edge_by_derivation=edge_derivs,
        issues=all_issues,
        orphan_concepts=orphan_concepts,
        orphan_chunks=orphan_chunks,
        invalid_edges=deduped_invalid_edges,
        prerequisite_acyclic=is_acyclic,
    )


def validate_graph_file(path: Optional[str] = None) -> ValidationReport:
    """Load graph_data from file and validate it."""
    from app.rag.graph_builder import _output_path
    target_path = path or _output_path()

    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Graph file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    return validate_graph(graph_data)


# ── CLI Entrypoint ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="SmartInterview — Knowledge Graph Validation Engine (Phase 4)"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to graph_data.json (defaults to data/graph_data.json)",
    )
    args = parser.parse_args()

    report = validate_graph_file(args.file)
    print(report.format_text_report())
    sys.exit(0 if report.is_valid else 1)

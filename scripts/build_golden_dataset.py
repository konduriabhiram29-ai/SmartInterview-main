"""
SmartInterview — Golden Evaluation Dataset Builder (Phase 12)

Constructs the comprehensive, canonical golden evaluation benchmark pairing:
  1. Benchmark technical queries across all 8 CS domains.
  2. Ground-truth canonical chunk IDs from CanonicalChunkResolver (402 chunks).
  3. Ground-truth prerequisite dependencies derived from knowledge graph PREREQUISITE_OF edges.
  4. Cognitive Bloom levels (remember, understand, apply, analyze, evaluate, create).
  5. Key terminology and technical concepts for recall verification.
  6. Evaluation scenarios: standard, multi_hop, remediation, terminology, cognitive.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.rag.canonical_resolver import get_canonical_resolver


# Domain and query metadata enrichments
QUERY_METADATA = {
    "dns": {
        "bloom_level": "remember",
        "difficulty": "easy",
        "scenario_type": "standard",
        "key_terms": ["domain name system", "ip address", "resolver", "root server", "tld"],
    },
    "http-vs-https": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "terminology",
        "key_terms": ["ssl", "tls", "encryption", "handshake", "port 443", "certificate"],
    },
    "tcp-vs-udp": {
        "bloom_level": "analyze",
        "difficulty": "medium",
        "scenario_type": "cognitive",
        "key_terms": ["connection-oriented", "three-way handshake", "reliability", "flow control", "datagram"],
    },
    "osi-model": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["physical", "data link", "network", "transport", "session", "presentation", "application"],
    },
    "acid-properties": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "multi_hop",
        "key_terms": ["atomicity", "consistency", "isolation", "durability", "transaction"],
    },
    "indexing": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "terminology",
        "key_terms": ["b-tree", "clustered", "non-clustered", "search", "lookup", "performance"],
    },
    "keys": {
        "bloom_level": "remember",
        "difficulty": "easy",
        "scenario_type": "standard",
        "key_terms": ["primary key", "foreign key", "candidate key", "referential integrity"],
    },
    "normalization": {
        "bloom_level": "analyze",
        "difficulty": "hard",
        "scenario_type": "cognitive",
        "key_terms": ["1nf", "2nf", "3nf", "bcnf", "redundancy", "anomaly", "functional dependency"],
    },
    "factory": {
        "bloom_level": "apply",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["factory method", "creation", "instantiation", "abstract", "interface"],
    },
    "observer": {
        "bloom_level": "apply",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["publish-subscribe", "subject", "listener", "notify", "event"],
    },
    "singleton": {
        "bloom_level": "understand",
        "difficulty": "easy",
        "scenario_type": "terminology",
        "key_terms": ["single instance", "global access", "private constructor", "thread safety"],
    },
    "strategy": {
        "bloom_level": "apply",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["algorithm family", "interchangeable", "composition", "runtime"],
    },
    "array": {
        "bloom_level": "remember",
        "difficulty": "easy",
        "scenario_type": "standard",
        "key_terms": ["contiguous", "index", "o(1) access", "memory layout"],
    },
    "hash-table": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "multi_hop",
        "key_terms": ["hash function", "collision", "chaining", "open addressing", "buckets"],
    },
    "stack": {
        "bloom_level": "understand",
        "difficulty": "easy",
        "scenario_type": "remediation",
        "key_terms": ["lifo", "push", "pop", "peek", "queue"],
    },
    "tree": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["binary search tree", "root", "left child", "right child", "traversal"],
    },
    "dynamic-programming": {
        "bloom_level": "analyze",
        "difficulty": "hard",
        "scenario_type": "cognitive",
        "key_terms": ["optimal substructure", "overlapping subproblems", "memoization", "tabulation"],
    },
    "bias-variance-tradeoff": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "multi_hop",
        "key_terms": ["bias", "variance", "underfitting", "overfitting", "generalization"],
    },
    "linear-vs-logistic-regression": {
        "bloom_level": "analyze",
        "difficulty": "medium",
        "scenario_type": "cognitive",
        "key_terms": ["continuous", "classification", "sigmoid", "decision boundary"],
    },
    "decision-trees": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["gini impurity", "entropy", "information gain", "split", "pruning"],
    },
    "overfitting-vs-underfitting": {
        "bloom_level": "analyze",
        "difficulty": "medium",
        "scenario_type": "remediation",
        "key_terms": ["generalization error", "regularization", "training loss", "validation loss"],
    },
    "encapsulation": {
        "bloom_level": "remember",
        "difficulty": "easy",
        "scenario_type": "standard",
        "key_terms": ["data hiding", "private", "getters", "setters", "bundle data methods"],
    },
    "polymorphism": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["method overriding", "method overloading", "runtime", "compile-time"],
    },
    "composition-inheritance": {
        "bloom_level": "evaluate",
        "difficulty": "hard",
        "scenario_type": "cognitive",
        "key_terms": ["is-a", "has-a", "coupling", "flexibility", "fragile base class"],
    },
    "abstraction": {
        "bloom_level": "understand",
        "difficulty": "easy",
        "scenario_type": "standard",
        "key_terms": ["hide complexity", "essential features", "interfaces", "abstract class"],
    },
    "deadlock": {
        "bloom_level": "analyze",
        "difficulty": "hard",
        "scenario_type": "multi_hop",
        "key_terms": ["mutual exclusion", "hold and wait", "no preemption", "circular wait"],
    },
    "mutex-vs-semaphore": {
        "bloom_level": "analyze",
        "difficulty": "medium",
        "scenario_type": "terminology",
        "key_terms": ["locking mechanism", "signaling mechanism", "binary semaphore", "counting semaphore", "ownership"],
    },
    "process-vs-thread": {
        "bloom_level": "understand",
        "difficulty": "easy",
        "scenario_type": "standard",
        "key_terms": ["isolated address space", "shared memory", "context switch", "lightweight"],
    },
    "virtual-memory": {
        "bloom_level": "understand",
        "difficulty": "medium",
        "scenario_type": "standard",
        "key_terms": ["paging", "page table", "tlb", "page fault", "swap space"],
    },
    "caching": {
        "bloom_level": "understand",
        "difficulty": "easy",
        "scenario_type": "standard",
        "key_terms": ["latency reduction", "cache invalidation", "ttl", "lru", "write-through"],
    },
    "cap-theorem": {
        "bloom_level": "analyze",
        "difficulty": "hard",
        "scenario_type": "cognitive",
        "key_terms": ["consistency", "availability", "partition tolerance", "network partition"],
    },
    "consistent-hashing": {
        "bloom_level": "apply",
        "difficulty": "hard",
        "scenario_type": "multi_hop",
        "key_terms": ["hash ring", "virtual nodes", "horizontal scaling", "data rebalancing"],
    },
    "microservices-vs-monolith": {
        "bloom_level": "evaluate",
        "difficulty": "hard",
        "scenario_type": "cognitive",
        "key_terms": ["independent deployment", "network overhead", "distributed transactions", "scalability"],
    },
}


def build_golden_dataset():
    resolver = get_canonical_resolver()

    # Load graph data for PREREQUISITE_OF edges
    graph_path = PROJECT_ROOT / "data" / "graph_data.json"
    with open(graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    # Build target_concept -> prerequisite_concepts map
    prereq_map: dict[str, list[str]] = {}
    for edge in graph_data.get("edges", []):
        if edge.get("relation") == "PREREQUISITE_OF":
            target = edge["target_id"].split("_", 1)[-1]
            source = edge["source_id"].split("_", 1)[-1]
            prereq_map.setdefault(target, []).append(source)

    # Load baseline retrieval queries
    query_file = PROJECT_ROOT / "data" / "evaluation" / "retrieval_queries.json"
    with open(query_file, "r", encoding="utf-8") as f:
        base_queries = json.load(f)

    golden_records = []
    for idx, item in enumerate(base_queries, 1):
        q_id = f"GOLD_{idx:02d}"
        q_text = item["query"]
        domain = item["expected_domain"]
        concept = item["expected_concept"]

        # Fetch canonical chunks
        canonical_chunks = resolver.get_chunks_for_concept(concept)
        expected_chunk_ids = [c.chunk_id for c in canonical_chunks]

        # Prerequisite concepts from graph
        expected_prereqs = prereq_map.get(concept, [])

        meta = QUERY_METADATA.get(concept, {
            "bloom_level": "understand",
            "difficulty": "medium",
            "scenario_type": "standard",
            "key_terms": [],
        })

        record = {
            "query_id": q_id,
            "query": q_text,
            "domain": domain,
            "concept": concept,
            "bloom_level": meta["bloom_level"],
            "difficulty": meta["difficulty"],
            "scenario_type": meta["scenario_type"],
            "expected_chunk_ids": expected_chunk_ids,
            "expected_prerequisites": expected_prereqs,
            "key_terms": meta["key_terms"],
        }
        golden_records.append(record)

    out_file = PROJECT_ROOT / "data" / "evaluation" / "golden_evaluation_dataset.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(golden_records, f, indent=2)

    print(f"Successfully generated golden evaluation dataset at {out_file} with {len(golden_records)} benchmark records.")


if __name__ == "__main__":
    build_golden_dataset()

"""
SmartInterview — Knowledge Graph Storage & Query Layer (Phase 5)

Provides:
  1. BaseGraphStore: Abstract storage contract for knowledge graph operations.
  2. NetworkXGraphStore: High-performance embedded in-memory graph store backed by NetworkX.
  3. Neo4jGraphStore: Enterprise Cypher-based graph store with batch ingestion & Cypher queries.
  4. get_graph_store(): Resilient factory that provides the configured backend with automatic fallback.

Responsibilities separation:
  - MySQL: Relational application data (users, sessions, messages).
  - ChromaDB: Dense vector retrieval (all-MiniLM-L6-v2 embeddings).
  - Graph Store (Neo4j / NetworkX): Structured knowledge graph traversal.
"""

from __future__ import annotations

import os
import json
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set, Tuple

import networkx as nx

from app.config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    GRAPH_STORAGE_BACKEND,
)
from app.rag.graph_schema import NodeType, RelationType

logger = logging.getLogger(__name__)


# ── Abstract Graph Store Contract ─────────────────────────────────────

class BaseGraphStore(ABC):
    """Abstract interface defining the graph storage and query contract."""

    @abstractmethod
    def initialize_schema(self) -> None:
        """Initialize schema constraints, indices, or lookup tables."""
        pass

    @abstractmethod
    def ingest_graph(self, graph_data: dict) -> dict:
        """
        Ingest the complete graph structure (nodes + edges).
        Returns ingestion statistics dict.
        """
        pass

    @abstractmethod
    def get_domain(self, domain_id: str) -> Optional[dict]:
        """Fetch a Domain node by its unique ID."""
        pass

    @abstractmethod
    def get_concept(self, concept_id: str) -> Optional[dict]:
        """Fetch a Concept node by its unique ID."""
        pass

    @abstractmethod
    def get_chunks_for_concept(self, concept_id: str) -> List[dict]:
        """Fetch all KnowledgeChunk nodes attached to a concept via HAS_CHUNK."""
        pass

    @abstractmethod
    def get_prerequisites(self, concept_id: str) -> List[dict]:
        """
        Fetch all prerequisite Concept nodes for this concept.
        (Concepts P such that P ──PREREQUISITE_OF──> Concept).
        """
        pass

    @abstractmethod
    def get_dependents(self, concept_id: str) -> List[dict]:
        """
        Fetch all dependent Concept nodes for which this concept is a prerequisite.
        (Concepts D such that Concept ──PREREQUISITE_OF──> D).
        """
        pass

    @abstractmethod
    def get_related_concepts(self, concept_id: str) -> List[dict]:
        """Fetch all Concept nodes connected via RELATED_TO."""
        pass

    @abstractmethod
    def get_concepts_by_domain(self, domain_id: str) -> List[dict]:
        """Fetch all Concept nodes belonging to a Domain via CONTAINS."""
        pass

    @abstractmethod
    def get_concepts_by_skill(self, skill_key: str) -> List[dict]:
        """
        Fetch all Concept nodes mapped to a Skill key via
        Skill ──MAPS_TO──> Domain ──CONTAINS──> Concept.
        """
        pass

    @abstractmethod
    def get_subgraph(self, concept_ids: List[str], max_depth: int = 1) -> dict:
        """
        Extract an ego subgraph around candidate concepts including
        connected concepts, prerequisite chains, and relation types.
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """Return node and edge counts and metadata."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close client sessions and connection pools."""
        pass


# ── In-Memory / Embedded NetworkX Graph Store ─────────────────────────

class NetworkXGraphStore(BaseGraphStore):
    """
    High-performance, zero-latency graph store using NetworkX.
    Ideal for local development, fast retrieval testing, and offline modes.
    """

    def __init__(self, graph_data: Optional[dict] = None):
        self._graph = nx.MultiDiGraph()
        self._lock = threading.RLock()
        self._initialized = False

        # Fast lookup indexes
        self._nodes_by_type: Dict[str, Set[str]] = defaultdict_set()
        self._concepts_by_domain: Dict[str, Set[str]] = defaultdict_set()
        self._chunks_by_concept: Dict[str, List[str]] = {}
        self._domains_by_skill: Dict[str, Set[str]] = defaultdict_set()

        if graph_data:
            self.ingest_graph(graph_data)

    def initialize_schema(self) -> None:
        """No DDL required for NetworkX; ensures lookup caches are reset."""
        with self._lock:
            self._initialized = True
            logger.info("[NetworkXGraphStore] Schema initialized.")

    def ingest_graph(self, graph_data: dict) -> dict:
        """Populate the NetworkX MultiDiGraph from serialized graph_data."""
        with self._lock:
            self._graph.clear()
            self._nodes_by_type.clear()
            self._concepts_by_domain.clear()
            self._chunks_by_concept.clear()
            self._domains_by_skill.clear()

            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])

            for n in nodes:
                nid = n["id"]
                ntype = n["type"]
                props = n.get("properties", {})
                self._graph.add_node(nid, type=ntype, **props)
                self._nodes_by_type[ntype].add(nid)

            for e in edges:
                src = e["source_id"]
                tgt = e["target_id"]
                rel = e["relation"]
                props = {
                    "relation": rel,
                    "derivation": e.get("derivation", "metadata"),
                    "evidence": e.get("evidence", ""),
                    "confidence": float(e.get("confidence", 1.0)),
                }
                self._graph.add_edge(src, tgt, key=rel, **props)

                # Update fast lookup indexes
                if rel == "CONTAINS":
                    self._concepts_by_domain[src].add(tgt)
                elif rel == "HAS_CHUNK":
                    self._chunks_by_concept.setdefault(src, []).append(tgt)
                elif rel == "MAPS_TO":
                    self._domains_by_skill[src.lower()].add(tgt)
                    if src.lower().startswith("skill_"):
                        self._domains_by_skill[src[6:].lower()].add(tgt)

            self._initialized = True
            stats = {
                "nodes_ingested": len(nodes),
                "edges_ingested": len(edges),
                "backend": "networkx",
            }
            logger.info(
                "[NetworkXGraphStore] Ingestion complete: %d nodes, %d edges.",
                len(nodes), len(edges),
            )
            return stats

    def get_domain(self, domain_id: str) -> Optional[dict]:
        with self._lock:
            if domain_id in self._graph and self._graph.nodes[domain_id].get("type") == "Domain":
                data = dict(self._graph.nodes[domain_id])
                data["id"] = domain_id
                return data
            return None

    def get_concept(self, concept_id: str) -> Optional[dict]:
        with self._lock:
            if concept_id in self._graph and self._graph.nodes[concept_id].get("type") == "Concept":
                data = dict(self._graph.nodes[concept_id])
                data["id"] = concept_id
                return data
            return None

    def get_chunks_for_concept(self, concept_id: str) -> List[dict]:
        with self._lock:
            chunk_ids = self._chunks_by_concept.get(concept_id, [])
            results = []
            for cid in chunk_ids:
                if cid in self._graph:
                    d = dict(self._graph.nodes[cid])
                    d["id"] = cid
                    results.append(d)
            return results

    def get_prerequisites(self, concept_id: str) -> List[dict]:
        """Nodes P where P ──PREREQUISITE_OF──> concept_id."""
        with self._lock:
            results = []
            for pred in self._graph.predecessors(concept_id):
                edge_dict = self._graph.get_edge_data(pred, concept_id) or {}
                for edge_key, edge_attrs in edge_dict.items():
                    if edge_attrs.get("relation") == "PREREQUISITE_OF":
                        node_data = dict(self._graph.nodes[pred])
                        node_data["id"] = pred
                        node_data["edge"] = edge_attrs
                        results.append(node_data)
            return results

    def get_dependents(self, concept_id: str) -> List[dict]:
        """Nodes D where concept_id ──PREREQUISITE_OF──> D."""
        with self._lock:
            results = []
            for succ in self._graph.successors(concept_id):
                edge_dict = self._graph.get_edge_data(concept_id, succ) or {}
                for edge_key, edge_attrs in edge_dict.items():
                    if edge_attrs.get("relation") == "PREREQUISITE_OF":
                        node_data = dict(self._graph.nodes[succ])
                        node_data["id"] = succ
                        node_data["edge"] = edge_attrs
                        results.append(node_data)
            return results

    def get_related_concepts(self, concept_id: str) -> List[dict]:
        """Nodes R connected via RELATED_TO (in either direction)."""
        with self._lock:
            results = []
            seen: Set[str] = set()

            # Outgoing RELATED_TO
            for succ in self._graph.successors(concept_id):
                if succ == concept_id:
                    continue
                edge_dict = self._graph.get_edge_data(concept_id, succ) or {}
                for edge_key, edge_attrs in edge_dict.items():
                    if edge_attrs.get("relation") == "RELATED_TO" and succ not in seen:
                        seen.add(succ)
                        node_data = dict(self._graph.nodes[succ])
                        node_data["id"] = succ
                        node_data["edge"] = edge_attrs
                        results.append(node_data)

            # Incoming RELATED_TO
            for pred in self._graph.predecessors(concept_id):
                if pred == concept_id:
                    continue
                edge_dict = self._graph.get_edge_data(pred, concept_id) or {}
                for edge_key, edge_attrs in edge_dict.items():
                    if edge_attrs.get("relation") == "RELATED_TO" and pred not in seen:
                        seen.add(pred)
                        node_data = dict(self._graph.nodes[pred])
                        node_data["id"] = pred
                        node_data["edge"] = edge_attrs
                        results.append(node_data)

            return results

    def get_concepts_by_domain(self, domain_id: str) -> List[dict]:
        with self._lock:
            cids = self._concepts_by_domain.get(domain_id, set())
            results = []
            for cid in sorted(cids):
                if cid in self._graph:
                    d = dict(self._graph.nodes[cid])
                    d["id"] = cid
                    results.append(d)
            return results

    def get_concepts_by_skill(self, skill_key: str) -> List[dict]:
        with self._lock:
            sk_lower = skill_key.lower().strip()
            domains = self._domains_by_skill.get(sk_lower, set())
            results = []
            seen_concepts: Set[str] = set()

            for did in domains:
                for cnode in self.get_concepts_by_domain(did):
                    if cnode["id"] not in seen_concepts:
                        seen_concepts.add(cnode["id"])
                        results.append(cnode)
            return results

    def get_subgraph(self, concept_ids: List[str], max_depth: int = 1) -> dict:
        with self._lock:
            subgraph_nodes: Dict[str, dict] = {}
            subgraph_edges: List[dict] = []
            visited_nodes: Set[str] = set()

            frontier = set(concept_ids)
            for depth in range(max_depth + 1):
                next_frontier = set()
                for nid in frontier:
                    if nid not in self._graph or nid in visited_nodes:
                        continue
                    visited_nodes.add(nid)
                    ndata = dict(self._graph.nodes[nid])
                    ndata["id"] = nid
                    subgraph_nodes[nid] = ndata

                    if depth < max_depth:
                        # Follow concept-to-concept edges only for depth expansion
                        for neighbor in list(self._graph.successors(nid)) + list(self._graph.predecessors(nid)):
                            ntype = self._graph.nodes[neighbor].get("type")
                            if ntype in ("Concept", "Domain"):
                                next_frontier.add(neighbor)
                frontier = next_frontier

            # Collect edges among induced nodes
            for u in subgraph_nodes:
                for v in self._graph.successors(u):
                    if v in subgraph_nodes:
                        edge_dict = self._graph.get_edge_data(u, v) or {}
                        for k, attrs in edge_dict.items():
                            e_dict = dict(attrs)
                            e_dict["source_id"] = u
                            e_dict["target_id"] = v
                            subgraph_edges.append(e_dict)

            return {
                "nodes": list(subgraph_nodes.values()),
                "edges": subgraph_edges,
                "node_count": len(subgraph_nodes),
                "edge_count": len(subgraph_edges),
            }

    def get_stats(self) -> dict:
        with self._lock:
            type_counts = {t: len(ids) for t, ids in self._nodes_by_type.items()}
            return {
                "backend": "networkx",
                "total_nodes": self._graph.number_of_nodes(),
                "total_edges": self._graph.number_of_edges(),
                "node_types": type_counts,
            }

    def close(self) -> None:
        pass


def defaultdict_set():
    from collections import defaultdict
    return defaultdict(set)


# ── Neo4j Graph Store (Cypher Implementation) ─────────────────────────

class Neo4jGraphStore(BaseGraphStore):
    """
    Enterprise Cypher-based graph store connecting to Neo4j.
    Uses parameterized queries and batch ingestion via UNWIND.
    """

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
        database: str = NEO4J_DATABASE,
    ):
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver = None
        self._lock = threading.RLock()

    def _get_driver(self):
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    try:
                        from neo4j import GraphDatabase, basic_auth
                        auth = basic_auth(self._user, self._password) if self._password else None
                        self._driver = GraphDatabase.driver(self._uri, auth=auth)
                    except Exception as e:
                        logger.error("[Neo4jGraphStore] Failed to connect to Neo4j at %s: %s", self._uri, e)
                        raise ConnectionError(f"Could not connect to Neo4j at {self._uri}: {e}") from e
        return self._driver

    def is_connected(self) -> bool:
        """Check if Neo4j instance is alive and reachable."""
        try:
            driver = self._get_driver()
            with driver.session(database=self._database) as session:
                res = session.run("RETURN 1 AS ping")
                rec = res.single()
                return rec is not None and rec["ping"] == 1
        except Exception as e:
            logger.debug("[Neo4jGraphStore] Connection probe failed: %s", e)
            return False

    def initialize_schema(self) -> None:
        """Create uniqueness constraints for each node label."""
        driver = self._get_driver()
        queries = [
            "CREATE CONSTRAINT domain_id_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (k:KnowledgeChunk) REQUIRE k.id IS UNIQUE",
            "CREATE CONSTRAINT skill_id_unique IF NOT EXISTS FOR (s:Skill) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX concept_domain_idx IF NOT EXISTS FOR (c:Concept) ON (c.domain_id)",
        ]
        with driver.session(database=self._database) as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as e:
                    logger.warning("[Neo4jGraphStore] Schema query warning: %s (%s)", q, e)
        logger.info("[Neo4jGraphStore] Schema constraints and indices verified.")

    def ingest_graph(self, graph_data: dict) -> dict:
        """Batch-ingest nodes and edges into Neo4j using UNWIND."""
        driver = self._get_driver()
        self.initialize_schema()

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        # Group nodes by type
        nodes_by_type: Dict[str, List[dict]] = defaultdict_set()
        for n in nodes:
            props = dict(n.get("properties", {}))
            props["id"] = n["id"]
            props["type"] = n["type"]
            nodes_by_type.setdefault(n["type"], []).append(props)

        # Group edges by relation
        edges_by_rel: Dict[str, List[dict]] = defaultdict_set()
        for e in edges:
            edges_by_rel.setdefault(e["relation"], []).append({
                "source_id": e["source_id"],
                "target_id": e["target_id"],
                "derivation": e.get("derivation", "metadata"),
                "evidence": e.get("evidence", ""),
                "confidence": float(e.get("confidence", 1.0)),
            })

        with driver.session(database=self._database) as session:
            # Ingest nodes by label
            for label, items in nodes_by_type.items():
                if not items:
                    continue
                cypher = f"""
                UNWIND $batch AS item
                MERGE (n:{label} {{id: item.id}})
                SET n += item
                """
                session.run(cypher, batch=items)

            # Ingest edges by relationship type
            for rel, edge_items in edges_by_rel.items():
                if not edge_items:
                    continue
                cypher = f"""
                UNWIND $batch AS edge
                MATCH (a {{id: edge.source_id}})
                MATCH (b {{id: edge.target_id}})
                MERGE (a)-[r:{rel}]->(b)
                SET r.derivation = edge.derivation,
                    r.evidence   = edge.evidence,
                    r.confidence = edge.confidence
                """
                session.run(cypher, batch=edge_items)

        logger.info(
            "[Neo4jGraphStore] Ingestion complete: %d nodes, %d edges.",
            len(nodes), len(edges),
        )
        return {
            "nodes_ingested": len(nodes),
            "edges_ingested": len(edges),
            "backend": "neo4j",
        }

    def get_domain(self, domain_id: str) -> Optional[dict]:
        cypher = "MATCH (d:Domain {id: $id}) RETURN d"
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, id=domain_id).single()
            return dict(res["d"]) if res else None

    def get_concept(self, concept_id: str) -> Optional[dict]:
        cypher = "MATCH (c:Concept {id: $id}) RETURN c"
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, id=concept_id).single()
            return dict(res["c"]) if res else None

    def get_chunks_for_concept(self, concept_id: str) -> List[dict]:
        cypher = """
        MATCH (c:Concept {id: $id})-[:HAS_CHUNK]->(k:KnowledgeChunk)
        RETURN k
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, id=concept_id)
            return [dict(rec["k"]) for rec in res]

    def get_prerequisites(self, concept_id: str) -> List[dict]:
        cypher = """
        MATCH (p:Concept)-[r:PREREQUISITE_OF]->(c:Concept {id: $id})
        RETURN p, properties(r) AS edge
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, id=concept_id)
            results = []
            for rec in res:
                d = dict(rec["p"])
                d["edge"] = dict(rec["edge"])
                results.append(d)
            return results

    def get_dependents(self, concept_id: str) -> List[dict]:
        cypher = """
        MATCH (c:Concept {id: $id})-[r:PREREQUISITE_OF]->(d:Concept)
        RETURN d, properties(r) AS edge
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, id=concept_id)
            results = []
            for rec in res:
                d = dict(rec["d"])
                d["edge"] = dict(rec["edge"])
                results.append(d)
            return results

    def get_related_concepts(self, concept_id: str) -> List[dict]:
        cypher = """
        MATCH (c:Concept {id: $id})-[r:RELATED_TO]-(rel:Concept)
        RETURN DISTINCT rel, properties(r) AS edge
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, id=concept_id)
            results = []
            for rec in res:
                d = dict(rec["rel"])
                d["edge"] = dict(rec["edge"])
                results.append(d)
            return results

    def get_concepts_by_domain(self, domain_id: str) -> List[dict]:
        cypher = """
        MATCH (d:Domain {id: $id})-[:CONTAINS]->(c:Concept)
        RETURN c ORDER BY c.id
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, id=domain_id)
            return [dict(rec["c"]) for rec in res]

    def get_concepts_by_skill(self, skill_key: str) -> List[dict]:
        cypher = """
        MATCH (s:Skill) WHERE s.id = $skill OR s.id = ('skill_' + $skill) OR s.key = $skill
        MATCH (s)-[:MAPS_TO]->(d:Domain)-[:CONTAINS]->(c:Concept)
        RETURN DISTINCT c ORDER BY c.id
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, skill=skill_key.lower().strip())
            return [dict(rec["c"]) for rec in res]

    def get_subgraph(self, concept_ids: List[str], max_depth: int = 1) -> dict:
        cypher = """
        MATCH (c:Concept) WHERE c.id IN $ids
        OPTIONAL MATCH (c)-[r:PREREQUISITE_OF|RELATED_TO*1..1]-(neighbor:Concept)
        RETURN c, r, neighbor
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher, ids=concept_ids)
            nodes_map = {}
            edges = []
            for rec in res:
                c = dict(rec["c"])
                nodes_map[c["id"]] = c
                if rec["neighbor"]:
                    nbr = dict(rec["neighbor"])
                    nodes_map[nbr["id"]] = nbr
            return {
                "nodes": list(nodes_map.values()),
                "edges": edges,
                "node_count": len(nodes_map),
                "edge_count": len(edges),
            }

    def get_stats(self) -> dict:
        cypher = """
        MATCH (n) RETURN labels(n)[0] AS type, count(n) AS cnt
        """
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            res = session.run(cypher)
            type_counts = {rec["type"]: rec["cnt"] for rec in res if rec["type"]}
            total = sum(type_counts.values())
            return {
                "backend": "neo4j",
                "total_nodes": total,
                "node_types": type_counts,
            }

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None


# ── Store Factory & Singleton Manager ─────────────────────────────────

_store_lock = threading.Lock()
_active_store: Optional[BaseGraphStore] = None


def get_graph_store(
    backend: Optional[str] = None,
    graph_data_path: Optional[str] = None,
) -> BaseGraphStore:
    """
    Return the active graph store instance configured for the environment.

    Backend resolution logic:
      - 'neo4j': Attempt Neo4j connection; fail with ConnectionError if unavailable.
      - 'networkx': Always use NetworkXGraphStore.
      - 'auto' (default): Probe Neo4j connection. If alive, use Neo4jGraphStore;
        otherwise gracefully fallback to NetworkXGraphStore with an informative log.
    """
    global _active_store

    chosen_backend = (backend or GRAPH_STORAGE_BACKEND).lower().strip()

    if _active_store is not None:
        return _active_store

    with _store_lock:
        if _active_store is not None:
            return _active_store

        # 1. Explicit Neo4j requested
        if chosen_backend == "neo4j":
            logger.info("[GraphStore] Initializing explicit Neo4jGraphStore (%s)", NEO4J_URI)
            store = Neo4jGraphStore()
            if not store.is_connected():
                raise ConnectionError(
                    f"GRAPH_STORAGE_BACKEND='neo4j' specified, but Neo4j is not reachable at {NEO4J_URI}"
                )
            _active_store = store
            return _active_store

        # 2. Auto probe
        if chosen_backend == "auto":
            try:
                store = Neo4jGraphStore()
                if store.is_connected():
                    logger.info("[GraphStore] Neo4j instance detected at %s. Using Neo4jGraphStore.", NEO4J_URI)
                    _active_store = store
                    return _active_store
            except Exception as e:
                logger.debug("[GraphStore] Neo4j probe exception: %s", e)

            logger.info(
                "[GraphStore] No live Neo4j instance at %s. Using high-performance embedded NetworkXGraphStore.",
                NEO4J_URI,
            )

        # 3. Fallback / Default NetworkX
        from app.rag.graph_builder import _output_path
        target_path = graph_data_path or _output_path()

        graph_data = None
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    graph_data = json.load(f)
            except Exception as e:
                logger.warning("[GraphStore] Could not load graph data from %s: %s", target_path, e)

        _active_store = NetworkXGraphStore(graph_data=graph_data)
        return _active_store


def reset_graph_store() -> None:
    """Reset the singleton store (used by tests)."""
    global _active_store
    with _store_lock:
        if _active_store:
            _active_store.close()
        _active_store = None

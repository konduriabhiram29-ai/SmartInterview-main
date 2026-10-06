"""
SmartInterview — Knowledge Graph Ingestion Pipeline (Phase 5)

Ingests the validated knowledge graph (data/graph_data.json) into the configured
graph storage engine (Neo4j or NetworkX).

Workflow:
  1. Load graph data artefact.
  2. Run validation check (Phase 4 validator) to certify graph integrity.
  3. Initialize target storage schema (constraints and indices).
  4. Ingest nodes and relationships into the active graph store.
  5. Verify counts and print ingestion summary.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional, Dict, Any

from app.rag.graph_builder import _output_path
from app.rag.graph_validator import validate_graph
from app.rag.graph_store import get_graph_store, reset_graph_store, BaseGraphStore

logger = logging.getLogger(__name__)


def ingest_graph_pipeline(
    file_path: Optional[str] = None,
    backend: Optional[str] = None,
    validate_first: bool = True,
) -> Dict[str, Any]:
    """
    Execute the end-to-end graph ingestion pipeline.

    Parameters
    ----------
    file_path      : Path to graph_data.json (defaults to data/graph_data.json).
    backend        : Storage backend ("auto", "neo4j", or "networkx").
    validate_first : If True, runs Phase 4 validation and aborts on errors.

    Returns
    -------
    dict with ingestion statistics and status.
    """
    target_path = file_path or _output_path()

    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Knowledge graph artefact not found at: {target_path}")

    logger.info("=" * 60)
    logger.info("SmartInterview — Graph Ingestion Pipeline")
    logger.info("=" * 60)
    logger.info("Target file    : %s", target_path)
    logger.info("Target backend : %s", backend or "auto")

    # 1. Load data
    with open(target_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    # 2. Certification / Validation
    if validate_first:
        logger.info("[Ingestion] Validating graph integrity before ingestion...")
        report = validate_graph(graph_data)
        if not report.is_valid:
            logger.error("[Ingestion] Validation failed with %d errors. Ingestion aborted.", report.error_count)
            raise ValueError(f"Graph validation failed with {report.error_count} errors. Ingestion aborted.")
        logger.info("[Ingestion] Graph validation passed certified clean: 0 errors.")

    # 3. Obtain store
    reset_graph_store()
    store = get_graph_store(backend=backend, graph_data_path=target_path)

    # 4. Initialize schema
    logger.info("[Ingestion] Initializing storage schema...")
    store.initialize_schema()

    # 5. Ingest
    logger.info("[Ingestion] Ingesting nodes and edges...")
    stats = store.ingest_graph(graph_data)

    logger.info("=" * 60)
    logger.info("GRAPH INGESTION COMPLETE")
    logger.info("=" * 60)
    logger.info("Backend        : %s", stats.get("backend"))
    logger.info("Nodes ingested : %d", stats.get("nodes_ingested", 0))
    logger.info("Edges ingested : %d", stats.get("edges_ingested", 0))
    logger.info("=" * 60)

    return {
        "status": "success",
        "file_path": target_path,
        "backend": stats.get("backend"),
        "nodes_ingested": stats.get("nodes_ingested", 0),
        "edges_ingested": stats.get("edges_ingested", 0),
    }


# ── CLI Entrypoint ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="SmartInterview — Knowledge Graph Ingestion Pipeline"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to graph_data.json",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="auto",
        choices=["auto", "neo4j", "networkx"],
        help="Target graph store backend",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip pre-ingestion validation check",
    )
    args = parser.parse_args()

    try:
        res = ingest_graph_pipeline(
            file_path=args.file,
            backend=args.backend,
            validate_first=not args.no_validate,
        )
        sys.exit(0)
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        sys.exit(1)

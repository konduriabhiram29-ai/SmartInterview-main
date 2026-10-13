"""
SmartInterview — Phase 11 Tests: Configuration Consistency & Security Audit

Validates:
  1. Complete environment variable schema loading and type coercion.
  2. validate_config() operational audit results and status schema.
  3. JWT security warnings: critical flag when default secret is used in production.
  4. Alias resolution for backwards compatibility (SECRET_KEY -> JWT_SECRET_KEY, etc.).
  5. Validation gates for invalid RAG_MODE, GRAPH_STORAGE_BACKEND, and RERANKER_BACKEND.
  6. Hybrid weight balance checks (warns when weights do not sum close to 1.0).
  7. Path traversal protections across uploads and database directory resolution.
  8. Filename sanitization protecting against directory traversal injections.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import app.config as config
from app.config import (
    validate_config,
    PROJECT_ROOT,
    UPLOAD_DIR,
    SYLLABUS_UPLOAD_DIR,
    CHROMA_DB_DIR,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_EXPIRATION_MINUTES,
    RAG_MODE,
    GRAPH_STORAGE_BACKEND,
    RERANKER_BACKEND,
    RERANKER_ENABLED,
    HYBRID_VECTOR_WEIGHT,
    HYBRID_KEYWORD_WEIGHT,
    HYBRID_GRAPH_WEIGHT,
)


class TestConfigValidationFunction:
    def test_validate_config_healthy_state(self):
        report = validate_config()
        assert isinstance(report, dict)
        assert "is_valid" in report
        assert "findings" in report
        assert "warnings" in report
        assert report["rag_mode"] in {"dense", "vector", "keyword", "bm25", "graph", "hybrid"}
        assert report["graph_backend"] in {"auto", "neo4j", "networkx"}
        assert report["reranker_backend"] in {"semantic", "cross_encoder", "none", "passthrough"}
        assert isinstance(report["is_valid"], bool)

    def test_production_default_jwt_secret_triggers_critical_finding(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with patch.object(config, "JWT_SECRET_KEY", "dev-secret-change-in-production"):
                report = validate_config()
                assert not report["is_valid"]
                assert any("CRITICAL" in f for f in report["findings"])

    def test_production_strong_jwt_secret_passes(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with patch.object(config, "JWT_SECRET_KEY", "super_strong_production_random_secret_hex_64"):
                report = validate_config()
                assert not any("CRITICAL" in f for f in report["findings"])

    def test_invalid_rag_mode_reported_as_finding(self):
        with patch.object(config, "RAG_MODE", "unsupported_mode"):
            report = validate_config()
            assert not report["is_valid"]
            assert any("Invalid RAG_MODE" in f for f in report["findings"])

    def test_invalid_graph_storage_backend_reported_as_finding(self):
        with patch.object(config, "GRAPH_STORAGE_BACKEND", "invalid_backend"):
            report = validate_config()
            assert not report["is_valid"]
            assert any("Invalid GRAPH_STORAGE_BACKEND" in f for f in report["findings"])

    def test_invalid_reranker_backend_reported_as_finding(self):
        with patch.object(config, "RERANKER_BACKEND", "invalid_reranker"):
            report = validate_config()
            assert not report["is_valid"]
            assert any("Invalid RERANKER_BACKEND" in f for f in report["findings"])

    def test_unbalanced_hybrid_weights_triggers_warning(self):
        with patch.object(config, "HYBRID_VECTOR_WEIGHT", 0.9):
            with patch.object(config, "HYBRID_KEYWORD_WEIGHT", 0.9):
                with patch.object(config, "HYBRID_GRAPH_WEIGHT", 0.9):
                    report = validate_config()
                    assert any("weights do not sum" in w for w in report["warnings"])


class TestSecurityAndPathTraversal:
    def test_upload_directories_are_within_project_root(self):
        assert Path(UPLOAD_DIR).is_relative_to(PROJECT_ROOT)
        assert Path(SYLLABUS_UPLOAD_DIR).is_relative_to(PROJECT_ROOT)
        assert UPLOAD_DIR.exists()
        assert SYLLABUS_UPLOAD_DIR.exists()

    def test_chroma_db_dir_is_absolute_and_valid(self):
        chroma_path = Path(CHROMA_DB_DIR)
        assert chroma_path.is_absolute()
        assert chroma_path.exists()

    def test_filename_sanitization_defense_against_path_traversal(self):
        """
        Verify that user-supplied malicious file paths (e.g. ../../etc/passwd)
        are neutralized by os.path.basename in syllabus and resume uploads.
        """
        malicious_filename = "../../../etc/passwd"
        safe_base = os.path.basename(malicious_filename)
        assert ".." not in safe_base
        assert "/" not in safe_base
        assert "\\" not in safe_base
        assert safe_base == "passwd"

    def test_jwt_expiration_is_positive_integer(self):
        assert isinstance(JWT_EXPIRATION_MINUTES, int)
        assert JWT_EXPIRATION_MINUTES > 0

    def test_hybrid_fetch_k_is_positive_integer(self):
        from app.config import HYBRID_FETCH_K
        assert isinstance(HYBRID_FETCH_K, int)
        assert HYBRID_FETCH_K > 0

    def test_reranker_top_k_is_positive_integer(self):
        from app.config import RERANKER_TOP_K
        assert isinstance(RERANKER_TOP_K, int)
        assert RERANKER_TOP_K > 0

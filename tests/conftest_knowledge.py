"""Test conftest for BLOQUE 72 Knowledge RAG tests.

Provides a lightweight FastAPI app with only the knowledge router mounted,
avoiding the heavy imports from backend.main (which trigger HuggingFace API calls).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def knowledge_store_dir():
    """Create a temporary directory for knowledge store during tests."""
    tmp = tempfile.mkdtemp(prefix="aura_kb_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def knowledge_app(knowledge_store_dir):
    """Build a minimal FastAPI app with only the knowledge router."""
    # Patch environment before importing
    os.environ["AURA_KNOWLEDGE_DIR"] = knowledge_store_dir

    # Reset any existing engine state
    from backend.knowledge.rag import reset_rag_engine

    reset_rag_engine()

    # Build minimal app
    app = FastAPI(title="AURA Knowledge Test", version="test")
    from backend.knowledge.router import router as knowledge_router

    app.include_router(knowledge_router)

    # Reset after
    yield app

    reset_rag_engine()


@pytest.fixture
def knowledge_client(knowledge_app):
    """TestClient for the knowledge app."""
    with TestClient(knowledge_app) as client:
        yield client

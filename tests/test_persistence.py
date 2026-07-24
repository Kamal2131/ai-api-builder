"""Phase 3 persistence tests — hermetic via SQLite; no Postgres or LLM needed."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import db
from config.settings import settings
from server import app

BOOK_REQUEST = (
    "Create a Book Management API with JWT auth, CRUD Books and CRUD Authors, "
    "PostgreSQL, Docker, and unit tests."
)


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """Point persistence at a throwaway SQLite file and reset the cached factory."""
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'builds.db'}")
    monkeypatch.setattr(db, "_session_factory", None)


@pytest.fixture
def no_db(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(db, "_session_factory", None)


def test_record_list_and_download_roundtrip(sqlite_db):
    build_id = db.record_build(request="r", spec={"project_name": "book-api"},
                               attempts=2, status="success", zip_bytes=b"PK-fake")
    db.record_build(request="r2", spec=None, attempts=1, status="failed", error="boom")

    builds = db.list_builds()
    assert [b["status"] for b in builds] == ["failed", "success"]  # newest first
    assert builds[1]["project_name"] == "book-api"
    assert builds[1]["attempts"] == 2
    assert "zip_bytes" not in builds[1]

    assert db.get_build_zip(build_id) == ("book-api", b"PK-fake")
    assert db.get_build_zip(9999) is None  # unknown id


def test_persistence_disabled_without_database_url(no_db):
    assert db.record_build(request="r", spec=None, attempts=1, status="success") is None
    assert db.list_builds() is None
    assert TestClient(app).get("/api/builds").status_code == 503


def test_build_endpoint_records_history_end_to_end(sqlite_db):
    client = TestClient(app)
    with patch("agents.api_builder_agent.nodes.planner.get_llm",
               side_effect=RuntimeError("no llm")):
        response = client.post("/api/build", json={"request": BOOK_REQUEST})

    assert response.status_code == 200
    build_id = int(response.headers["x-build-id"])

    history = client.get("/api/builds").json()
    assert history[0]["id"] == build_id
    assert history[0]["status"] == "success"
    assert history[0]["zip_size"] > 0

    download = client.get(f"/api/builds/{build_id}/download")
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert any(n.endswith("app/main.py") for n in archive.namelist())


def test_broken_database_never_blocks_the_build(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://nobody@127.0.0.1:1/x")
    monkeypatch.setattr(db, "_session_factory", None)

    client = TestClient(app)
    with patch("agents.api_builder_agent.nodes.planner.get_llm",
               side_effect=RuntimeError("no llm")):
        response = client.post("/api/build", json={"request": BOOK_REQUEST})

    assert response.status_code == 200  # build succeeds, recording is best-effort
    assert "x-build-id" not in response.headers

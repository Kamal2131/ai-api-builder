"""Phase 3 S3 offload tests — hermetic via moto; no AWS, Postgres, or LLM needed."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

import db
import storage
from config.settings import settings
from server import app

BOOK_REQUEST = (
    "Create a Book Management API with JWT auth, CRUD Books and CRUD Authors, "
    "PostgreSQL, Docker, and unit tests."
)
BUCKET = "builder-test-bucket"


@pytest.fixture
def s3_bucket(monkeypatch):
    """In-memory S3 with the bucket created, plus a fresh client singleton."""
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        monkeypatch.setattr(settings, "s3_bucket", BUCKET)
        monkeypatch.setattr(settings, "s3_endpoint_url", "")
        monkeypatch.setattr(storage, "_client", None)
        yield


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'builds.db'}")
    monkeypatch.setattr(db, "_session_factory", None)


def test_store_and_fetch_roundtrip(s3_bucket):
    key = storage.store_zip("book-api", b"PK-fake")

    assert key is not None and key.endswith("book-api.zip")
    assert storage.fetch_zip(key) == b"PK-fake"
    assert storage.fetch_zip("builds/nope/missing.zip") is None


def test_offload_disabled_without_bucket(monkeypatch):
    monkeypatch.setattr(settings, "s3_bucket", "")
    monkeypatch.setattr(storage, "_client", None)

    assert storage.store_zip("book-api", b"PK-fake") is None
    assert storage.fetch_zip("builds/any/key.zip") is None


def test_recorded_build_offloads_zip_and_redownloads(s3_bucket, sqlite_db):
    client = TestClient(app)
    with patch("agents.api_builder_agent.nodes.planner.get_llm",
               side_effect=RuntimeError("no llm")):
        response = client.post("/api/build", json={"request": BOOK_REQUEST})

    assert response.status_code == 200
    build_id = int(response.headers["x-build-id"])

    entry = client.get("/api/builds").json()[0]
    assert entry["id"] == build_id
    assert entry["storage"] == "s3"
    assert entry["zip_size"] > 0

    download = client.get(f"/api/builds/{build_id}/download")
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert any(n.endswith("app/main.py") for n in archive.namelist())


def test_failed_upload_falls_back_to_inline_storage(s3_bucket, sqlite_db):
    with patch.object(storage, "store_zip", return_value=None):  # S3 "down" at upload time
        build_id = db.record_build(request="r", spec={"project_name": "book-api"},
                                   attempts=1, status="success", zip_bytes=b"PK-fake")

    assert db.list_builds()[0]["storage"] == "inline"
    assert db.get_build_zip(build_id) == ("book-api", b"PK-fake")


def test_schema_migration_adds_zip_key_to_existing_table(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text

    # A pre-S3 builds table, as an existing deployment would have it.
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE builds (id INTEGER PRIMARY KEY, created_at DATETIME, "
            "request TEXT, project_name VARCHAR(200), spec TEXT, attempts INTEGER, "
            "status VARCHAR(20), error TEXT, zip_size INTEGER, zip_bytes BLOB)"
        ))
    engine.dispose()

    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(db, "_session_factory", None)

    build_id = db.record_build(request="r", spec=None, attempts=1,
                               status="success", zip_bytes=b"PK-fake")
    assert build_id is not None  # would raise without the zip_key column migration

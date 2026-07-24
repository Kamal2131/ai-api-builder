"""Phase 1 tests — planner fallback, renderer output validity, and end-to-end packaging."""

from __future__ import annotations

import ast
import io
import zipfile
from unittest.mock import patch

from agents.api_builder_agent.generators.renderer import render_project
from agents.api_builder_agent.graph import build_graph
from agents.api_builder_agent.nodes.planner import _fallback_spec

BOOK_REQUEST = (
    "Create a Book Management API with JWT auth, CRUD Books and CRUD Authors, "
    "PostgreSQL, Docker, and unit tests."
)


def test_fallback_spec_parses_book_example():
    spec = _fallback_spec(BOOK_REQUEST)
    assert spec["database"] == "postgres"
    assert spec["auth"] == "jwt"
    assert spec["entities"] == ["Book", "Author"]
    assert spec["project_name"].endswith("api")


def test_render_project_emits_expected_files_and_valid_python():
    spec = {"project_name": "book-api", "database": "postgres", "auth": "jwt",
            "entities": ["Book", "Author"]}
    files = render_project(spec)

    for path in ("app/main.py", "app/models.py", "app/schemas.py", "app/crud.py",
                 "app/routers/book.py", "app/routers/author.py", "app/auth.py",
                 "tests/test_crud.py", "Dockerfile", "requirements.txt", "README.md"):
        assert path in files, f"missing {path}"

    for path, content in files.items():
        if path.endswith(".py"):
            ast.parse(content)  # raises SyntaxError if the codegen is broken


def test_render_project_without_auth_skips_auth_module():
    spec = {"project_name": "note-api", "database": "sqlite", "auth": None, "entities": ["Note"]}
    files = render_project(spec)

    assert "app/auth.py" not in files
    assert "app/routers/note.py" in files
    assert "Depends(get_current_user)" not in files["app/routers/note.py"]


def test_graph_produces_zip_via_fallback():
    # Force the planner's LLM call to fail so the deterministic fallback runs (no network).
    with patch("agents.api_builder_agent.nodes.planner.get_llm", side_effect=RuntimeError("no llm")):
        result = build_graph().invoke({"request": BOOK_REQUEST})

    assert not result.get("error")
    with zipfile.ZipFile(io.BytesIO(result["zip_bytes"])) as archive:
        names = archive.namelist()

    assert any(n.endswith("app/main.py") for n in names)
    assert any(n.endswith("app/routers/book.py") for n in names)
    assert any(n.endswith("app/routers/author.py") for n in names)


def test_empty_request_reports_error():
    result = build_graph().invoke({"request": "   "})
    assert result.get("error")

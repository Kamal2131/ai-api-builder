"""Phase 2 tests — planner fallback, per-node rendering, reviewer gate, end-to-end packaging."""

from __future__ import annotations

import ast
import io
import zipfile
from unittest.mock import patch

from agents.api_builder_agent.generators.renderer import build_context, render_project
from agents.api_builder_agent.graph import build_graph
from agents.api_builder_agent.nodes.planner import _fallback_spec, _normalize_spec, _parse_llm_json
from agents.api_builder_agent.nodes.reviewer import review

BOOK_REQUEST = (
    "Create a Book Management API with JWT auth, CRUD Books and CRUD Authors, "
    "PostgreSQL, Docker, and unit tests."
)

BOOK_SPEC = {"project_name": "book-api", "database": "postgres", "auth": "jwt",
             "entities": ["Book", "Author"]}


def test_fallback_spec_parses_book_example():
    spec = _fallback_spec(BOOK_REQUEST)
    assert spec["database"] == "postgres"
    assert spec["auth"] == "jwt"
    assert spec["entities"] == ["Book", "Author"]
    assert spec["project_name"].endswith("api")


def test_parse_llm_json_tolerates_fences_and_prose():
    spec = '{"project_name": "book-api", "entities": ["Book"]}'
    assert _parse_llm_json(spec) == {"project_name": "book-api", "entities": ["Book"]}
    assert _parse_llm_json(f"```json\n{spec}\n```")["project_name"] == "book-api"
    assert _parse_llm_json(f"Here is the spec: {spec}")["entities"] == ["Book"]
    assert _parse_llm_json("no json here") is None


def test_normalize_spec_drops_infra_words_and_duplicates():
    raw = {"project_name": "Book API", "database": "postgres", "auth": "jwt",
           "entities": ["Book", "Auth", "Book", "Docker", "Author"]}
    spec = _normalize_spec(raw, BOOK_REQUEST)
    assert spec["entities"] == ["Book", "Author"]


def test_render_project_emits_expected_files_and_valid_python():
    files = render_project(BOOK_SPEC)

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


def test_reviewer_passes_a_complete_project():
    ctx = build_context(BOOK_SPEC)
    result = review({"files": render_project(BOOK_SPEC), "context": ctx})
    assert not result.get("error")


def test_reviewer_requests_retry_with_feedback_on_first_failure():
    ctx = build_context(BOOK_SPEC)
    files = render_project(BOOK_SPEC)
    files["app/crud.py"] = "def broken(:"
    del files["app/routers/author.py"]

    result = review({"files": files, "context": ctx, "attempts": 1})
    assert "error" not in result
    assert result["files"] is None  # wipes the map so the rebuild starts clean
    assert "invalid python in app/crud.py" in result["review_feedback"]
    assert "missing router app/routers/author.py" in result["review_feedback"]


def test_reviewer_fails_for_good_once_attempts_are_exhausted():
    ctx = build_context(BOOK_SPEC)
    files = render_project(BOOK_SPEC)
    files["app/main.py"] = files["app/main.py"].replace("app.include_router(book.router)\n", "")
    files["app/models.py"] = files["app/models.py"].replace("class Author(Base)", "class Writer(Base)")
    files["requirements.txt"] = files["requirements.txt"].replace("psycopg[binary]==3.3.4\n", "")

    result = review({"files": files, "context": ctx, "attempts": 2})
    assert "router for Book not mounted" in result["error"]
    assert "no model class for Author" in result["error"]
    assert "requirements.txt missing psycopg" in result["error"]


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


def test_graph_retries_once_then_fails_when_review_keeps_failing():
    # Backend output stays broken, so the retry cannot help: expect a bounded, final failure.
    with (
        patch("agents.api_builder_agent.nodes.planner.get_llm", side_effect=RuntimeError("no llm")),
        patch("agents.api_builder_agent.nodes.backend.render_backend",
              return_value={"app/main.py": "def broken(:"}),
    ):
        result = build_graph().invoke({"request": BOOK_REQUEST})

    assert "failed review after 2 attempts" in result["error"]
    assert result["attempts"] == 2
    assert "zip_bytes" not in result


def test_graph_recovers_when_retry_fixes_the_project():
    # First backend render is broken, the rebuild is fine: the retry loop must recover.
    ctx = build_context(_fallback_spec(BOOK_REQUEST))
    from agents.api_builder_agent.generators.renderer import render_backend
    good_files = render_backend(ctx)

    with (
        patch("agents.api_builder_agent.nodes.planner.get_llm", side_effect=RuntimeError("no llm")),
        patch("agents.api_builder_agent.nodes.backend.render_backend",
              side_effect=[{"app/main.py": "def broken(:"}, good_files]),
    ):
        result = build_graph().invoke({"request": BOOK_REQUEST})

    assert not result.get("error")
    assert result["attempts"] == 2
    with zipfile.ZipFile(io.BytesIO(result["zip_bytes"])) as archive:
        assert any(n.endswith("app/main.py") for n in archive.namelist())


def test_retry_prompt_includes_reviewer_feedback():
    from agents.api_builder_agent.interpreter.prompts import build_planner_messages

    messages = build_planner_messages(BOOK_REQUEST, feedback="missing router app/routers/book.py",
                                      previous_spec={"entities": ["Book"]})
    final = messages[-1].content
    assert "missing router app/routers/book.py" in final
    assert '"entities": ["Book"]' in final
    assert "corrected JSON spec" in final


def test_empty_request_reports_error():
    result = build_graph().invoke({"request": "   "})
    assert result.get("error")

"""reviewer node — validates the generated project before it is packaged.

Checks go beyond "files exist": every entity must be wired end-to-end
(model → schemas → router → mounted in main), the requirements must match
the chosen database, and every Python file must actually parse.
"""

from __future__ import annotations

import ast

from agents.api_builder_agent.state import ApiBuilderAgentState

# Total build attempts (first try + retries with reviewer feedback) before giving up.
_MAX_BUILD_ATTEMPTS = 2

_MAIN_PY = "app/main.py"
_REQUIRED_FILES = (
    _MAIN_PY,
    "app/models.py",
    "app/schemas.py",
    "app/crud.py",
    "app/database.py",
    "requirements.txt",
    "Dockerfile",
    "README.md",
    "tests/test_crud.py",
)
_DB_DRIVERS = {"postgres": "psycopg", "mysql": "pymysql"}


def _entity_problems(files: dict[str, str], entity: dict) -> list[str]:
    """Verify one entity is wired through every layer of the generated app."""
    name, snake = entity["name"], entity["snake"]
    problems = []

    if f"app/routers/{snake}.py" not in files:
        problems.append(f"missing router app/routers/{snake}.py")
    if f"class {name}(Base)" not in files.get("app/models.py", ""):
        problems.append(f"no model class for {name} in app/models.py")
    schemas = files.get("app/schemas.py", "")
    if f"class {name}Create" not in schemas or f"class {name}Read" not in schemas:
        problems.append(f"incomplete schemas for {name} in app/schemas.py")
    if f"include_router({snake}.router)" not in files.get(_MAIN_PY, ""):
        problems.append(f"router for {name} not mounted in {_MAIN_PY}")

    return problems


def _wiring_problems(files: dict[str, str], context: dict) -> list[str]:
    """Cross-file consistency: DB driver in requirements, auth present and mounted."""
    problems = []

    driver = _DB_DRIVERS.get(context.get("database", ""))
    if driver and driver not in files.get("requirements.txt", ""):
        problems.append(f"requirements.txt missing {driver} for {context['database']}")

    if context.get("use_jwt"):
        if "app/auth.py" not in files:
            problems.append("missing app/auth.py (JWT requested)")
        elif "include_router(auth.router)" not in files.get(_MAIN_PY, ""):
            problems.append(f"auth router not mounted in {_MAIN_PY}")

    return problems


def _find_problems(files: dict[str, str], context: dict) -> list[str]:
    """Collect every validation failure instead of stopping at the first one."""
    problems = [f"missing {path}" for path in _REQUIRED_FILES if path not in files]

    for entity in context.get("entities", []):
        problems.extend(_entity_problems(files, entity))
    problems.extend(_wiring_problems(files, context))

    for path, content in sorted(files.items()):
        if path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as exc:
                problems.append(f"invalid python in {path}: {exc.msg} (line {exc.lineno})")

    return problems


def review(state: ApiBuilderAgentState) -> dict:
    """Pass the build, send it back to the planner with feedback, or fail it for good."""
    files = state.get("files") or {}
    if not files:
        return {"error": "Nothing to review.", "messages": ["reviewer: no files"]}

    problems = _find_problems(files, state.get("context") or {})
    if not problems:
        return {"messages": [f"reviewer: ok ({len(files)} files)"]}

    report = "; ".join(problems)
    if state.get("attempts", 1) < _MAX_BUILD_ATTEMPTS:
        return {
            "review_feedback": report,
            "files": None,  # wipe the map so the rebuild starts clean, without stale files
            "messages": [f"reviewer: retrying — {report}"],
        }

    return {
        "error": f"Generated project failed review after {_MAX_BUILD_ATTEMPTS} attempts: {report}",
        "messages": [f"reviewer: FAILED — {report}"],
    }

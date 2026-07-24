"""Templates-first FastAPI project renderer — turns a planner spec into a {path: content} file map."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "fastapi"

# Global templates rendered once: template filename -> output path in the generated project.
_GLOBAL_TEMPLATES = {
    "main.py.jinja": "app/main.py",
    "config.py.jinja": "app/config.py",
    "database.py.jinja": "app/database.py",
    "deps.py.jinja": "app/deps.py",
    "models.py.jinja": "app/models.py",
    "schemas.py.jinja": "app/schemas.py",
    "crud.py.jinja": "app/crud.py",
    "requirements.txt.jinja": "requirements.txt",
    "Dockerfile.jinja": "Dockerfile",
    "docker-compose.yml.jinja": "docker-compose.yml",
    "env.example.jinja": ".env.example",
    "gitignore.jinja": ".gitignore",
    "README.md.jinja": "README.md",
    "test_crud.py.jinja": "tests/test_crud.py",
}
_ROUTER_TEMPLATE = "router.py.jinja"          # rendered once per entity
_AUTH_TEMPLATE = ("auth.py.jinja", "app/auth.py")  # rendered only when JWT is requested
_PACKAGE_DIRS = ("app", "app/routers", "tests")


def _snake(name: str) -> str:
    """PascalCase / spaced name -> snake_case identifier."""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return re.sub(r"[^a-z0-9_]", "_", spaced.lower()).strip("_") or "item"


def _normalize_entity(entity: Any) -> dict:
    """Turn a spec entity (string or dict) into the naming variants templates need."""
    raw = entity if isinstance(entity, str) else entity.get("name", "Item")
    name = re.sub(r"[^A-Za-z0-9]", "", raw.strip()) or "Item"
    snake = _snake(name)
    return {
        "name": name,               # Book
        "snake": snake,             # book
        "plural": f"{snake}s",      # books
        "table": f"{snake}s",       # books
    }


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_project(spec: dict) -> dict[str, str]:
    """Render every project file from the build spec and return a {path: content} map."""
    env = _build_env()
    entities = [_normalize_entity(e) for e in spec.get("entities", [])] or [_normalize_entity("Item")]

    ctx = {
        "project_name": spec.get("project_name", "generated-api"),
        "database": spec.get("database", "postgres"),
        "auth": spec.get("auth"),
        "use_jwt": spec.get("auth") == "jwt",
        "entities": entities,
    }

    files: dict[str, str] = {}
    for template_name, out_path in _GLOBAL_TEMPLATES.items():
        files[out_path] = env.get_template(template_name).render(**ctx)

    router_tpl = env.get_template(_ROUTER_TEMPLATE)
    for entity in entities:
        files[f"app/routers/{entity['snake']}.py"] = router_tpl.render(entity=entity, **ctx)

    if ctx["use_jwt"]:
        tpl_name, out_path = _AUTH_TEMPLATE
        files[out_path] = env.get_template(tpl_name).render(**ctx)

    for pkg in _PACKAGE_DIRS:
        files.setdefault(f"{pkg}/__init__.py", "")

    return files

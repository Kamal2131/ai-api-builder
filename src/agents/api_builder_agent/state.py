"""API Builder Agent state — single source of truth for one build run."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ApiBuilderAgentState(TypedDict, total=False):
    # ── Input ──
    request: str                        # plain-English API description from the user

    # ── Planner output ──
    spec: dict[str, Any]                # {project_name, database, auth, entities: [...]}

    # ── Generation ──
    files: dict[str, str]               # generated project file map: path -> content

    # ── Packaging ──
    zip_bytes: bytes                    # the packaged project archive

    # ── Error ──
    error: str | None

    # ── Audit ──
    messages: Annotated[list[str], operator.add]

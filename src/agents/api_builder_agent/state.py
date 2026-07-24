"""API Builder Agent state — single source of truth for one build run."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_files(current: dict[str, str] | None, update: dict[str, str] | None) -> dict[str, str]:
    """Each generator node merges its slice; a None update wipes the map for a rebuild attempt."""
    if update is None:
        return {}
    return {**(current or {}), **update}


class ApiBuilderAgentState(TypedDict, total=False):
    # ── Input ──
    request: str                        # plain-English API description from the user

    # ── Planner output ──
    spec: dict[str, Any]                # {project_name, database, auth, entities: [...]}
    attempts: int                       # build attempts so far (planner increments)

    # ── Architecture output ──
    context: dict[str, Any]             # shared render context (normalized entities, flags)

    # ── Generation ──
    files: Annotated[dict[str, str], merge_files]

    # ── Review ──
    review_feedback: str | None         # reviewer's problem report, fed back to the planner on retry

    # ── Packaging ──
    zip_bytes: bytes                    # the packaged project archive

    # ── Error ──
    error: str | None

    # ── Audit ──
    messages: Annotated[list[str], operator.add]

"""database node — renders the persistence layer from the shared render context."""

from __future__ import annotations

from agents.api_builder_agent.generators.renderer import render_database
from agents.api_builder_agent.state import ApiBuilderAgentState


def generate_database(state: ApiBuilderAgentState) -> dict:
    """Render engine/session setup and SQLAlchemy models."""
    context = state.get("context")
    if not context:
        return {"error": "No render context for database.", "messages": ["database: missing context"]}

    files = render_database(context)
    return {"files": files, "messages": [f"database: rendered {len(files)} files ({context['database']})"]}

"""backend node — renders the application code from the shared render context."""

from __future__ import annotations

from agents.api_builder_agent.generators.renderer import render_backend
from agents.api_builder_agent.state import ApiBuilderAgentState


def generate_backend(state: ApiBuilderAgentState) -> dict:
    """Render core app modules, per-entity routers, and auth when JWT is requested."""
    context = state.get("context")
    if not context:
        return {"error": "No render context for backend.", "messages": ["backend: missing context"]}

    files = render_backend(context)
    return {"files": files, "messages": [f"backend: rendered {len(files)} files"]}

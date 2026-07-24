"""backend node — renders the FastAPI project files from the planner spec (templates-first)."""

from __future__ import annotations

from agents.api_builder_agent.generators.renderer import render_project
from agents.api_builder_agent.state import ApiBuilderAgentState


def generate_backend(state: ApiBuilderAgentState) -> dict:
    """Render the full project file map from the spec produced by the planner."""
    spec = state.get("spec")
    if not spec:
        return {"error": "No spec to generate from.", "messages": ["backend: missing spec"]}

    files = render_project(spec)
    return {"files": files, "messages": [f"backend: rendered {len(files)} files"]}

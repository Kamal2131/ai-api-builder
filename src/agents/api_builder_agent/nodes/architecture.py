"""architecture node — turns the planner spec into the shared render context and project skeleton."""

from __future__ import annotations

from agents.api_builder_agent.generators.renderer import build_context, render_scaffold
from agents.api_builder_agent.state import ApiBuilderAgentState


def design_architecture(state: ApiBuilderAgentState) -> dict:
    """Normalize the spec into a render context and lay down the project scaffold."""
    spec = state.get("spec")
    if not spec:
        return {"error": "No spec to design from.", "messages": ["architecture: missing spec"]}

    context = build_context(spec)
    files = render_scaffold(context)
    entities = ", ".join(e["name"] for e in context["entities"])
    return {
        "context": context,
        "files": files,
        "messages": [f"architecture: {len(files)} scaffold files, entities [{entities}]"],
    }

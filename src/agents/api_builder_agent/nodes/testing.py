"""testing node — renders the generated project's test suite."""

from __future__ import annotations

from agents.api_builder_agent.generators.renderer import render_tests
from agents.api_builder_agent.state import ApiBuilderAgentState


def generate_tests(state: ApiBuilderAgentState) -> dict:
    """Render the smoke-test suite shipped with the generated project."""
    context = state.get("context")
    if not context:
        return {"error": "No render context for testing.", "messages": ["testing: missing context"]}

    files = render_tests(context)
    return {"files": files, "messages": [f"testing: rendered {len(files)} files"]}

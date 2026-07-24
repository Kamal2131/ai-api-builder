"""API Builder Agent LangGraph — Phase 2 specialized pipeline.

planner → architecture → backend → database → testing → reviewer → package

A failed review loops back to the planner with the reviewer's problem report so
the spec can be corrected; attempts are bounded in the reviewer node.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.api_builder_agent.nodes.architecture import design_architecture
from agents.api_builder_agent.nodes.backend import generate_backend
from agents.api_builder_agent.nodes.database import generate_database
from agents.api_builder_agent.nodes.package import package
from agents.api_builder_agent.nodes.planner import plan
from agents.api_builder_agent.nodes.reviewer import review
from agents.api_builder_agent.nodes.testing import generate_tests
from agents.api_builder_agent.state import ApiBuilderAgentState


def _after_review(state: ApiBuilderAgentState) -> str:
    """Package on success, replan with feedback on a failed attempt, stop on final failure."""
    if state.get("error"):
        return END
    if state.get("review_feedback"):
        return "planner"
    return "package"


def build_graph(checkpointer=None):
    """Wire the Phase 2 flow: plan, design, generate each layer, review, then package."""
    builder = StateGraph(ApiBuilderAgentState)

    builder.add_node("planner", plan)
    builder.add_node("architecture", design_architecture)
    builder.add_node("backend", generate_backend)
    builder.add_node("database", generate_database)
    builder.add_node("testing", generate_tests)
    builder.add_node("reviewer", review)
    builder.add_node("package", package)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "architecture")
    builder.add_edge("architecture", "backend")
    builder.add_edge("backend", "database")
    builder.add_edge("database", "testing")
    builder.add_edge("testing", "reviewer")
    builder.add_conditional_edges(
        "reviewer", _after_review, {"planner": "planner", "package": "package", END: END}
    )
    builder.add_edge("package", END)

    return builder.compile(checkpointer=checkpointer)


def get_default_app():
    """Builds run stateless — a single-shot build needs no checkpointer."""
    return build_graph()

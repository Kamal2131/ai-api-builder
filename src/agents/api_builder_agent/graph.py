"""API Builder Agent LangGraph — planner → backend → package (Phase 1 walking skeleton)."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.api_builder_agent.nodes.backend import generate_backend
from agents.api_builder_agent.nodes.package import package
from agents.api_builder_agent.nodes.planner import plan
from agents.api_builder_agent.state import ApiBuilderAgentState


def build_graph(checkpointer=None):
    """Wire the Phase 1 linear flow: planner → backend → package."""
    builder = StateGraph(ApiBuilderAgentState)

    builder.add_node("planner", plan)
    builder.add_node("backend", generate_backend)
    builder.add_node("package", package)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "backend")
    builder.add_edge("backend", "package")
    builder.add_edge("package", END)

    return builder.compile(checkpointer=checkpointer)


def get_default_app():
    """Phase 1 runs stateless — a single-shot build needs no checkpointer."""
    return build_graph()

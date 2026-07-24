"""Prompts for the API Builder planner node."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

PLANNER_SYSTEM = (
    "You convert a plain-English API description into a strict JSON build spec. "
    "Return ONLY a JSON object (no prose, no code fences) with these keys:\n"
    '  - "project_name": kebab-case string, e.g. "book-api"\n'
    '  - "database": one of "postgres", "mysql", "sqlite"\n'
    '  - "auth": "jwt" or null\n'
    '  - "entities": array of singular PascalCase resource names, e.g. ["Book", "Author"]\n'
    "Infer sensible defaults when the description is vague. Default database to "
    '"postgres" and auth to null unless the description implies otherwise.'
)


def build_planner_messages(request: str) -> list:
    """Build the chat messages that ask the LLM for a structured build spec."""
    return [SystemMessage(content=PLANNER_SYSTEM), HumanMessage(content=request)]

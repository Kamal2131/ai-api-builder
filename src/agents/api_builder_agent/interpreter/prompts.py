"""Prompts for the API Builder planner node.

The planner runs on a small local model (qwen2.5:1.5b), so the prompt leans on
few-shot examples — worked request→spec pairs steer small models far more
reliably than rules alone.
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

PLANNER_SYSTEM = (
    "You are the planner of an API code generator. Convert the user's plain-English "
    "API description into a build spec.\n"
    "Respond with ONLY one JSON object — no prose, no markdown, no code fences.\n"
    "The object has exactly these four keys:\n"
    '  "project_name": short kebab-case name derived from the description, ending in "-api"\n'
    '  "database": "postgres" | "mysql" | "sqlite"\n'
    '  "auth": "jwt" | null\n'
    '  "entities": the data resources that need CRUD endpoints, as singular PascalCase nouns\n'
    "Rules:\n"
    "- Entities are domain objects only. Never list infrastructure or feature words "
    "(Auth, Jwt, Api, Docker, Test, Database) as entities.\n"
    "- Singularize plurals: Books -> Book, Categories -> Category.\n"
    '- Any mention of login, authentication, tokens, or JWT means "auth": "jwt".\n'
    '- Default to "postgres" and "auth": null when the description does not say otherwise.\n'
    "- Every listed resource must appear in entities — do not drop any."
)

# Worked examples sent as real chat turns: an easy case, a no-auth/sqlite case,
# and a vague one that forces sensible defaults.
_EXAMPLES = (
    (
        "Create a Book Management API with JWT auth, CRUD Books and CRUD Authors, "
        "PostgreSQL, Docker, and unit tests.",
        '{"project_name": "book-management-api", "database": "postgres", '
        '"auth": "jwt", "entities": ["Book", "Author"]}',
    ),
    (
        "Simple todo backend storing tasks and tags in sqlite, no login needed.",
        '{"project_name": "todo-api", "database": "sqlite", '
        '"auth": null, "entities": ["Task", "Tag"]}',
    ),
    (
        "I need something to track my movie collection.",
        '{"project_name": "movie-collection-api", "database": "postgres", '
        '"auth": null, "entities": ["Movie"]}',
    ),
)


def build_planner_messages(request: str, feedback: str | None = None,
                           previous_spec: dict | None = None) -> list:
    """Build the chat messages that ask the LLM for a structured build spec.

    When reviewer feedback from a failed attempt is available, the previous spec and
    the problem report are appended so the model returns a corrected spec.
    """
    messages: list = [SystemMessage(content=PLANNER_SYSTEM)]
    for example_request, example_spec in _EXAMPLES:
        messages.append(HumanMessage(content=example_request))
        messages.append(AIMessage(content=example_spec))

    if feedback and previous_spec:
        request = (
            f"{request}\n\n"
            f"Your previous spec was: {json.dumps(previous_spec)}\n"
            f"The project generated from it failed review with these problems: {feedback}\n"
            "Return a corrected JSON spec that fixes every problem."
        )
    messages.append(HumanMessage(content=request))
    return messages

"""planner node — turns a plain-English API request into a structured build spec."""

from __future__ import annotations

import json
import logging
import re

from agents.api_builder_agent.interpreter.prompts import build_planner_messages
from agents.api_builder_agent.state import ApiBuilderAgentState
from llm import get_llm

logger = logging.getLogger(__name__)

_DB_KEYWORDS = {
    "postgres": ("postgres", "postgresql"),
    "mysql": ("mysql",),
    "sqlite": ("sqlite",),
}
_VALID_DATABASES = frozenset(_DB_KEYWORDS)

# Feature/infra words small models sometimes emit as entities despite the prompt.
_NON_ENTITY_WORDS = frozenset({"auth", "jwt", "api", "crud", "docker", "test", "tests", "database"})


def _slug(text: str) -> str:
    """Kebab-case a free-text name into a safe project slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "generated-api"


def _parse_llm_json(content: str) -> dict | None:
    """Extract a JSON object from an LLM response, tolerating code fences and stray prose."""
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```")
        stripped = stripped.removesuffix("```").strip()
    candidates = [stripped]

    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _fallback_spec(request: str) -> dict:
    """Deterministic spec when the LLM is unavailable or returns nothing usable."""
    text = request.lower()

    database = "postgres"
    for name, keywords in _DB_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            database = name
            break

    auth = "jwt" if ("jwt" in text or "auth" in text) else None

    entities = []
    for match in re.findall(r"crud\s+([a-zA-Z]+)", text):
        singular = match[:-1] if match.endswith("s") else match
        entities.append(singular.capitalize())
    entities = list(dict.fromkeys(entities)) or ["Item"]

    # Words are matched as unambiguous [a-z]+ tokens with single separators so the
    # regex can't backtrack super-linearly (text is already lowercased).
    name_match = re.search(r"(?:create|build|generate)\s+(?:an?\s+)?([a-z]+(?:\s+[a-z]+)*?)\s+api\b",
                           text)
    project = name_match.group(1).strip() if name_match else "generated api"

    return {
        "project_name": _slug(f"{project} api"),
        "database": database,
        "auth": auth,
        "entities": entities,
    }


def _normalize_spec(spec: dict, request: str) -> dict:
    """Coerce a raw spec (LLM or fallback) into the shape the renderer expects."""
    spec["project_name"] = _slug(str(spec.get("project_name") or "generated-api"))

    database = str(spec.get("database") or "postgres").lower()
    spec["database"] = database if database in _VALID_DATABASES else "postgres"

    auth = spec.get("auth")
    spec["auth"] = "jwt" if (isinstance(auth, str) and auth.lower() == "jwt") else None

    entities = [str(e).strip() for e in (spec.get("entities") or []) if str(e).strip()]
    entities = [e for e in dict.fromkeys(entities) if e.lower() not in _NON_ENTITY_WORDS]
    spec["entities"] = entities or _fallback_spec(request)["entities"]
    return spec


def plan(state: ApiBuilderAgentState) -> dict:
    """Produce the build spec from the request, preferring the LLM, falling back to heuristics.

    On a retry the reviewer's problem report and the previous spec are included in
    the prompt so the LLM can correct the spec instead of repeating the same mistake.
    """
    request = str(state.get("request", "")).strip()
    if not request:
        return {"error": "No API description provided.", "messages": ["planner: empty request"]}

    attempts = state.get("attempts", 0) + 1
    feedback = state.get("review_feedback")

    spec = None
    try:
        messages = build_planner_messages(request, feedback=feedback,
                                          previous_spec=state.get("spec"))
        response = get_llm().invoke(messages)
        spec = _parse_llm_json(getattr(response, "content", str(response)))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("[api_builder.planner] LLM planning failed, using fallback: %s", exc)

    if not spec or not spec.get("entities"):
        spec = _fallback_spec(request)

    spec = _normalize_spec(spec, request)
    return {
        "spec": spec,
        "attempts": attempts,
        "review_feedback": None,  # consumed — a stale report must not leak into the next review
        "messages": [f"planner (attempt {attempts}): {spec}"],
    }

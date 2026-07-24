"""Process-wide LLM accessor — an OpenAI-compatible chat model built lazily on first use.

Defaults target a local Ollama server (qwen2.5:1.5b) via its OpenAI-compatible /v1 API.
Any OpenAI-compatible endpoint (Ollama, vLLM, ...) works by setting LLM_BASE_URL /
LLM_API_KEY / LLM_MODEL in the environment.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

_llm: Any = None


def _build_llm() -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=lambda: settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
    )


def get_llm() -> Any:
    """Return the shared chat model, constructing it on first use."""
    global _llm  # pylint: disable=global-statement
    if _llm is None:
        _llm = _build_llm()
    return _llm

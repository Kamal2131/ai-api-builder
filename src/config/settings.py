"""Process-wide settings sourced from the environment (.env)."""

from __future__ import annotations

import os


class Settings:
    """Runtime configuration for the AI API Builder service."""

    port: int = int(os.getenv("PORT", "8080"))
    root_path: str = os.getenv("ROOT_PATH", "")

    # LLM — OpenAI-compatible endpoint. Defaults target a local Ollama server
    # (Qwen2.5-3B). Ollama exposes an OpenAI-compatible API at /v1, so the same
    # ChatOpenAI client swaps to vLLM later by changing these env vars only.
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))


settings = Settings()

"""Process-wide settings sourced from the environment (.env)."""

from __future__ import annotations

import os


class Settings:
    """Runtime configuration for the AI API Builder service."""

    # Loopback by default — binding all interfaces is opt-in (Docker sets its
    # own 0.0.0.0 via the uvicorn CLI, where the container boundary protects it).
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8080"))
    root_path: str = os.getenv("ROOT_PATH", "")

    # Build-history persistence (Phase 3). Empty means persistence is disabled —
    # the API still builds projects, it just doesn't record them.
    database_url: str = os.getenv("DATABASE_URL", "")

    # Build-result cache (Phase 3). Empty disables caching; identical requests
    # then always rebuild. TTL bounds how long a cached ZIP is served.
    redis_url: str = os.getenv("REDIS_URL", "")
    build_cache_ttl: int = int(os.getenv("BUILD_CACHE_TTL", "3600"))

    # ZIP offload to S3 (Phase 3). Empty bucket keeps ZIPs inline in the
    # database. Endpoint override targets MinIO/LocalStack in local dev.
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "")

    # LLM — OpenAI-compatible endpoint. Defaults target a local Ollama server
    # (qwen2.5:1.5b). Ollama exposes an OpenAI-compatible API at /v1, so the same
    # ChatOpenAI client swaps to vLLM later by changing these env vars only.
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))


settings = Settings()

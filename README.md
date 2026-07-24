# AI API Builder

Describe an API in plain English; the agent generates a production-ready FastAPI project and returns it as a downloadable ZIP.

## How it works (Phase 1)

A LangGraph agent runs three nodes

```
request → planner → backend → package → ZIP
```

- **planner** (`nodes/planner.py`) parses the request into a build spec `{project_name, database, auth, entities}` using the LLM, with a deterministic regex fallback when no LLM is reachable.
- **backend** (`nodes/backend.py`) renders a working FastAPI project from Jinja templates in `agents/api_builder_agent/templates/fastapi/` (templates-first — deterministic, always-valid Python).
- **package** (`nodes/package.py`) zips the file map.

## Project layout

```
src/
├── server.py                     # FastAPI entry point
├── llm.py                        # OpenAI-compatible LLM accessor (Ollama / vLLM, Qwen2.5-3B)
├── config/settings.py
├── controllers/
│   ├── health.py
│   └── api_builder.py            # POST /api/build → ZIP
└── agents/api_builder_agent/
    ├── graph.py                  # planner → backend → package
    ├── state.py
    ├── interpreter/prompts.py
    ├── generators/renderer.py
    ├── nodes/{planner,backend,package}.py
    └── templates/fastapi/*.jinja
tests/
```

## Run the model locally (Ollama in Docker)

The LLM runs locally via [Ollama](https://ollama.com). The whole stack (Ollama + the
builder API) comes up with Docker Compose:

```bash
docker compose up --build -d
# One-time: pull the model into the Ollama container
docker compose exec ollama ollama pull qwen2.5:3b   # or: phi3:3.8b
```

The API is then on http://localhost:8080 and reaches Ollama at `http://ollama:11434/v1`.

## Run the API without Docker

```bash
python -m venv venv
venv/Scripts/pip install -r requirements.txt
cd src && ../venv/Scripts/uvicorn server:app --reload --port 8080
```

This talks to an Ollama server on the host (`http://localhost:11434/v1`). Install Ollama,
then `ollama pull qwen2.5:3b`. See `.env.example` to point at a different endpoint (e.g. vLLM).

## Generate a project

```bash
curl -X POST http://localhost:8080/api/build \
  -H "Content-Type: application/json" \
  -d '{"request": "Create a Book Management API with JWT auth, CRUD Books and Authors, PostgreSQL, Docker, and tests."}' \
  --output book-api.zip
```

The LLM is optional for a first run: without a reachable endpoint the planner falls back to
heuristics, so generation still works.

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR: **ruff** lint → **pytest** (hermetic — no
LLM needed) → **docker build**. The docker-build job only runs if lint and tests pass.

## Tests

```bash
venv/Scripts/pytest
```

## Roadmap

- **Phase 1 (this):** single-agent templates-first generator → ZIP.
- **Phase 2:** split into planner → architecture → backend → database → testing → reviewer nodes.
- **Phase 3:** AWS backing (vLLM on EC2 GPU, Postgres, Redis, S3).
- **Phase 4–7:** GitHub push, Docker verify, CI/CD generation, ECS deploy agent.

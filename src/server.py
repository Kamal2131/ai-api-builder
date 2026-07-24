"""FastAPI application entry point for the AI API Builder."""

from pathlib import Path

import uvicorn
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# pylint: disable=wrong-import-position
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from controllers import api_builder, builds, health

# pylint: enable=wrong-import-position

app = FastAPI(title="AI API Builder", root_path=settings.root_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(api_builder.router)
app.include_router(builds.router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_config=None)

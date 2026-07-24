"""package node — zips the generated file map into a downloadable archive."""

from __future__ import annotations

import io
import zipfile

from agents.api_builder_agent.state import ApiBuilderAgentState


def package(state: ApiBuilderAgentState) -> dict:
    """Bundle every generated file under the project root into an in-memory ZIP."""
    files = state.get("files") or {}
    if not files:
        return {"error": "Nothing to package.", "messages": ["package: no files"]}

    project = state.get("spec", {}).get("project_name", "generated-api")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            archive.writestr(f"{project}/{path}", content)

    return {
        "zip_bytes": buffer.getvalue(),
        "messages": [f"package: {len(files)} files -> {project}.zip"],
    }

# pylint: disable=import-error,no-name-in-module
"""Build history endpoints — list past builds and re-download their ZIPs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

import db

router = APIRouter(prefix="/api/builds", tags=["builds"])


@router.get("", responses={
    503: {"description": "Build history is disabled — no DATABASE_URL configured."},
})
def history(limit: int = 50) -> list[dict]:
    """Recent build runs, newest first, without ZIP payloads."""
    builds = db.list_builds(limit=limit)
    if builds is None:
        raise HTTPException(status_code=503, detail="Build history requires DATABASE_URL.")
    return builds


@router.get("/{build_id}/download", responses={
    404: {"description": "Unknown build id, or the build has no stored ZIP."},
})
def download(build_id: int) -> Response:
    """Re-download the ZIP of a previously successful build."""
    stored = db.get_build_zip(build_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="No stored ZIP for this build.")

    project, zip_bytes = stored
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project}.zip"'},
    )

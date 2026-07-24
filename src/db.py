"""Build-run persistence — optional Postgres-backed history of every build.

Persistence is opt-in via DATABASE_URL. Without it — or with the database
unreachable — the API keeps building projects and simply skips recording,
mirroring the planner's LLM-fallback philosophy. A failed connection is retried
on the next call rather than disabling persistence for the process lifetime.

ZIP bytes are stored inline for now; they move to S3 later in Phase 3.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, LargeBinary, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config.settings import settings

logger = logging.getLogger(__name__)

_session_factory = None


class Base(DeclarativeBase):
    pass


class BuildRecord(Base):
    """One build run — what was asked, what was decided, and what came out."""

    __tablename__ = "builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    request: Mapped[str] = mapped_column(Text)
    project_name: Mapped[str] = mapped_column(String(200))
    spec: Mapped[str] = mapped_column(Text)                     # build spec as JSON
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))             # "success" | "failed"
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    zip_size: Mapped[int] = mapped_column(Integer, default=0)
    zip_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


def _get_session_factory():
    """Build the session factory on first use; None means persistence is off or down."""
    global _session_factory  # pylint: disable=global-statement
    if _session_factory is not None:
        return _session_factory
    if not settings.database_url:
        return None

    try:
        # Fail fast when the database is unreachable — a build request must degrade
        # to "not recorded" in seconds, not hang on TCP connect timeouts.
        connect_args = {}
        if settings.database_url.startswith("postgresql"):
            connect_args["connect_timeout"] = 3
        engine = create_engine(settings.database_url, pool_pre_ping=True,
                               connect_args=connect_args)
        Base.metadata.create_all(engine)
        _session_factory = sessionmaker(bind=engine)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("[db] database unavailable, build not recorded: %s", exc)
        return None
    return _session_factory


def record_build(*, request: str, spec: dict | None, attempts: int, status: str,
                 error: str | None = None, zip_bytes: bytes | None = None) -> int | None:
    """Persist one build run; returns the record id, or None when persistence is off."""
    factory = _get_session_factory()
    if factory is None:
        return None

    try:
        with factory() as session:
            record = BuildRecord(
                request=request,
                project_name=(spec or {}).get("project_name", "generated-api"),
                spec=json.dumps(spec or {}),
                attempts=attempts,
                status=status,
                error=error,
                zip_size=len(zip_bytes) if zip_bytes else 0,
                zip_bytes=zip_bytes,
            )
            session.add(record)
            session.commit()
            return record.id
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("[db] failed to record build: %s", exc)
        return None


def list_builds(limit: int = 50) -> list[dict] | None:
    """Recent build history without ZIP payloads; None when persistence is off."""
    factory = _get_session_factory()
    if factory is None:
        return None

    with factory() as session:
        records = session.scalars(
            select(BuildRecord).order_by(BuildRecord.id.desc()).limit(limit)
        )
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "request": r.request,
                "project_name": r.project_name,
                "spec": json.loads(r.spec),
                "attempts": r.attempts,
                "status": r.status,
                "error": r.error,
                "zip_size": r.zip_size,
            }
            for r in records
        ]


def get_build_zip(build_id: int) -> tuple[str, bytes] | None:
    """(project_name, zip_bytes) for a stored successful build, else None."""
    factory = _get_session_factory()
    if factory is None:
        return None

    with factory() as session:
        record = session.get(BuildRecord, build_id)
        if record is None or not record.zip_bytes:
            return None
        return record.project_name, record.zip_bytes

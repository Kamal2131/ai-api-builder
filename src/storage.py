"""Generated-ZIP storage — optional S3 offload for build archives.

Opt-in via S3_BUCKET; credentials and region come from the standard AWS
environment (env vars, shared config, or instance role). When the bucket is
unset or an upload fails, ZIP bytes simply stay inline in the build-history
database — the pre-S3 behavior — so a build is never lost to a storage outage.
S3_ENDPOINT_URL points the client at MinIO/LocalStack for local development.
"""

from __future__ import annotations

import logging
import uuid

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Build the S3 client on first use; None means offload is off."""
    global _client  # pylint: disable=global-statement
    if _client is not None:
        return _client
    if not settings.s3_bucket:
        return None

    import boto3
    from botocore.config import Config

    # Fail fast on network trouble — callers fall back to inline DB storage.
    config = Config(connect_timeout=3, read_timeout=10, retries={"max_attempts": 2})
    kwargs = {"config": config}
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    _client = boto3.client("s3", **kwargs)
    return _client


def store_zip(project_name: str, zip_bytes: bytes) -> str | None:
    """Upload a build ZIP; returns its object key, or None when S3 is off or failed."""
    client = _get_client()
    if client is None:
        return None

    key = f"builds/{uuid.uuid4().hex}/{project_name}.zip"
    try:
        client.put_object(Bucket=settings.s3_bucket, Key=key,
                          Body=zip_bytes, ContentType="application/zip")
        return key
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("[storage] S3 upload failed, keeping ZIP inline: %s", exc)
        return None


def fetch_zip(key: str) -> bytes | None:
    """Download a stored build ZIP by key, or None when unavailable."""
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.get_object(Bucket=settings.s3_bucket, Key=key)
        return response["Body"].read()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("[storage] S3 download failed for %s: %s", key, exc)
        return None

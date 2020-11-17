# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime
from datetime import timedelta
from typing import Iterator
from typing import Optional
from typing import Tuple

import pytz
import structlog
import zstandard
from google.cloud import storage as gcp_storage
from google.oauth2.service_account import Credentials

logger = structlog.get_logger(__name__)

DEFAULT_FILTER = "all"


def get_bucket(service_account: str) -> gcp_storage.bucket.Bucket:
    """
    Build a Google Cloud Storage client & bucket
    from Taskcluster secret
    """
    assert isinstance(service_account, dict)

    # Load credentials from Taskcluster secret
    if "bucket" not in service_account:
        raise KeyError("Missing bucket in GOOGLE_CLOUD_STORAGE")
    bucket = service_account["bucket"]

    # Use those credentials to create a Storage client
    # The project is needed to avoid checking env variables and crashing
    creds = Credentials.from_service_account_info(service_account)
    client = gcp_storage.Client(project=creds.project_id, credentials=creds)

    return client.get_bucket(bucket)


def get_name(repository: str, changeset: str, platform: str, suite: str) -> str:
    return f"{repository}/{changeset}/{platform}:{suite}"


def download_report(
    base_dir: str, bucket: gcp_storage.bucket.Bucket, name: str
) -> bool:
    path = f"{name}.json"
    archive_path = f"{name}.json.zstd"
    full_archive_path = os.path.join(base_dir, archive_path)
    full_path = os.path.join(base_dir, path)

    blob = bucket.blob(archive_path)
    if not blob.exists():
        logger.debug("No report found on GCP", path=archive_path)
        return False

    if os.path.exists(full_path):
        logger.info("Report already available", path=full_path)
        return True

    os.makedirs(os.path.dirname(full_archive_path), exist_ok=True)
    blob.download_to_filename(full_archive_path)
    logger.info("Downloaded report archive", path=full_archive_path)

    with open(full_path, "wb") as output:
        with open(full_archive_path, "rb") as archive:
            dctx = zstandard.ZstdDecompressor()
            reader = dctx.stream_reader(archive)
            while True:
                chunk = reader.read(16384)
                if not chunk:
                    break
                output.write(chunk)

    os.unlink(full_archive_path)
    return True


def list_reports(
    bucket: gcp_storage.bucket.Bucket, repository: str, until: Optional[datetime] = None
) -> Iterator[Tuple[str, str, str]]:
    REGEX_BLOB = re.compile(
        r"^{}/(\w+)/([\w\-]+):([\w\-]+).json.zstd$".format(repository)
    )
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    for blob in bucket.list_blobs(prefix=repository):
        if isinstance(until, timedelta) and (now - blob.time_created) >= until:
            logger.debug(f"Skipping old blob {blob}")
            continue

        # Get changeset from blob name
        match = REGEX_BLOB.match(blob.name)
        if match is None:
            logger.warn("Invalid blob found {}".format(blob.name))
            continue
        changeset = match.group(1)
        platform = match.group(2)
        suite = match.group(3)

        # Build report instance and ingest it
        yield changeset, platform, suite

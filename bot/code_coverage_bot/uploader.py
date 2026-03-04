# -*- coding: utf-8 -*-
import itertools
import os.path

import structlog
import zstandard as zstd
from google.cloud.storage.bucket import Bucket

from code_coverage_bot.secrets import secrets
from code_coverage_bot.gcp import get_bucket
from code_coverage_bot import hgmo

logger = structlog.get_logger(__name__)
GCP_COVDIR_PATH = "{repository}/{revision}/{platform}:{suite}.json.zstd"


def gcp(repository, revision, report, platform, suite):
    """
    Upload a grcov raw report on Google Cloud Storage
    * Compress with zstandard
    * Upload on bucket using revision in name
    * Trigger ingestion on channel's backend
    """
    assert isinstance(report, bytes)
    assert isinstance(platform, str)
    assert isinstance(suite, str)
    bucket = get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])

    # Compress report
    compressor = zstd.ZstdCompressor(threads=-1)
    archive = compressor.compress(report)

    # Upload archive
    path = GCP_COVDIR_PATH.format(
        repository=repository, revision=revision, platform=platform, suite=suite
    )
    blob = bucket.blob(path)
    blob.upload_from_string(archive)

    # Update headers
    blob.content_type = "application/json"
    blob.content_encoding = "zstd"
    blob.patch()

    logger.info("Uploaded {} on {}".format(path, bucket))

    return blob


def gcp_covdir_exists(
    bucket: Bucket, repository: str, revision: str, platform: str, suite: str
) -> bool:
    """
    Check if a covdir report exists on the Google Cloud Storage bucket
    """
    path = GCP_COVDIR_PATH.format(
        repository=repository, revision=revision, platform=platform, suite=suite
    )
    blob = bucket.blob(path)
    return blob.exists()


def gcp_latest(repo_url):
    """
    List the latest reports ingested on the backend
    """
    assert (
        secrets[secrets.GOOGLE_CLOUD_STORAGE] is not None
    ), "Missing GOOGLE_CLOUD_STORAGE secret"
    bucket = get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])

    for push_id, push_data in hgmo.iter_pushes(server_address=repo_url):
        changesets: list[str] = push_data.get("changesets", [])
        if not changesets:
            continue

        if gcp_covdir_exists(bucket, "mozilla-central", changesets[-1], "all", "all"):
            return changesets[-1]

    return None


def covdir_paths(report):
    """
    Load a covdir report and recursively list all the paths
    """
    assert isinstance(report, dict)

    def _extract(obj, base_path=""):
        out = []
        children = obj.get("children", {})
        if children:
            # Recursive on folder files
            out += itertools.chain(
                *[
                    _extract(child, os.path.join(base_path, obj["name"]))
                    for child in children.values()
                ]
            )

        else:
            # Add full filename
            out.append(os.path.join(base_path, obj["name"]))

        return out

    return _extract(report)

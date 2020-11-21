# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io
import json
import os
import time

import structlog
import zstandard
from tqdm import tqdm

from code_coverage_bot import hgmo
from code_coverage_bot.phabricator import PhabricatorUploader
from code_coverage_bot.secrets import secrets
from code_coverage_tools.gcp import DEFAULT_FILTER
from code_coverage_tools.gcp import download_report
from code_coverage_tools.gcp import get_bucket
from code_coverage_tools.gcp import get_name
from code_coverage_tools.gcp import list_reports

logger = structlog.get_logger(__name__)


def generate(server_address: str, repo_dir: str, out_dir: str = ".") -> None:
    start_time = time.monotonic()

    commit_coverage_path = os.path.join(out_dir, "commit_coverage.json.zst")

    assert (
        secrets[secrets.GOOGLE_CLOUD_STORAGE] is not None
    ), "Missing GOOGLE_CLOUD_STORAGE secret"
    bucket = get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])

    blob = bucket.blob("commit_coverage.json.zst")
    if blob.exists():
        dctx = zstandard.ZstdDecompressor()
        commit_coverage = json.loads(dctx.decompress(blob.download_as_bytes()))
    else:
        commit_coverage = {}

    cctx = zstandard.ZstdCompressor(threads=-1)

    def _upload():
        blob = bucket.blob("commit_coverage.json.zst")
        blob.upload_from_string(
            cctx.compress(json.dumps(commit_coverage).encode("ascii"))
        )
        blob.content_type = "application/json"
        blob.content_encoding = "zstd"
        blob.patch()

    # We are only interested in "overall" coverage, not platform or suite specific.
    changesets_to_analyze = [
        changeset
        for changeset, platform, suite in list_reports(bucket, "mozilla-central")
        if platform == DEFAULT_FILTER and suite == DEFAULT_FILTER
    ]

    # Skip already analyzed changesets.
    changesets_to_analyze = [
        changeset
        for changeset in changesets_to_analyze
        if changeset not in commit_coverage
    ]

    for changeset_to_analyze in tqdm(changesets_to_analyze):
        report_name = get_name(
            "mozilla-central", changeset_to_analyze, DEFAULT_FILTER, DEFAULT_FILTER
        )
        assert download_report(
            os.path.join(out_dir, "ccov-reports"), bucket, report_name
        )

        with open(
            os.path.join(out_dir, "ccov-reports", f"{report_name}.json"), "r"
        ) as f:
            report = json.load(f)

        phabricatorUploader = PhabricatorUploader(
            repo_dir, changeset_to_analyze, warnings_enabled=False
        )

        # Use the hg.mozilla.org server to get the automation relevant changesets, since
        # this information is broken in our local repo (which mozilla-unified).
        with hgmo.HGMO(server_address=server_address) as hgmo_remote_server:
            changesets = hgmo_remote_server.get_automation_relevance_changesets(
                changeset_to_analyze
            )

        # Use the local server to generate the coverage mapping, as it is faster and
        # correct.
        with hgmo.HGMO(repo_dir=repo_dir) as hgmo_local_server:
            results = phabricatorUploader.generate(
                hgmo_local_server, report, changesets
            )

        for changeset in changesets:
            # Lookup changeset coverage from phabricator uploader
            coverage = results.get(changeset["node"])
            if coverage is None:
                logger.info("No coverage found", changeset=changeset)
                commit_coverage[changeset["node"]] = None
                continue

            commit_coverage[changeset["node"]] = {
                "added": sum(c["lines_added"] for c in coverage["paths"].values()),
                "covered": sum(c["lines_covered"] for c in coverage["paths"].values()),
                "unknown": sum(c["lines_unknown"] for c in coverage["paths"].values()),
            }

        if time.monotonic() - start_time >= 3600:
            _upload()
            start_time = time.monotonic()

    _upload()

    with open(commit_coverage_path, "wb") as zf:
        with cctx.stream_writer(zf) as compressor:
            with io.TextIOWrapper(compressor, encoding="ascii") as f:
                json.dump(commit_coverage, f)

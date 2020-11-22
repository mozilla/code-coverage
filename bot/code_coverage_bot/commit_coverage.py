# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import concurrent.futures
import io
import json
import os
import threading
import time

import hglib
import structlog
import zstandard
from tqdm import tqdm

from code_coverage_bot import hgmo
from code_coverage_bot.phabricator import PhabricatorUploader
from code_coverage_bot.secrets import secrets
from code_coverage_bot.utils import ThreadPoolExecutorResult
from code_coverage_tools.gcp import DEFAULT_FILTER
from code_coverage_tools.gcp import download_report
from code_coverage_tools.gcp import get_bucket
from code_coverage_tools.gcp import get_name
from code_coverage_tools.gcp import list_reports

logger = structlog.get_logger(__name__)

hg_servers = list()
hg_servers_lock = threading.Lock()
thread_local = threading.local()


def _init_thread(repo_dir: str) -> None:
    hg_server = hglib.open(repo_dir)
    thread_local.hg = hg_server
    with hg_servers_lock:
        hg_servers.append(hg_server)


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

    # Use the local server to generate the coverage mapping, as it is faster and
    # correct.
    def analyze_changeset(changeset_to_analyze: str) -> None:
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

        results = phabricatorUploader.generate(thread_local.hg, report, changesets)

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

    max_workers = min(32, (os.cpu_count() or 1) + 4)
    logger.info(f"Analyzing {len(changesets_to_analyze)} with {max_workers} workers")

    with ThreadPoolExecutorResult(
        initializer=_init_thread, initargs=(repo_dir,)
    ) as executor:

        futures = [
            executor.submit(analyze_changeset, changeset)
            for changeset in changesets_to_analyze
        ]
        for changeset, future in tqdm(
            zip(changesets_to_analyze, concurrent.futures.as_completed(futures)),
            total=len(futures),
        ):
            exc = future.exception()
            if exc is not None:
                logger.error(f"Exception {exc} while analyzing {changeset}")

            if time.monotonic() - start_time >= 3600:
                _upload()
                start_time = time.monotonic()

    while len(hg_servers) > 0:
        hg_server = hg_servers.pop()
        hg_server.close()

    _upload()

    with open(commit_coverage_path, "wb") as zf:
        with cctx.stream_writer(zf) as compressor:
            with io.TextIOWrapper(compressor, encoding="ascii") as f:
                json.dump(commit_coverage, f)

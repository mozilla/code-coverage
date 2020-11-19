# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io
import os
from datetime import datetime
from datetime import timedelta

import requests
import structlog
import zstandard
from taskcluster.utils import slugId

from code_coverage_bot import config
from code_coverage_bot import hgmo
from code_coverage_bot import taskcluster
from code_coverage_bot import uploader
from code_coverage_bot import utils
from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config
from code_coverage_tools.gcp import get_bucket

logger = structlog.get_logger(__name__)


def trigger_task(task_group_id: str, revision: str) -> None:
    """
    Trigger a code coverage task to build covdir at a specified revision
    """
    hooks = taskcluster_config.get_service("hooks")
    hooks.triggerHook(
        "project-relman",
        f"code-coverage-repo-{secrets[secrets.APP_CHANNEL]}",
        {
            "REPOSITORY": config.MOZILLA_CENTRAL_REPOSITORY,
            "REVISION": revision,
            "taskGroupId": task_group_id,
            "taskName": "covdir for {}".format(revision),
        },
    )


def trigger_missing(repo_dir: str, out_dir: str = ".") -> None:
    triggered_revisions_path = os.path.join(out_dir, "triggered_revisions.zst")

    url = f"https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.{secrets[secrets.APP_CHANNEL]}.cron.latest/artifacts/public/triggered_revisions.zst"  # noqa
    r = requests.head(url, allow_redirects=True)
    if r.status_code != 404:
        utils.download_file(url, triggered_revisions_path)

    try:
        dctx = zstandard.ZstdDecompressor()
        with open(triggered_revisions_path, "rb") as zf:
            with dctx.stream_reader(zf) as reader:
                with io.TextIOWrapper(reader, encoding="ascii") as f:
                    triggered_revisions = set(rev for rev in f.read().splitlines())
    except FileNotFoundError:
        triggered_revisions = set()

    # Get all mozilla-central revisions from the past year.
    days = 365 if secrets[secrets.APP_CHANNEL] == "production" else 90
    a_year_ago = datetime.utcnow() - timedelta(days=days)
    with hgmo.HGMO(repo_dir=repo_dir) as hgmo_server:
        data = hgmo_server.get_pushes(
            startDate=a_year_ago.strftime("%Y-%m-%d"), full=False, tipsonly=True
        )

    revisions = [
        (push_data["changesets"][0], int(push_data["date"]))
        for push_data in data["pushes"].values()
    ]

    logger.info(f"{len(revisions)} pushes in the past year")

    assert (
        secrets[secrets.GOOGLE_CLOUD_STORAGE] is not None
    ), "Missing GOOGLE_CLOUD_STORAGE secret"
    bucket = get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])

    missing_revisions = []
    for revision, timestamp in revisions:
        # Skip revisions that have already been triggered. If they are still missing,
        # it means there is a problem that is preventing us from ingesting them.
        if revision in triggered_revisions:
            continue

        # If the revision was already ingested, we don't need to trigger ingestion for it again.
        if uploader.gcp_covdir_exists(
            bucket, "mozilla-central", revision, "all", "all"
        ):
            triggered_revisions.add(revision)
            continue

        missing_revisions.append((revision, timestamp))

    logger.info(f"{len(missing_revisions)} missing pushes in the past year")

    yesterday = int(datetime.timestamp(datetime.utcnow() - timedelta(days=1)))

    task_group_id = slugId()
    logger.info(f"Triggering tasks in the {task_group_id} group")
    for revision, timestamp in missing_revisions:
        # If it's older than yesterday, we assume the group finished.
        # If it is newer than yesterday, we load the group and check if all tasks in it finished.
        if timestamp > yesterday:
            decision_task_id = taskcluster.get_decision_task(
                "mozilla-central", revision
            )
            if decision_task_id is None:
                continue

            group = taskcluster.get_task_details(decision_task_id)["taskGroupId"]
            if not all(
                task["status"]["state"] in taskcluster.FINISHED_STATUSES
                for task in taskcluster.get_tasks_in_group(group)
                if taskcluster.is_coverage_task(task["task"])
            ):
                continue

        trigger_task(task_group_id, revision)
        triggered_revisions.add(revision)

    cctx = zstandard.ZstdCompressor(threads=-1)
    with open(triggered_revisions_path, "wb") as zf:
        with cctx.stream_writer(zf) as compressor:
            with io.TextIOWrapper(compressor, encoding="ascii") as f:
                f.write("\n".join(triggered_revisions))

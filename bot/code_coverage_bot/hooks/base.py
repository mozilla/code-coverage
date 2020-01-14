# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
from datetime import datetime
from datetime import timedelta

import hglib
import structlog

from code_coverage_bot import config
from code_coverage_bot import grcov
from code_coverage_bot import taskcluster
from code_coverage_bot.artifacts import ArtifactsHandler
from code_coverage_bot.taskcluster import taskcluster_config
from code_coverage_bot.utils import ThreadPoolExecutorResult

logger = structlog.get_logger(__name__)


class Hook(object):
    def __init__(
        self,
        repository,
        revision,
        task_name_filter,
        cache_root,
        working_dir,
        required_platforms=[],
    ):
        os.makedirs(working_dir, exist_ok=True)
        self.artifacts_dir = os.path.join(working_dir, "ccov-artifacts")
        self.reports_dir = os.path.join(working_dir, "ccov-reports")
        logger.info(
            "Local storage initialized.",
            artifacts=self.artifacts_dir,
            reports=self.reports_dir,
        )

        self.repository = repository
        self.revision = revision
        assert (
            self.revision is not None and self.repository is not None
        ), "Missing repo/revision"
        logger.info(
            "Mercurial setup", repository=self.repository, revision=self.revision
        )

        assert os.path.isdir(cache_root), f"Cache root {cache_root} is not a dir."
        self.repo_dir = os.path.join(cache_root, self.branch)

        # Load coverage tasks for all platforms
        decision_task_id = taskcluster.get_decision_task(self.branch, self.revision)

        group = taskcluster.get_task_details(decision_task_id)["taskGroupId"]

        test_tasks = [
            task
            for task in taskcluster.get_tasks_in_group(group)
            if taskcluster.is_coverage_task(task["task"])
        ]

        # Check the required platforms are present
        platforms = set(
            taskcluster.get_platform(test_task["task"]) for test_task in test_tasks
        )
        for platform in required_platforms:
            assert platform in platforms, f"{platform} missing in the task group."

        self.artifactsHandler = ArtifactsHandler(
            test_tasks, self.artifacts_dir, task_name_filter
        )

    @property
    def branch(self):
        return self.repository[len(config.HG_BASE) :]

    def clone_repository(self):
        cmd = hglib.util.cmdbuilder(
            "robustcheckout",
            self.repository,
            self.repo_dir,
            purge=True,
            sharebase="hg-shared",
            upstream="https://hg.mozilla.org/mozilla-unified",
            revision=self.revision,
            networkattempts=7,
        )

        cmd.insert(0, hglib.HGPATH)

        proc = hglib.util.popen(cmd)
        out, err = proc.communicate()
        if proc.returncode:
            raise hglib.error.CommandError(cmd, proc.returncode, out, err)

        logger.info("{} cloned".format(self.repository))

    def retrieve_source_and_artifacts(self):
        with ThreadPoolExecutorResult(max_workers=2) as executor:
            # Thread 1 - Download coverage artifacts.
            executor.submit(self.artifactsHandler.download_all)

            # Thread 2 - Clone repository.
            executor.submit(self.clone_repository)

    def build_reports(self, only=None):
        """
        Build all the possible covdir reports using current artifacts
        """
        os.makedirs(self.reports_dir, exist_ok=True)

        reports = {}
        for (
            (platform, suite),
            artifacts,
        ) in self.artifactsHandler.get_combinations().items():

            if only is not None and (platform, suite) not in only:
                continue

            # Generate covdir report for that suite & platform
            logger.info(
                "Building covdir suite report",
                suite=suite,
                platform=platform,
                artifacts=len(artifacts),
            )
            output = grcov.report(
                artifacts, source_dir=self.repo_dir, out_format="covdir"
            )

            # Write output on FS
            path = os.path.join(self.reports_dir, f"{platform}.{suite}.json")
            with open(path, "wb") as f:
                f.write(output)

            reports[(platform, suite)] = path

        return reports

    def index_task(self, namespaces, ttl=180):
        """
        Index current task on Taskcluster Index
        TTL is expressed in days
        """
        assert isinstance(ttl, int) and ttl > 0
        task_id = os.environ.get("TASK_ID")
        if task_id is None:
            logger.warning("Skipping Taskcluster indexation, no task id found.")
            return

        index_service = taskcluster_config.get_service("index")

        for namespace in namespaces:
            index_service.insertTask(
                namespace,
                {
                    "taskId": task_id,
                    "rank": 0,
                    "data": {},
                    "expires": (datetime.utcnow() + timedelta(ttl)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                },
            )

# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import concurrent.futures
import os
import shutil
import subprocess

import hglib
import structlog

from code_coverage_bot import config
from code_coverage_bot import grcov
from code_coverage_bot import taskcluster
from code_coverage_bot.artifacts import ArtifactsHandler
from code_coverage_bot.taskcluster import taskcluster_config
from code_coverage_bot.utils import ThreadPoolExecutorResult

logger = structlog.get_logger(__name__)

# Leaves whose artifacts are at most this big (compressed, in bytes) are built in
# parallel, as they don't need much memory.
SMALL_LEAF_MAX_SIZE = 500 * 1000 * 1000
SMALL_LEAF_WORKERS = 4


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
        self.lines_dir = os.path.join(working_dir, "ccov-lines")
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

        if cache_root is not None:
            assert os.path.isdir(cache_root), f"Cache root {cache_root} is not a dir."
            self.repo_dir = os.path.join(cache_root, self.branch)

        # Load coverage tasks for all platforms
        decision_task_id = taskcluster.get_decision_task(self.branch, self.revision)

        assert decision_task_id is not None, "The decision task couldn't be found"

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

        subprocess.run(cmd, stdin=subprocess.DEVNULL, check=True)

        logger.info("{} cloned".format(self.repository))

    def retrieve_source_and_artifacts(self):
        with ThreadPoolExecutorResult(max_workers=2) as executor:
            futures = []

            # Thread 1 - Download coverage artifacts.
            futures.append(executor.submit(self.artifactsHandler.download_all))

            # Thread 2 - Clone repository.
            futures.append(executor.submit(self.clone_repository))

            for future in concurrent.futures.as_completed(futures):
                exc = future.exception()
                if exc is not None:
                    logger.error(
                        "Exception while downloading coverage artifacts or cloning repository",
                        exception=exc,
                    )
                    from traceback import format_exception

                    logger.error(format_exception(exc, exc, exc.__traceback__))
                    os._exit(1)

    def report_path(self, platform, suite):
        return os.path.join(self.reports_dir, f"{platform}.{suite}.json")

    def build_full_report(self):
        """
        Build only the full covdir report, directly from all the artifacts,
        and return its path.

        This is faster than build_reports when the other reports are not
        needed (e.g. on try), as it doesn't need to build the reports of each
        (platform, suite) combination first.
        """
        os.makedirs(self.reports_dir, exist_ok=True)

        artifacts = self.artifactsHandler.get_combinations()[("all", "all")]
        logger.info(
            "Building covdir suite report",
            suite="all",
            platform="all",
            artifacts=len(artifacts),
        )
        path = self.report_path("all", "all")
        with open(path, "wb") as f:
            f.write(
                grcov.report(artifacts, source_dir=self.repo_dir, out_format="covdir")
            )
        return path

    def build_reports(self):
        """
        Build all the possible covdir reports using current artifacts, yielding
        ((platform, suite), path).

        Each artifact is parsed only once: the reports of each (platform,
        suite) combination (the leaves) are built first from their artifacts,
        along with an LCOV file of their line coverage. All the other reports
        (the full report, a platform for all suites, a suite for all
        platforms) are built from these much smaller LCOV files.

        The full report is yielded first, so it can be used right away, then
        the leaf reports, then the other aggregated reports.
        """
        os.makedirs(self.reports_dir, exist_ok=True)

        combinations = self.artifactsHandler.get_combinations()

        leaves = [key for key in combinations if "all" not in key]

        # Most leaves have little coverage data: building their reports is
        # mostly grcov's fixed cost, and uses at most ~3 GB of memory, so they
        # are built in parallel. The others can use more than 10 GB each, so
        # they are built one at a time, after the small ones.
        size = {
            leaf: sum(os.path.getsize(path) for path in combinations[leaf])
            for leaf in leaves
        }
        small = [leaf for leaf in leaves if size[leaf] <= SMALL_LEAF_MAX_SIZE]
        big = [leaf for leaf in leaves if size[leaf] > SMALL_LEAF_MAX_SIZE]
        leaf_lines = {}
        with ThreadPoolExecutorResult(max_workers=SMALL_LEAF_WORKERS) as executor:
            futures = {
                leaf: executor.submit(self.build_leaf_report, leaf, combinations[leaf])
                for leaf in small
            }
        for leaf in small:
            leaf_lines[leaf] = futures[leaf].result()
        for leaf in big:
            leaf_lines[leaf] = self.build_leaf_report(leaf, combinations[leaf])

        yield ("all", "all"), self.build_aggregated_report("all", "all", leaf_lines)

        for platform, suite in leaves:
            yield (platform, suite), self.report_path(platform, suite)

        for platform, suite in combinations:
            if "all" in (platform, suite) and (platform, suite) != ("all", "all"):
                path = self.build_aggregated_report(platform, suite, leaf_lines)
                yield (platform, suite), path

    def build_leaf_report(self, leaf, artifacts):
        """
        Build the covdir report of a (platform, suite) combination from its
        artifacts, along with an LCOV file of its line coverage, and return
        the path of the LCOV file.
        """
        platform, suite = leaf
        # Identify the leaf in all the logs (e.g. of grcov's duration and
        # memory), as leaves can be built in parallel.
        with structlog.contextvars.bound_contextvars(platform=platform, suite=suite):
            logger.info("Building covdir suite report", artifacts=len(artifacts))
            covdir, lines = grcov.report_with_lines(
                artifacts,
                self.repo_dir,
                os.path.join(self.lines_dir, f"{platform}.{suite}"),
            )
        os.replace(covdir, self.report_path(platform, suite))
        return lines

    def build_aggregated_report(self, platform, suite, leaf_lines):
        """
        Build the covdir report of a combination aggregating several leaves
        (where platform and/or suite is "all"), from the LCOV files of the
        leaves (leaf_lines, mapping each (platform, suite) leaf to its LCOV
        file), and return its path.
        """
        parts = [
            (p, s)
            for p, s in leaf_lines
            if platform in ("all", p) and suite in ("all", s)
        ]
        path = self.report_path(platform, suite)

        if len(parts) == 1:
            # e.g. a suite running on a single platform: the aggregated
            # report is the same as the leaf report.
            shutil.copyfile(self.report_path(*parts[0]), path)
        else:
            logger.info(
                "Building covdir aggregated report",
                suite=suite,
                platform=platform,
                parts=len(parts),
            )
            with open(path, "wb") as f:
                f.write(
                    grcov.report(
                        [leaf_lines[part] for part in parts],
                        source_dir=self.repo_dir,
                        out_format="covdir",
                    )
                )

        return path

    def index_task(self, namespaces):
        """
        Index current task on Taskcluster Index. The index lifetime will be the
        same as the task's.
        """
        task_id = os.environ.get("TASK_ID")
        if task_id is None:
            logger.warning("Skipping Taskcluster indexation, no task id found.")
            return

        task_expires = taskcluster.get_task_details(task_id)["expires"]
        index_service = taskcluster_config.get_service("index")

        for namespace in namespaces:
            index_service.insertTask(
                namespace,
                {
                    "taskId": task_id,
                    "rank": 0,
                    "data": {},
                    "expires": task_expires,
                },
            )

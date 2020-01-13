# -*- coding: utf-8 -*-
import collections
import fnmatch
import itertools
import os
import time

import structlog

from code_coverage_bot import taskcluster
from code_coverage_bot.utils import ThreadPoolExecutorResult

logger = structlog.get_logger(__name__)


Artifact = collections.namedtuple("Artifact", "path, task_id, platform, suite, chunk")


SUITES_TO_IGNORE = [
    "awsy",
    "talos",
]  # Ignore awsy and talos as they aren't actually suites of tests.
FINISHED_STATUSES = ["completed", "failed", "exception"]
ALL_STATUSES = FINISHED_STATUSES + ["unscheduled", "pending", "running"]
STATUS_VALUE = {"exception": 1, "failed": 2, "completed": 3}


class ArtifactsHandler(object):
    def __init__(self, test_tasks, parent_dir="ccov-artifacts", task_name_filter="*"):
        self.test_tasks = test_tasks
        self.parent_dir = parent_dir
        self.task_name_filter = task_name_filter
        self.artifacts = []

    def generate_path(self, platform, chunk, artifact):
        file_name = "%s_%s_%s" % (platform, chunk, os.path.basename(artifact["name"]))
        return os.path.join(self.parent_dir, file_name)

    def get_chunks(self, platform):
        return set(
            artifact.chunk
            for artifact in self.artifacts
            if artifact.platform == platform
        )

    def get_combinations(self):
        # Add the full report
        out = collections.defaultdict(list)
        out[("all", "all")] = [artifact.path for artifact in self.artifacts]

        # Group by suite first
        suites = itertools.groupby(
            sorted(self.artifacts, key=lambda a: a.suite), lambda a: a.suite
        )
        for suite, artifacts in suites:
            artifacts = list(artifacts)

            # List all available platforms
            platforms = {a.platform for a in artifacts}
            platforms.add("all")

            # And list all possible permutations with suite + platform
            out[("all", suite)] += [artifact.path for artifact in artifacts]
            for platform in platforms:
                if platform != "all":
                    out[(platform, "all")] += [
                        artifact.path
                        for artifact in artifacts
                        if artifact.platform == platform
                    ]
                out[(platform, suite)] = [
                    artifact.path
                    for artifact in artifacts
                    if platform == "all" or artifact.platform == platform
                ]

        return out

    def get(self, platform=None, suite=None, chunk=None):
        if suite is not None and chunk is not None:
            raise Exception("suite and chunk can't both have a value")

        # Filter artifacts according to platform, suite and chunk.
        filtered_files = []
        for artifact in self.artifacts:
            if platform is not None and artifact.platform != platform:
                continue

            if suite is not None and artifact.suite != suite:
                continue

            if chunk is not None and artifact.chunk != chunk:
                continue

            filtered_files.append(artifact.path)

        return filtered_files

    def download(self, test_task):
        suite = taskcluster.get_suite(test_task["task"])
        chunk_name = taskcluster.get_chunk(test_task["task"])
        platform_name = taskcluster.get_platform(test_task["task"])
        test_task_id = test_task["status"]["taskId"]

        for artifact in taskcluster.get_task_artifacts(test_task_id):
            if not any(
                n in artifact["name"]
                for n in ["code-coverage-grcov.zip", "code-coverage-jsvm.zip"]
            ):
                continue

            artifact_path = self.generate_path(platform_name, chunk_name, artifact)
            taskcluster.download_artifact(artifact_path, test_task_id, artifact["name"])
            logger.info("%s artifact downloaded" % artifact_path)

            self.artifacts.append(
                Artifact(artifact_path, test_task_id, platform_name, suite, chunk_name)
            )

    def is_filtered_task(self, task):
        """
        Apply name filter from CLI args on task name
        """
        assert isinstance(task, dict)
        name = task["task"]["metadata"]["name"]

        if not fnmatch.fnmatch(name, self.task_name_filter):
            logger.debug("Filtered task", name=name)
            return True

        return False

    def download_all(self):
        os.makedirs(self.parent_dir, exist_ok=True)

        logger.info("Downloading artifacts from {} tasks".format(len(self.test_tasks)))

        for test_task in self.test_tasks:
            status = test_task["status"]["state"]
            task_id = test_task["status"]["taskId"]
            while status not in FINISHED_STATUSES:
                assert status in ALL_STATUSES, "State '{}' not recognized".format(
                    status
                )
                logger.info(f"Waiting for task {task_id} to finish...")
                time.sleep(60)
                task_status = taskcluster.get_task_status(task_id)
                status = task_status["status"]["state"]
                # Update the task status, as we will use it to compare statuses later.
                test_task["status"]["state"] = status

        # Choose best tasks to download (e.g. 'completed' is better than 'failed')
        download_tasks = {}
        for test_task in self.test_tasks:
            status = test_task["status"]["state"]
            assert status in FINISHED_STATUSES, "State '{}' not recognized".format(
                status
            )

            chunk_name = taskcluster.get_chunk(test_task["task"])
            platform_name = taskcluster.get_platform(test_task["task"])

            if any(to_ignore in chunk_name for to_ignore in SUITES_TO_IGNORE):
                continue

            if (chunk_name, platform_name) not in download_tasks:
                # If the chunk hasn't been downloaded before, this is obviously the best task
                # to download it from.
                download_tasks[(chunk_name, platform_name)] = test_task
            else:
                # Otherwise, compare the status of this task with the previously selected task.
                prev_task = download_tasks[(chunk_name, platform_name)]

                if STATUS_VALUE[status] > STATUS_VALUE[prev_task["status"]["state"]]:
                    download_tasks[(chunk_name, platform_name)] = test_task

        with ThreadPoolExecutorResult() as executor:
            for test_task in download_tasks.values():
                executor.submit(self.download, test_task)

        logger.info("Code coverage artifacts downloaded")

# -*- coding: utf-8 -*-
import collections
import concurrent.futures
import fnmatch
import itertools
import os
import time

import structlog

from code_coverage_bot import taskcluster
from code_coverage_bot.utils import ThreadPoolExecutorResult
from code_coverage_bot.utils import is_not_found_error

logger = structlog.get_logger(__name__)


Artifact = collections.namedtuple("Artifact", "path, task_id, platform, suite, chunk")


SUITES_TO_IGNORE = [
    "awsy",
    "talos",
]  # Ignore awsy and talos as they aren't actually suites of tests.
STATUS_VALUE = {"exception": 1, "failed": 2, "completed": 3}
COVERAGE_ARTIFACTS = ["code-coverage-grcov.zip", "code-coverage-jsvm.zip"]

# Number of threads downloading artifacts in parallel.
DOWNLOAD_WORKERS = 8

MB = 1_000_000


class ArtifactsHandler(object):
    def __init__(self, test_tasks, parent_dir="ccov-artifacts", task_name_filter="*"):
        self.test_tasks = test_tasks
        self.parent_dir = parent_dir
        self.task_name_filter = task_name_filter
        self.artifacts = []
        # (size in bytes, duration in seconds) of each artifact downloaded by
        # download_all, not counting the ones which were already on disk.
        self.download_stats = []
        # Coverage artifact names for each task kind.
        self.artifact_names = {}

    def generate_path(self, platform, chunk, artifact_name):
        file_name = "%s_%s_%s" % (platform, chunk, os.path.basename(artifact_name))
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

    def find_artifact_names(self, test_tasks):
        """
        Learn the coverage artifact names of each task kind, assuming all tasks
        of the same kind use the same names, so we don't need to list the
        artifacts of every task.
        """
        tasks_by_kind = collections.defaultdict(list)
        for test_task in test_tasks:
            kind = taskcluster.get_task_kind(test_task["task"])
            if kind not in self.artifact_names:
                tasks_by_kind[kind].append(test_task)

        for kind, tasks in tasks_by_kind.items():
            # Some tasks might not have any coverage artifact (e.g. if they failed
            # early), so look for the first one that has them.
            names = []
            for test_task in tasks:
                names = [
                    artifact["name"]
                    for artifact in taskcluster.get_task_artifacts(
                        test_task["status"]["taskId"]
                    )
                    if any(n in artifact["name"] for n in COVERAGE_ARTIFACTS)
                ]
                if names:
                    break

            logger.info("Coverage artifact names for task kind", kind=kind, names=names)
            self.artifact_names[kind] = names

    def download(self, test_task):
        suite = taskcluster.get_suite(test_task["task"])
        chunk_name = taskcluster.get_chunk(test_task["task"])
        platform_name = taskcluster.get_platform(test_task["task"])
        test_task_id = test_task["status"]["taskId"]

        kind = taskcluster.get_task_kind(test_task["task"])
        if kind not in self.artifact_names:
            self.find_artifact_names([test_task])

        for artifact_name in self.artifact_names[kind]:
            artifact_path = self.generate_path(platform_name, chunk_name, artifact_name)
            cached = os.path.exists(artifact_path)
            start = time.monotonic()
            try:
                taskcluster.download_artifact(
                    artifact_path, test_task_id, artifact_name
                )
            except Exception as e:
                if not is_not_found_error(e):
                    raise
                logger.info(
                    "Artifact not found", task_id=test_task_id, artifact=artifact_name
                )
                continue
            duration = time.monotonic() - start
            size = os.path.getsize(artifact_path)
            if not cached:
                self.download_stats.append((size, duration))
            logger.info(
                "Artifact downloaded",
                path=artifact_path,
                size_mb=round(size / MB, 1),
                duration=round(duration, 2),
                mb_per_s=round(size / MB / duration, 1) if duration > 0 else None,
                cached=cached,
            )

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

    def download_all(self) -> None:
        os.makedirs(self.parent_dir, exist_ok=True)

        logger.info("Downloading artifacts from {} tasks".format(len(self.test_tasks)))

        for test_task in self.test_tasks:
            status = test_task["status"]["state"]
            task_id = test_task["status"]["taskId"]
            if status in taskcluster.FINISHED_STATUSES:
                continue
            while True:
                # refresh the status information
                task_status = taskcluster.get_task_status(task_id)
                status = task_status["status"]["state"]
                assert (
                    status in taskcluster.ALL_STATUSES
                ), "State '{}' not recognized".format(status)
                if status in taskcluster.FINISHED_STATUSES:
                    # Update the task status, as we will use it to compare statuses later.
                    test_task["status"]["state"] = status
                    break
                logger.info(f"Waiting for task {task_id} to finish...")
                time.sleep(60)

        # Choose best tasks to download (e.g. 'completed' is better than 'failed')
        download_tasks = {}
        for test_task in self.test_tasks:
            status = test_task["status"]["state"]
            assert (
                status in taskcluster.FINISHED_STATUSES
            ), "State '{}' not recognized".format(status)

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

        self.find_artifact_names(download_tasks.values())

        logger.info(
            "Downloading artifacts", tasks=len(download_tasks), workers=DOWNLOAD_WORKERS
        )
        self.download_stats = []
        start = time.monotonic()
        with ThreadPoolExecutorResult(max_workers=DOWNLOAD_WORKERS) as executor:
            futures = [
                executor.submit(self.download, test_task)
                for test_task in download_tasks.values()
            ]
            for future in concurrent.futures.as_completed(futures):
                exc = future.exception()
                if exc is not None:
                    logger.error("Exception while downloading artifacts", exception=exc)
                    for f in futures:
                        f.cancel()

        duration = time.monotonic() - start

        total_size = sum(size for size, _ in self.download_stats)
        total_download_duration = sum(d for _, d in self.download_stats)
        logger.info(
            "Code coverage artifacts downloaded",
            artifacts=len(self.download_stats),
            size_mb=round(total_size / MB, 1),
            duration=round(duration, 1),
            mb_per_s=round(total_size / MB / duration, 1) if duration > 0 else None,
            workers=DOWNLOAD_WORKERS,
            # Average number of artifacts being downloaded at the same time.
            concurrency=(
                round(total_download_duration / duration, 1) if duration > 0 else None
            ),
        )

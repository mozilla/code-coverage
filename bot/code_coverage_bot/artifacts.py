# -*- coding: utf-8 -*-
import fnmatch
import os
import time

import structlog

from code_coverage_bot import taskcluster
from code_coverage_bot.utils import ThreadPoolExecutorResult

logger = structlog.get_logger(__name__)


SUITES_TO_IGNORE = [
    "awsy",
    "talos",
]  # Ignore awsy and talos as they aren't actually suites of tests.
FINISHED_STATUSES = ["completed", "failed", "exception"]
ALL_STATUSES = FINISHED_STATUSES + ["unscheduled", "pending", "running"]
STATUS_VALUE = {"exception": 1, "failed": 2, "completed": 3}


class ArtifactsHandler(object):
    def __init__(self, task_ids, parent_dir="ccov-artifacts", task_name_filter="*"):
        self.task_ids = task_ids
        self.parent_dir = parent_dir
        self.task_name_filter = task_name_filter

    def generate_path(self, platform, chunk, artifact):
        file_name = "%s_%s_%s" % (platform, chunk, os.path.basename(artifact["name"]))
        return os.path.join(self.parent_dir, file_name)

    def get_chunks(self, platform):
        return set(
            f.split("_")[1]
            for f in os.listdir(self.parent_dir)
            if os.path.basename(f).startswith(f"{platform}_")
        )

    def get(self, platform=None, suite=None, chunk=None):
        files = os.listdir(self.parent_dir)

        if suite is not None and chunk is not None:
            raise Exception("suite and chunk can't both have a value")

        # Filter artifacts according to platform, suite and chunk.
        filtered_files = []
        for fname in files:
            if platform is not None and not fname.startswith("%s_" % platform):
                continue

            if suite is not None and suite not in fname:
                continue

            if chunk is not None and ("%s_code-coverage" % chunk) not in fname:
                continue

            filtered_files.append(os.path.join(self.parent_dir, fname))

        return filtered_files

    def download(self, test_task):
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

        # The test tasks for the Linux and Windows builds are in the same group,
        # but the following code is generic and supports build tasks split in
        # separate groups.
        groups = set(
            [
                taskcluster.get_task_details(build_task_id)["taskGroupId"]
                for build_task_id in self.task_ids.values()
            ]
        )
        test_tasks = [
            task
            for group in groups
            for task in taskcluster.get_tasks_in_group(group)
            if taskcluster.is_coverage_task(task["task"])
            and not self.is_filtered_task(task)
        ]
        logger.info("Downloading artifacts from {} tasks".format(len(test_tasks)))

        for test_task in test_tasks:
            status = test_task["status"]["state"]
            while status not in FINISHED_STATUSES:
                assert status in ALL_STATUSES, "State '{}' not recognized".format(
                    status
                )
                logger.info(
                    "Waiting for task {} to finish...".format(
                        test_task["status"]["taskId"]
                    )
                )
                time.sleep(60)
                status = taskcluster.get_task_status(test_task["status"]["taskId"])

        # Choose best tasks to download (e.g. 'completed' is better than 'failed')
        download_tasks = {}
        for test_task in test_tasks:
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

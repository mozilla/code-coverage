# -*- coding: utf-8 -*-
import os
import shutil
from zipfile import BadZipFile
from zipfile import is_zipfile

import requests
import structlog
import taskcluster
from taskcluster.helper import TaskclusterConfig

from code_coverage_bot.utils import retry

logger = structlog.getLogger(__name__)
taskcluster_config = TaskclusterConfig("https://firefox-ci-tc.services.mozilla.com")

NAME_PARTS_TO_SKIP = ("opt", "debug", "e10s", "1proc")


def get_decision_task(branch, revision):
    route = f"gecko.v2.{branch}.revision.{revision}.firefox.decision"
    index = taskcluster_config.get_service("index")
    try:
        return index.findTask(route)["taskId"]
    except taskcluster.exceptions.TaskclusterRestFailure as e:
        if e.status_code == 404:
            return None
        raise


def get_task_details(task_id):
    queue = taskcluster_config.get_service("queue")
    return queue.task(task_id)


def get_task_status(task_id):
    queue = taskcluster_config.get_service("queue")
    return queue.status(task_id)


def get_task_artifacts(task_id):
    queue = taskcluster_config.get_service("queue")
    return queue.listLatestArtifacts(task_id)["artifacts"]


def get_tasks_in_group(group_id):
    queue = taskcluster_config.get_service("queue")

    token = None
    while True:
        query = {"limit": 200}
        if token is not None:
            query["continuationToken"] = token

        response = queue.listTaskGroup(group_id, query=query)

        yield from response["tasks"]

        token = response.get("continuationToken")
        if token is None:
            break


def download_artifact(artifact_path, task_id, artifact_name):
    if os.path.exists(artifact_path):
        return artifact_path

    # Build artifact public url
    # Use un-authenticated Taskcluster client to avoid taskcluster-proxy rewrite issue
    # https://github.com/taskcluster/taskcluster-proxy/issues/44
    queue = taskcluster.Queue({"rootUrl": "https://firefox-ci-tc.services.mozilla.com"})
    url = queue.buildUrl("getLatestArtifact", task_id, artifact_name)
    logger.debug("Downloading artifact", url=url)

    def perform_download():
        r = requests.get(url, stream=True)
        r.raise_for_status()

        with open(artifact_path, "wb") as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

        if artifact_path.endswith(".zip") and not is_zipfile(artifact_path):
            raise BadZipFile("File is not a zip file")

    retry(perform_download)


def is_coverage_task(task):
    return "ccov" in task["metadata"]["name"].split("/")[0].split("-")


def name_to_chunk(name: str):
    """
    Helper to convert a task name to a chunk
    Used by chunk mapping
    """
    # Some tests are run on build machines, we define placeholder chunks for those.
    if name.startswith("build-signing-"):
        return "build-signing"
    elif name.startswith("build-"):
        return "build"

    name = name.split("/")[1]

    return "-".join(p for p in name.split("-") if p not in NAME_PARTS_TO_SKIP)


def chunk_to_suite(chunk: str):
    """
    Helper to convert a chunk to a suite (no numbers)
    Used by chunk mapping
    """
    return "-".join(p for p in chunk.split("-") if not p.isdigit())


def get_chunk(task):
    """
    Build clean chunk name from a Taskcluster task
    """
    suite = get_suite(task)
    chunks = task["extra"].get("chunks", {})
    if "current" in chunks:
        return f'{suite}-{chunks["current"]}'
    return suite


def get_suite(task):
    """
    Build clean suite name from a Taskcluster task
    """
    assert isinstance(task, dict)
    tags = task["tags"]
    extra = task["extra"]

    if tags.get("kind") == "build":
        return "build"
    elif tags.get("kind") == "build-signing":
        return "build-signing"
    elif "suite" in extra:
        if isinstance(extra["suite"], dict):
            return extra["suite"]["name"]
        return extra["suite"]
    else:
        return tags.get("test-type")

    raise Exception(f"Unknown chunk for {task}")


def get_platform(task):
    """
    Build clean platform from a Taskcluster task
    """
    assert isinstance(task, dict)
    tags = task.get("tags", {})
    platform = tags.get("os")

    # Fallback on parsing the task name for signing tasks, as they don't have "os" in their tags.
    name = task.get("metadata", {}).get("name", "")
    if not platform and "signing" in name:
        name = name.split("/")[0]
        if "linux" in name:
            platform = "linux"
        if "win" in name:
            assert platform is None
            platform = "windows"
        if "mac" in name:
            assert platform is None
            platform = "mac"

    if not platform:
        raise Exception(f"Unknown platform for {task}")

    # Weird case for android build on Linux docker
    if platform == "linux" and tags.get("android-stuff"):
        return "android"

    return platform

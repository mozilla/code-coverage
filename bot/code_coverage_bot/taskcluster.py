# -*- coding: utf-8 -*-
import os
import shutil
from zipfile import BadZipFile
from zipfile import is_zipfile

import requests

from code_coverage_bot.utils import retry
from code_coverage_tools.taskcluster import TaskclusterConfig

taskcluster_config = TaskclusterConfig()

index_base = "https://index.taskcluster.net/v1/"
queue_base = "https://queue.taskcluster.net/v1/"


class TaskclusterException(Exception):
    pass


def get_task(branch, revision, platform):
    if platform == "linux":
        platform_name = "linux64-ccov-debug"
        product = "firefox"
    elif platform == "windows":
        platform_name = "win64-ccov-debug"
        product = "firefox"
    elif platform == "android-test":
        platform_name = "android-test-ccov"
        product = "mobile"
    elif platform == "android-emulator":
        platform_name = "android-api-16-ccov-debug"
        product = "mobile"
    else:
        raise TaskclusterException("Unsupported platform: %s" % platform)

    r = requests.get(
        index_base
        + "task/gecko.v2.{}.revision.{}.{}.{}".format(
            branch, revision, product, platform_name
        )
    )
    task = r.json()
    if r.status_code == requests.codes.ok:
        return task["taskId"]
    else:
        if task["code"] == "ResourceNotFound":
            return None
        else:
            raise TaskclusterException("Unknown TaskCluster index error.")


def get_task_details(task_id):
    r = requests.get(queue_base + "task/{}".format(task_id))
    r.raise_for_status()
    return r.json()


def get_task_status(task_id):
    r = requests.get(queue_base + "task/{}/status".format(task_id))
    r.raise_for_status()
    return r.json()


def get_task_artifacts(task_id):
    r = requests.get(queue_base + "task/{}/artifacts".format(task_id))
    r.raise_for_status()
    return r.json()["artifacts"]


def get_tasks_in_group(group_id):
    list_url = queue_base + "task-group/{}/list".format(group_id)

    r = requests.get(list_url, params={"limit": 200})
    r.raise_for_status()
    reply = r.json()
    tasks = reply["tasks"]
    while "continuationToken" in reply:
        r = requests.get(
            list_url,
            params={"limit": 200, "continuationToken": reply["continuationToken"]},
        )
        r.raise_for_status()
        reply = r.json()
        tasks += reply["tasks"]
    return tasks


def download_artifact(artifact_path, task_id, artifact_name):
    if os.path.exists(artifact_path):
        return artifact_path

    def perform_download():
        r = requests.get(
            queue_base + "task/{}/artifacts/{}".format(task_id, artifact_name),
            stream=True,
        )

        r.raise_for_status()

        with open(artifact_path, "wb") as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

        if artifact_path.endswith(".zip") and not is_zipfile(artifact_path):
            raise BadZipFile("File is not a zip file")

    retry(perform_download)


BUILD_PLATFORMS = [
    "build-linux64-ccov/debug",
    "build-win64-ccov/debug",
    "build-android-test-ccov/opt",
]

TEST_PLATFORMS = [
    "test-linux64-ccov/debug",
    "test-windows10-64-ccov/debug",
    "test-android-em-4.3-arm7-api-16-ccov/debug",
] + BUILD_PLATFORMS


def is_coverage_task(task):
    return any(task["metadata"]["name"].startswith(t) for t in TEST_PLATFORMS)


def name_to_chunk(name):
    """
    Helper to convert a task name to a chunk
    Used by chunk mapping
    """
    assert isinstance(name, str)

    # Some tests are run on build machines, we define a placeholder chunk for those.
    if name in BUILD_PLATFORMS:
        return "build"

    for t in TEST_PLATFORMS:
        if name.startswith(t):
            name = name[len(t) + 1 :]
            break
    return "-".join([p for p in name.split("-") if p != "e10s"])


def chunk_to_suite(chunk):
    """
    Helper to convert a chunk to a suite (no numbers)
    Used by chunk mapping
    """
    assert isinstance(chunk, str)
    return "-".join([p for p in chunk.split("-") if not p.isdigit()])


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
    treeherder = extra.get("treeherder", {})

    if treeherder.get("jobKind") == "build":
        return "build"
    elif "suite" in extra:
        if isinstance(extra["suite"], dict):
            return extra["suite"]["name"]
        return extra["suite"]
    else:
        return tags.get("test-type")

    raise Exception("Unknown chunk")


def get_platform(task):
    """
    Build clean platform from a Taskcluster task
    """
    assert isinstance(task, dict)
    assert isinstance(task, dict)
    tags = task.get("tags", {})
    platform = tags.get("os")
    if not platform:
        raise Exception("Unknown platform")

    # Weird case for android build on Linux docker
    if platform == "linux" and tags.get("android-stuff"):
        return "android"

    return platform

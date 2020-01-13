# -*- coding: utf-8 -*-
import hashlib
import itertools
import os
from unittest import mock

import pytest
import responses

from code_coverage_bot.artifacts import Artifact
from code_coverage_bot.artifacts import ArtifactsHandler
from code_coverage_bot.hooks.base import Hook

FILES = [
    "windows_mochitest-1_code-coverage-jsvm.info",
    "linux_mochitest-2_code-coverage-grcov.zip",
    "windows_xpcshell-7_code-coverage-jsvm.info",
    "linux_xpcshell-7_code-coverage-grcov.zip",
    "linux_xpcshell-3_code-coverage-grcov.zip",
    "windows_cppunit_code-coverage-grcov.zip",
    "linux_firefox-ui-functional-remote_code-coverage-jsvm.info",
]


@pytest.fixture
def fake_artifacts(tmpdir):
    def name_to_artifact(name):
        """
        Touch the fake artifact & build instance
        """
        path = os.path.join(tmpdir.strpath, name)
        open(path, "w")

        platform, chunk, _ = name.split("_")
        return Artifact(
            path,
            hashlib.md5(name.encode("utf-8")).hexdigest()[:10],
            platform,
            chunk[: chunk.rindex("-")] if "-" in chunk else chunk,
            chunk,
        )

    return [name_to_artifact(f) for f in FILES]


def test_generate_path(fake_artifacts):
    a = ArtifactsHandler([])
    artifact_jsvm = {"name": "code-coverage-jsvm.info"}
    artifact_grcov = {"name": "code-coverage-grcov.zip"}
    assert os.path.join(
        a.parent_dir, "linux_xpcshell-3_code-coverage-jsvm.info"
    ) == a.generate_path("linux", "xpcshell-3", artifact_jsvm)
    assert os.path.join(
        a.parent_dir, "windows_cppunit_code-coverage-grcov.zip"
    ) == a.generate_path("windows", "cppunit", artifact_grcov)


def test_get_chunks(fake_artifacts):
    a = ArtifactsHandler([])
    a.artifacts = fake_artifacts
    assert a.get_chunks("windows") == {"mochitest-1", "xpcshell-7", "cppunit"}
    assert a.get_chunks("linux") == {
        "mochitest-2",
        "xpcshell-3",
        "xpcshell-7",
        "firefox-ui-functional-remote",
    }


def test_get_combinations(tmpdir, fake_artifacts):
    def add_dir(files):
        return [os.path.join(tmpdir.strpath, f) for f in files]

    a = ArtifactsHandler([])
    a.artifacts = fake_artifacts
    assert dict(a.get_combinations()) == {
        ("all", "all"): add_dir(
            [
                "windows_mochitest-1_code-coverage-jsvm.info",
                "linux_mochitest-2_code-coverage-grcov.zip",
                "windows_xpcshell-7_code-coverage-jsvm.info",
                "linux_xpcshell-7_code-coverage-grcov.zip",
                "linux_xpcshell-3_code-coverage-grcov.zip",
                "windows_cppunit_code-coverage-grcov.zip",
                "linux_firefox-ui-functional-remote_code-coverage-jsvm.info",
            ]
        ),
        ("linux", "all"): add_dir(
            [
                "linux_firefox-ui-functional-remote_code-coverage-jsvm.info",
                "linux_mochitest-2_code-coverage-grcov.zip",
                "linux_xpcshell-7_code-coverage-grcov.zip",
                "linux_xpcshell-3_code-coverage-grcov.zip",
            ]
        ),
        ("windows", "all"): add_dir(
            [
                "windows_cppunit_code-coverage-grcov.zip",
                "windows_mochitest-1_code-coverage-jsvm.info",
                "windows_xpcshell-7_code-coverage-jsvm.info",
            ]
        ),
        ("all", "cppunit"): add_dir(["windows_cppunit_code-coverage-grcov.zip"]),
        ("windows", "cppunit"): add_dir(["windows_cppunit_code-coverage-grcov.zip"]),
        ("all", "firefox-ui-functional"): add_dir(
            ["linux_firefox-ui-functional-remote_code-coverage-jsvm.info"]
        ),
        ("linux", "firefox-ui-functional"): add_dir(
            ["linux_firefox-ui-functional-remote_code-coverage-jsvm.info"]
        ),
        ("all", "mochitest"): add_dir(
            [
                "windows_mochitest-1_code-coverage-jsvm.info",
                "linux_mochitest-2_code-coverage-grcov.zip",
            ]
        ),
        ("linux", "mochitest"): add_dir(["linux_mochitest-2_code-coverage-grcov.zip"]),
        ("windows", "mochitest"): add_dir(
            ["windows_mochitest-1_code-coverage-jsvm.info"]
        ),
        ("all", "xpcshell"): add_dir(
            [
                "windows_xpcshell-7_code-coverage-jsvm.info",
                "linux_xpcshell-7_code-coverage-grcov.zip",
                "linux_xpcshell-3_code-coverage-grcov.zip",
            ]
        ),
        ("linux", "xpcshell"): add_dir(
            [
                "linux_xpcshell-7_code-coverage-grcov.zip",
                "linux_xpcshell-3_code-coverage-grcov.zip",
            ]
        ),
        ("windows", "xpcshell"): add_dir(
            ["windows_xpcshell-7_code-coverage-jsvm.info"]
        ),
    }


def test_get_coverage_artifacts(tmpdir, fake_artifacts):
    def add_dir(files):
        return set([os.path.join(tmpdir.strpath, f) for f in files])

    a = ArtifactsHandler([])
    a.artifacts = fake_artifacts
    assert set(a.get()) == add_dir(FILES)
    assert set(a.get(suite="mochitest")) == add_dir(
        [
            "windows_mochitest-1_code-coverage-jsvm.info",
            "linux_mochitest-2_code-coverage-grcov.zip",
        ]
    )
    assert set(a.get(chunk="xpcshell-7")) == add_dir(
        [
            "windows_xpcshell-7_code-coverage-jsvm.info",
            "linux_xpcshell-7_code-coverage-grcov.zip",
        ]
    )
    assert set(a.get(chunk="cppunit")) == add_dir(
        ["windows_cppunit_code-coverage-grcov.zip"]
    )
    assert set(a.get(platform="windows")) == add_dir(
        [
            "windows_mochitest-1_code-coverage-jsvm.info",
            "windows_xpcshell-7_code-coverage-jsvm.info",
            "windows_cppunit_code-coverage-grcov.zip",
        ]
    )
    assert set(a.get(platform="linux", chunk="xpcshell-7")) == add_dir(
        ["linux_xpcshell-7_code-coverage-grcov.zip"]
    )

    with pytest.raises(Exception, match="suite and chunk can't both have a value"):
        a.get(chunk="xpcshell-7", suite="mochitest")


@mock.patch("code_coverage_bot.taskcluster.get_task_artifacts")
@mock.patch("code_coverage_bot.taskcluster.download_artifact")
def test_download(
    mocked_download_artifact,
    mocked_get_task_artifact,
    TEST_TASK_FROM_GROUP,
    LINUX_TEST_TASK_ARTIFACTS,
):
    a = ArtifactsHandler([])
    mocked_get_task_artifact.return_value = LINUX_TEST_TASK_ARTIFACTS["artifacts"]

    a.download(TEST_TASK_FROM_GROUP)

    assert mocked_get_task_artifact.call_count == 1
    assert mocked_download_artifact.call_count == 2
    assert mocked_download_artifact.call_args_list[0] == mock.call(
        "ccov-artifacts/linux_mochitest-devtools-chrome-4_code-coverage-grcov.zip",
        "AN1M9SW0QY6DZT6suL3zlQ",
        "public/test_info/code-coverage-grcov.zip",
    )
    assert mocked_download_artifact.call_args_list[1] == mock.call(
        "ccov-artifacts/linux_mochitest-devtools-chrome-4_code-coverage-jsvm.zip",
        "AN1M9SW0QY6DZT6suL3zlQ",
        "public/test_info/code-coverage-jsvm.zip",
    )


# In the download_all tests, we want to make sure the relative ordering of the tasks
# in the Taskcluster group does not affect the result, so we test with all possible
# orderings of several possible states.
def _group_tasks():
    task_state_groups = [
        [
            ("test-linux64-ccov/opt-mochitest-devtools-chrome-e10s-4", "exception"),
            ("test-linux64-ccov/opt-mochitest-devtools-chrome-e10s-4", "failed"),
            ("test-linux64-ccov/opt-mochitest-devtools-chrome-e10s-4", "completed"),
        ],
        [
            ("test-windows10-64-ccov/debug-xpcshell-4", "exception"),
            ("test-windows10-64-ccov/debug-xpcshell-4", "failed"),
        ],
        [
            ("test-windows10-64-ccov/debug-talos-dromaeojs-e10s", "failed"),
            ("test-windows10-64-ccov/debug-talos-dromaeojs-e10s", "completed"),
        ],
        [
            ("test-linux64-ccov/opt-cppunit", "exception"),
            ("test-linux64-ccov/opt-cppunit", "completed"),
        ],
        [("test-linux64-stylo-disabled/debug-crashtest-e10s", "completed")],
    ]

    # Transform a task_name and state into an object like the ones returned by Taskcluster.
    def build_task(task_state):
        task_name = task_state[0]
        state = task_state[1]
        platform, test = task_name.split("/")
        suite = test.rstrip("debug-")
        platform = platform.lstrip("test-").rstrip("-ccov")
        return {
            "status": {"taskId": task_name + "-" + state, "state": state},
            "task": {
                "metadata": {"name": task_name},
                "env": {},
                "extra": {"suite": suite},
                "tags": {"os": platform},
            },
        }

    # Generate all possible permutations of task_name - state.
    task_state_groups_permutations = [
        list(itertools.permutations(task_state_group))
        for task_state_group in task_state_groups
    ]

    # Generate the product of all possible permutations.
    for ordering in itertools.product(*task_state_groups_permutations):
        yield {
            "taskGroupId": "aPt9FbIdQwmhwDIPDYLuaw",
            "tasks": [
                build_task(task_state) for sublist in ordering for task_state in sublist
            ],
        }


def test_download_all(
    DECISION_TASK_ID,
    DECISION_TASK,
    LATEST_DECISION,
    GROUP_TASKS_1,
    GROUP_TASKS_2,
    fake_artifacts,
    mock_taskcluster,
    tmpdir,
):
    responses.add(
        responses.GET,
        "http://taskcluster.test/api/index/v1/task/gecko.v2.mozilla-central.revision.7828a10a94b6afb78d18d9b7b83e7aa79337cc24.firefox.decision",
        json=LATEST_DECISION,
        status=200,
    )
    responses.add(
        responses.GET,
        f"http://taskcluster.test/api/queue/v1/task/{DECISION_TASK_ID}",
        json=DECISION_TASK,
        status=200,
    )
    for group_tasks in _group_tasks():
        responses.add(
            responses.GET,
            "http://taskcluster.test/api/queue/v1/task-group/OuvSoOjkSvKYLbaGMknMfA/list",
            json=group_tasks,
            status=200,
        )

        h = Hook(
            "https://hg.mozilla.org/mozilla-central",
            "7828a10a94b6afb78d18d9b7b83e7aa79337cc24",
            "*",
            tmpdir,
            tmpdir,
        )
        a = h.artifactsHandler

        # a = ArtifactsHandler({"linux": LINUX_TASK_ID})

        downloaded = set()

        def mock_download(task):
            downloaded.add(task["status"]["taskId"])

        a.download = mock_download

        a.download_all()

        assert downloaded == set(
            [
                "test-linux64-ccov/opt-mochitest-devtools-chrome-e10s-4-completed",
                "test-windows10-64-ccov/debug-xpcshell-4-failed",
                "test-linux64-ccov/opt-cppunit-completed",
            ]
        )

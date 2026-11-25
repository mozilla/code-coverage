# -*- coding: utf-8 -*-
import hashlib
import io
import itertools
import os
import urllib.parse
import zipfile
from unittest import mock

import pytest
import requests
import responses
import structlog

from code_coverage_bot import artifacts
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
    artifact_jsvm = "code-coverage-jsvm.info"
    artifact_grcov = "code-coverage-grcov.zip"
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


def fake_download_artifact(artifact_path, task_id, artifact_name):
    with open(artifact_path, "wb") as f:
        f.write(b"x" * 1_500_000)


@mock.patch("code_coverage_bot.taskcluster.get_task_artifacts")
@mock.patch(
    "code_coverage_bot.taskcluster.download_artifact",
    side_effect=fake_download_artifact,
)
def test_download(
    mocked_download_artifact,
    mocked_get_task_artifact,
    TEST_TASK_FROM_GROUP,
    LINUX_TEST_TASK_ARTIFACTS,
    tmpdir,
    monkeypatch,
):
    monkeypatch.chdir(tmpdir)
    a = ArtifactsHandler([])
    os.makedirs(a.parent_dir)
    mocked_get_task_artifact.return_value = LINUX_TEST_TASK_ARTIFACTS["artifacts"]

    with structlog.testing.capture_logs() as logs:
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

    downloaded_logs = [log for log in logs if log["event"] == "Artifact downloaded"]
    assert [log["path"] for log in downloaded_logs] == [
        "ccov-artifacts/linux_mochitest-devtools-chrome-4_code-coverage-grcov.zip",
        "ccov-artifacts/linux_mochitest-devtools-chrome-4_code-coverage-jsvm.zip",
    ]
    for log in downloaded_logs:
        assert log["size_mb"] == 1.5
        assert log["cached"] is False
        assert log["duration"] >= 0
        assert "mb_per_s" in log
    assert [size for size, _ in a.download_stats] == [1_500_000, 1_500_000]


@mock.patch("code_coverage_bot.taskcluster.get_task_artifacts")
@mock.patch("code_coverage_bot.taskcluster.download_artifact")
def test_download_cached(
    mocked_download_artifact,
    mocked_get_task_artifact,
    TEST_TASK_FROM_GROUP,
    LINUX_TEST_TASK_ARTIFACTS,
    tmpdir,
):
    a = ArtifactsHandler([], parent_dir=tmpdir.strpath)
    mocked_get_task_artifact.return_value = LINUX_TEST_TASK_ARTIFACTS["artifacts"]
    # The artifacts are already on disk, so download_artifact skips them.
    for name in ["code-coverage-grcov.zip", "code-coverage-jsvm.zip"]:
        tmpdir.join(f"linux_mochitest-devtools-chrome-4_{name}").write("x" * 10)

    with structlog.testing.capture_logs() as logs:
        a.download(TEST_TASK_FROM_GROUP)

    downloaded_logs = [log for log in logs if log["event"] == "Artifact downloaded"]
    assert len(downloaded_logs) == 2
    assert all(log["cached"] is True for log in downloaded_logs)
    # Artifacts which were already on disk are not counted in the measurements.
    assert a.download_stats == []
    assert len(a.artifacts) == 2


def _completed_task(task_name):
    platform, test = task_name.split("/")
    return {
        "status": {"taskId": task_name, "state": "completed"},
        "task": {
            "metadata": {"name": task_name},
            "env": {},
            "extra": {"suite": test},
            "tags": {"os": platform},
        },
    }


@mock.patch("code_coverage_bot.taskcluster.get_task_artifacts")
@mock.patch(
    "code_coverage_bot.taskcluster.download_artifact",
    side_effect=fake_download_artifact,
)
def test_download_all_summary(
    mocked_download_artifact, mocked_get_task_artifact, tmpdir, monkeypatch
):
    assert artifacts.DOWNLOAD_WORKERS == 16
    # Use a different value to check it is the one used by download_all.
    expected_workers = 3
    monkeypatch.setattr(artifacts, "DOWNLOAD_WORKERS", expected_workers)

    mocked_get_task_artifact.return_value = [
        {"name": "public/test_info/code-coverage-grcov.zip"},
        {"name": "public/test_info/code-coverage-jsvm.zip"},
        {"name": "public/test_info/other.log"},
    ]
    a = ArtifactsHandler(
        [_completed_task("linux/mochitest"), _completed_task("windows/xpcshell")],
        parent_dir=tmpdir.strpath,
    )

    with mock.patch(
        "code_coverage_bot.artifacts.ThreadPoolExecutorResult",
        wraps=artifacts.ThreadPoolExecutorResult,
    ) as executor:
        with structlog.testing.capture_logs() as logs:
            a.download_all()

    executor.assert_called_once_with(max_workers=expected_workers)

    assert mocked_download_artifact.call_count == 4
    assert len(a.artifacts) == 4

    start_log = next(log for log in logs if log["event"] == "Downloading artifacts")
    assert start_log["tasks"] == 2
    assert start_log["workers"] == expected_workers

    summary = next(
        log for log in logs if log["event"] == "Code coverage artifacts downloaded"
    )
    assert summary["artifacts"] == 4
    assert summary["size_mb"] == 6.0
    assert summary["workers"] == expected_workers
    assert summary["duration"] >= 0
    assert "mb_per_s" in summary
    assert "concurrency" in summary


LISTING_URL = "http://taskcluster.test/api/queue/v1/task/{}/artifacts"
DOWNLOAD_URL = (
    "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/{}/artifacts/{}"
)
TEST_ARTIFACTS = [
    "public/test_info/code-coverage-grcov.zip",
    "public/test_info/code-coverage-jsvm.zip",
]
BUILD_ARTIFACTS = ["public/code-coverage-grcov.zip"]


def _zip_content():
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as z:
        z.writestr("file.info", "")
    return content.getvalue()


def _make_task(task_id, kind, suite, chunk=None):
    task = {
        "status": {"taskId": task_id, "state": "completed"},
        "task": {
            "metadata": {"name": f"{kind}-linux64-ccov/opt-{suite}"},
            "tags": {"kind": kind, "os": "linux"},
            "extra": {"suite": suite},
        },
    }
    if chunk is not None:
        task["task"]["extra"]["chunks"] = {"current": chunk}
    return task


def _add_listing(task_id, artifact_names):
    responses.add(
        responses.GET,
        LISTING_URL.format(task_id),
        json={
            "artifacts": [{"name": "public/logs/live.log"}]
            + [{"name": name} for name in artifact_names]
        },
        status=200,
    )


def _add_download(task_id, artifact_name, status=200):
    responses.add(
        responses.GET,
        DOWNLOAD_URL.format(task_id, urllib.parse.quote(artifact_name, safe="")),
        body=_zip_content() if status == 200 else "error",
        status=status,
    )


def _count_calls(url):
    return sum(1 for call in responses.calls if call.request.url == url)


def test_download_requests(
    mock_taskcluster,
    mock_tenacity,
    tmpdir,
    TEST_TASK_FROM_GROUP,
    LINUX_TEST_TASK_ARTIFACTS,
):
    a = ArtifactsHandler([], parent_dir=tmpdir.strpath)
    task_id = "AN1M9SW0QY6DZT6suL3zlQ"
    responses.add(
        responses.GET,
        LISTING_URL.format(task_id),
        json=LINUX_TEST_TASK_ARTIFACTS,
        status=200,
    )
    for name in TEST_ARTIFACTS:
        _add_download(task_id, name)

    a.find_artifact_names([TEST_TASK_FROM_GROUP])
    a.download(TEST_TASK_FROM_GROUP)

    assert a.artifact_names == {"test": TEST_ARTIFACTS}
    assert a.artifacts == [
        Artifact(
            os.path.join(
                tmpdir.strpath,
                "linux_mochitest-devtools-chrome-4_code-coverage-grcov.zip",
            ),
            task_id,
            "linux",
            "mochitest-devtools-chrome",
            "mochitest-devtools-chrome-4",
        ),
        Artifact(
            os.path.join(
                tmpdir.strpath,
                "linux_mochitest-devtools-chrome-4_code-coverage-jsvm.zip",
            ),
            task_id,
            "linux",
            "mochitest-devtools-chrome",
            "mochitest-devtools-chrome-4",
        ),
    ]
    assert all(os.path.exists(artifact.path) for artifact in a.artifacts)
    # One listing call and two downloads.
    assert len(responses.calls) == 3


def test_download_learns_names_when_unknown(mock_taskcluster, mock_tenacity, tmpdir):
    # Calling download directly, without finding the artifact names first.
    a = ArtifactsHandler([], parent_dir=tmpdir.strpath)
    task = _make_task("task1", "test", "mochitest-plain", 4)
    _add_listing("task1", TEST_ARTIFACTS)
    for name in TEST_ARTIFACTS:
        _add_download("task1", name)

    a.download(task)

    assert a.artifact_names == {"test": TEST_ARTIFACTS}
    assert [artifact.path for artifact in a.artifacts] == [
        os.path.join(tmpdir.strpath, "linux_mochitest-plain-4_code-coverage-grcov.zip"),
        os.path.join(tmpdir.strpath, "linux_mochitest-plain-4_code-coverage-jsvm.zip"),
    ]


def test_find_artifact_names(mock_taskcluster):
    a = ArtifactsHandler([])
    tasks = [
        # The first test task doesn't have coverage artifacts, so the next one is used.
        _make_task("test1", "test", "xpcshell", 1),
        _make_task("test2", "test", "xpcshell", 2),
        _make_task("test3", "test", "xpcshell", 3),
        _make_task("build1", "build", "build"),
        _make_task("build2", "build", "build"),
        _make_task("source1", "source-test", "source-test"),
        # No task of this kind has coverage artifacts.
        _make_task("signing1", "build-signing", "build-signing"),
        _make_task("signing2", "build-signing", "build-signing"),
    ]
    _add_listing("test1", [])
    _add_listing("test2", TEST_ARTIFACTS + ["public/test_info/other.log"])
    _add_listing("build1", BUILD_ARTIFACTS + ["public/build/target.zip"])
    _add_listing("source1", BUILD_ARTIFACTS)
    _add_listing("signing1", [])
    _add_listing("signing2", [])

    a.find_artifact_names(tasks)

    assert a.artifact_names == {
        "test": TEST_ARTIFACTS,
        "build": BUILD_ARTIFACTS,
        "source-test": BUILD_ARTIFACTS,
        "build-signing": [],
    }
    assert [call.request.url for call in responses.calls] == [
        LISTING_URL.format(task_id)
        for task_id in ["test1", "test2", "build1", "source1", "signing1", "signing2"]
    ]

    # Names are only looked up once per kind.
    a.find_artifact_names(tasks)
    assert len(responses.calls) == 6


def test_download_different_kinds(mock_taskcluster, mock_tenacity, tmpdir):
    a = ArtifactsHandler([], parent_dir=tmpdir.strpath)
    test_task = _make_task("test1", "test", "xpcshell", 1)
    build_task = _make_task("build1", "build", "build")
    signing_task = _make_task("signing1", "build-signing", "build-signing")
    a.artifact_names = {
        "test": TEST_ARTIFACTS,
        "build": BUILD_ARTIFACTS,
        "build-signing": [],
    }
    for name in TEST_ARTIFACTS:
        _add_download("test1", name)
    _add_download("build1", BUILD_ARTIFACTS[0])

    for task in [test_task, build_task, signing_task]:
        a.download(task)

    assert [(artifact.path, artifact.task_id) for artifact in a.artifacts] == [
        (
            os.path.join(tmpdir.strpath, "linux_xpcshell-1_code-coverage-grcov.zip"),
            "test1",
        ),
        (
            os.path.join(tmpdir.strpath, "linux_xpcshell-1_code-coverage-jsvm.zip"),
            "test1",
        ),
        (os.path.join(tmpdir.strpath, "linux_build_code-coverage-grcov.zip"), "build1"),
    ]
    # No listing calls, only the three downloads.
    assert len(responses.calls) == 3


def test_download_missing_artifact(mock_taskcluster, mock_tenacity, tmpdir):
    a = ArtifactsHandler([], parent_dir=tmpdir.strpath)
    task = _make_task("task1", "test", "xpcshell", 1)
    a.artifact_names = {"test": TEST_ARTIFACTS}
    _add_download("task1", TEST_ARTIFACTS[0])
    _add_download("task1", TEST_ARTIFACTS[1], status=404)

    with structlog.testing.capture_logs() as logs:
        a.download(task)

    assert [artifact.path for artifact in a.artifacts] == [
        os.path.join(tmpdir.strpath, "linux_xpcshell-1_code-coverage-grcov.zip")
    ]
    assert [
        log["event"]
        for log in logs
        if log["event"] in ("Artifact downloaded", "Artifact not found")
    ] == ["Artifact downloaded", "Artifact not found"]
    assert len(a.download_stats) == 1
    assert not os.path.exists(
        os.path.join(tmpdir.strpath, "linux_xpcshell-1_code-coverage-jsvm.zip")
    )
    # The missing artifact is requested only once, without retries.
    missing_url = DOWNLOAD_URL.format(
        "task1", urllib.parse.quote(TEST_ARTIFACTS[1], safe="")
    )
    assert _count_calls(missing_url) == 1
    assert len(responses.calls) == 2


def test_download_error_retried(mock_taskcluster, mock_tenacity, tmpdir):
    a = ArtifactsHandler([], parent_dir=tmpdir.strpath)
    task = _make_task("task1", "test", "xpcshell", 1)
    a.artifact_names = {"test": TEST_ARTIFACTS}
    _add_download("task1", TEST_ARTIFACTS[0], status=500)

    with pytest.raises(requests.exceptions.HTTPError, match="500 Server Error"):
        a.download(task)

    assert a.artifacts == []
    assert len(responses.calls) == 5


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


@mock.patch("code_coverage_bot.taskcluster.get_task_artifacts")
def test_download_all(
    mocked_get_task_artifacts,
    DECISION_TASK_ID,
    DECISION_TASK,
    LATEST_DECISION,
    GROUP_TASKS_1,
    GROUP_TASKS_2,
    LINUX_TEST_TASK_ARTIFACTS,
    fake_artifacts,
    mock_taskcluster,
    tmpdir,
):
    mocked_get_task_artifacts.return_value = LINUX_TEST_TASK_ARTIFACTS["artifacts"]
    responses.add(
        responses.GET,
        "http://taskcluster.test/api/index/v1/task/gecko.v2.mozilla-central.revision.7828a10a94b6afb78d18d9b7b83e7aa79337cc24.taskgraph.decision",
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

        mocked_get_task_artifacts.reset_mock()

        a.download_all()

        # All tasks have the same kind, so only one listing call is needed.
        assert mocked_get_task_artifacts.call_count == 1
        assert a.artifact_names == {
            "test": [
                "public/test_info/code-coverage-grcov.zip",
                "public/test_info/code-coverage-jsvm.zip",
            ]
        }

        assert downloaded == set(
            [
                "test-linux64-ccov/opt-mochitest-devtools-chrome-e10s-4-completed",
                "test-windows10-64-ccov/debug-xpcshell-4-failed",
                "test-linux64-ccov/opt-cppunit-completed",
            ]
        )

# -*- coding: utf-8 -*-
import io
import os

import responses
import zstandard

from code_coverage_bot import taskcluster
from code_coverage_bot import trigger_missing
from code_coverage_bot import uploader
from code_coverage_bot.taskcluster import taskcluster_config
from conftest import add_file
from conftest import commit
from conftest import copy_pushlog_database


def test_trigger_from_scratch(
    monkeypatch, tmpdir, mock_secrets, mock_taskcluster, mock_phabricator, fake_hg_repo
):
    tmp_path = tmpdir.strpath

    responses.add(
        responses.HEAD,
        "https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/triggered_revisions.zst",  # noqa
        status=404,
    )

    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n")
    commit(hg, 1)

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    add_file(hg, local, "file2", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision3 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    add_file(hg, local, "file3", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision4 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    add_file(hg, local, "file4", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision5 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    myBucket = {}

    def get_bucket(acc):
        return myBucket

    monkeypatch.setattr(trigger_missing, "get_bucket", get_bucket)

    gcp_covdir_exists_calls = 0

    def gcp_covdir_exists(bucket, repository, revision, platform, suite):
        nonlocal gcp_covdir_exists_calls
        gcp_covdir_exists_calls += 1
        assert bucket == myBucket
        assert repository == "mozilla-central"
        assert platform == "all"
        assert suite == "all"
        return revision == revision3

    monkeypatch.setattr(uploader, "gcp_covdir_exists", gcp_covdir_exists)

    def slugId():
        return "myGroupId"

    monkeypatch.setattr(trigger_missing, "slugId", slugId)

    trigger_hook_calls = 0

    def get_service(serv):
        assert serv == "hooks"

        class HooksService:
            def triggerHook(self, hook_group, hook_id, payload):
                nonlocal trigger_hook_calls
                assert hook_group == "project-relman"
                assert hook_id == "code-coverage-repo-production"
                rev = revision2 if trigger_hook_calls == 0 else revision4
                assert payload == {
                    "REPOSITORY": "https://hg.mozilla.org/mozilla-central",
                    "REVISION": rev,
                    "taskGroupId": "myGroupId",
                    "taskName": f"covdir for {rev}",
                }
                trigger_hook_calls += 1

        return HooksService()

    monkeypatch.setattr(taskcluster_config, "get_service", get_service)

    get_decision_task_calls = 0

    def get_decision_task(branch, revision):
        nonlocal get_decision_task_calls
        assert branch == "mozilla-central"
        if get_decision_task_calls == 0:
            assert revision == revision2
        elif get_decision_task_calls == 1:
            assert revision == revision4
        elif get_decision_task_calls == 2:
            assert revision == revision5
        get_decision_task_calls += 1
        return f"decisionTask-{revision}"

    monkeypatch.setattr(taskcluster, "get_decision_task", get_decision_task)

    get_task_details_calls = 0

    def get_task_details(decision_task_id):
        nonlocal get_task_details_calls
        if get_task_details_calls == 0:
            assert decision_task_id == f"decisionTask-{revision2}"
            get_task_details_calls += 1
            return {"taskGroupId": f"decisionTaskGroup-{revision2}"}
        elif get_task_details_calls == 1:
            assert decision_task_id == f"decisionTask-{revision4}"
            get_task_details_calls += 1
            return {"taskGroupId": f"decisionTaskGroup-{revision4}"}
        elif get_task_details_calls == 2:
            assert decision_task_id == f"decisionTask-{revision5}"
            get_task_details_calls += 1
            return {"taskGroupId": f"decisionTaskGroup-{revision5}"}

    monkeypatch.setattr(taskcluster, "get_task_details", get_task_details)

    get_tasks_in_group_calls = 0

    def get_tasks_in_group(group_id):
        nonlocal get_tasks_in_group_calls
        if get_tasks_in_group_calls == 0:
            assert group_id == f"decisionTaskGroup-{revision2}"
            get_tasks_in_group_calls += 1
            return [
                {
                    "status": {
                        "state": "completed",
                    },
                    "task": {
                        "metadata": {
                            "name": "build-linux64-ccov/opt",
                        }
                    },
                }
            ]
        elif get_tasks_in_group_calls == 1:
            assert group_id == f"decisionTaskGroup-{revision4}"
            get_tasks_in_group_calls += 1
            return [
                {
                    "status": {
                        "state": "completed",
                    },
                    "task": {
                        "metadata": {
                            "name": "build-linux64-ccov/opt",
                        }
                    },
                }
            ]
        elif get_tasks_in_group_calls == 2:
            assert group_id == f"decisionTaskGroup-{revision5}"
            get_tasks_in_group_calls += 1
            return [
                {
                    "status": {
                        "state": "running",
                    },
                    "task": {
                        "metadata": {
                            "name": "build-linux64-ccov/opt",
                        }
                    },
                }
            ]

    monkeypatch.setattr(taskcluster, "get_tasks_in_group", get_tasks_in_group)

    trigger_missing.trigger_missing(local, out_dir=tmp_path)

    assert gcp_covdir_exists_calls == 4
    assert trigger_hook_calls == 2
    assert get_decision_task_calls == 3
    assert get_task_details_calls == 3
    assert get_tasks_in_group_calls == 3

    dctx = zstandard.ZstdDecompressor()
    with open(os.path.join(tmp_path, "triggered_revisions.zst"), "rb") as zf:
        with dctx.stream_reader(zf) as reader:
            with io.TextIOWrapper(reader, encoding="ascii") as f:
                result = set(rev for rev in f.read().splitlines())

    assert result == {revision2, revision3, revision4}


def test_trigger_from_preexisting(
    monkeypatch, tmpdir, mock_secrets, mock_taskcluster, mock_phabricator, fake_hg_repo
):
    tmp_path = tmpdir.strpath

    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n")
    commit(hg, 1)

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    add_file(hg, local, "file2", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision3 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    add_file(hg, local, "file3", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision4 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    responses.add(
        responses.HEAD,
        "https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/triggered_revisions.zst",  # noqa
        status=200,
    )

    responses.add(
        responses.GET,
        "https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/triggered_revisions.zst",  # noqa
        status=200,
        body=zstandard.ZstdCompressor().compress(
            f"{revision2}\n{revision3}".encode("ascii")
        ),
    )

    copy_pushlog_database(remote, local)

    myBucket = {}

    def get_bucket(acc):
        return myBucket

    monkeypatch.setattr(trigger_missing, "get_bucket", get_bucket)

    gcp_covdir_exists_calls = 0

    def gcp_covdir_exists(bucket, repository, revision, platform, suite):
        nonlocal gcp_covdir_exists_calls
        gcp_covdir_exists_calls += 1
        assert bucket == myBucket
        assert repository == "mozilla-central"
        assert platform == "all"
        assert suite == "all"
        return revision == revision3

    monkeypatch.setattr(uploader, "gcp_covdir_exists", gcp_covdir_exists)

    def slugId():
        return "myGroupId"

    monkeypatch.setattr(trigger_missing, "slugId", slugId)

    trigger_hook_calls = 0

    def get_service(serv):
        assert serv == "hooks"

        class HooksService:
            def triggerHook(self, hook_group, hook_id, payload):
                nonlocal trigger_hook_calls
                assert hook_group == "project-relman"
                assert hook_id == "code-coverage-repo-production"
                assert payload == {
                    "REPOSITORY": "https://hg.mozilla.org/mozilla-central",
                    "REVISION": revision4,
                    "taskGroupId": "myGroupId",
                    "taskName": f"covdir for {revision4}",
                }
                trigger_hook_calls += 1

        return HooksService()

    monkeypatch.setattr(taskcluster_config, "get_service", get_service)

    get_decision_task_calls = 0

    def get_decision_task(branch, revision):
        nonlocal get_decision_task_calls
        assert branch == "mozilla-central"
        assert revision == revision4
        get_decision_task_calls += 1
        return f"decisionTask-{revision}"

    monkeypatch.setattr(taskcluster, "get_decision_task", get_decision_task)

    get_task_details_calls = 0

    def get_task_details(decision_task_id):
        nonlocal get_task_details_calls
        assert decision_task_id == f"decisionTask-{revision4}"
        get_task_details_calls += 1
        return {"taskGroupId": f"decisionTaskGroup-{revision4}"}

    monkeypatch.setattr(taskcluster, "get_task_details", get_task_details)

    get_tasks_in_group_calls = 0

    def get_tasks_in_group(group_id):
        nonlocal get_tasks_in_group_calls
        assert group_id == f"decisionTaskGroup-{revision4}"
        get_tasks_in_group_calls += 1
        return [
            {
                "status": {
                    "state": "completed",
                },
                "task": {
                    "metadata": {
                        "name": "build-linux64-ccov/opt",
                    }
                },
            }
        ]

    monkeypatch.setattr(taskcluster, "get_tasks_in_group", get_tasks_in_group)

    trigger_missing.trigger_missing(local, out_dir=tmp_path)

    assert gcp_covdir_exists_calls == 1
    assert trigger_hook_calls == 1
    assert get_decision_task_calls == 1
    assert get_task_details_calls == 1
    assert get_tasks_in_group_calls == 1

    dctx = zstandard.ZstdDecompressor()
    with open(os.path.join(tmp_path, "triggered_revisions.zst"), "rb") as zf:
        with dctx.stream_reader(zf) as reader:
            with io.TextIOWrapper(reader, encoding="ascii") as f:
                result = set(rev for rev in f.read().splitlines())

    assert result == {revision2, revision3, revision4}

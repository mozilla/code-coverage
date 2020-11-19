# -*- coding: utf-8 -*-
import json
import os

import responses
import zstandard

from code_coverage_bot import commit_coverage
from conftest import add_file
from conftest import commit
from conftest import copy_pushlog_database
from conftest import covdir_report


def test_generate_from_scratch(
    monkeypatch, tmpdir, mock_secrets, mock_taskcluster, mock_phabricator, fake_hg_repo
):
    tmp_path = tmpdir.strpath

    responses.add(
        responses.HEAD,
        "https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/commit_coverage.json.zst",  # noqa
        status=404,
    )

    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    report = covdir_report(
        {
            "source_files": [
                {"name": "file", "coverage": [None, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]}
            ]
        }
    )

    myBucket = {}

    def get_bucket(acc):
        return myBucket

    monkeypatch.setattr(commit_coverage, "get_bucket", get_bucket)

    def list_reports(bucket, repo):
        assert bucket == myBucket
        assert repo == "mozilla-central"
        yield revision2, "linux", "all"
        yield revision2, "all", "xpcshell"
        yield revision2, "all", "all"

    monkeypatch.setattr(commit_coverage, "list_reports", list_reports)

    def download_report(report_dir, bucket, report_name):
        os.makedirs(
            os.path.join(tmp_path, report_dir, "mozilla-central", revision2),
            exist_ok=True,
        )
        with open(
            os.path.join(
                tmp_path, report_dir, "mozilla-central", revision2, "all:all.json"
            ),
            "w",
        ) as f:
            json.dump(report, f)

        return True

    monkeypatch.setattr(commit_coverage, "download_report", download_report)

    commit_coverage.generate(local, out_dir=tmp_path)

    dctx = zstandard.ZstdDecompressor()
    with open(os.path.join(tmp_path, "commit_coverage.json.zst"), "rb") as zf:
        with dctx.stream_reader(zf) as reader:
            result = json.load(reader)

    assert result == {
        revision1: {
            "added": 3,
            "covered": 2,
            "unknown": 0,
        },
        revision2: {
            "added": 6,
            "covered": 0,
            "unknown": 0,
        },
    }


def test_generate_two_pushes(
    monkeypatch, tmpdir, mock_secrets, mock_taskcluster, mock_phabricator, fake_hg_repo
):
    tmp_path = tmpdir.strpath

    responses.add(
        responses.HEAD,
        "https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/commit_coverage.json.zst",  # noqa
        status=404,
    )

    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file1", "1\n2\n3\n4\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file1", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    add_file(hg, local, "file2", "1\n2\n3\n4\n")
    revision3 = commit(hg, 1)

    add_file(hg, local, "file2", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision4 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    report1 = covdir_report(
        {
            "source_files": [
                {"name": "file1", "coverage": [None, 1, 1, 0, 0, 0, 0, 0, 0, 0]}
            ]
        }
    )

    report2 = covdir_report(
        {
            "source_files": [
                {"name": "file1", "coverage": [None, 1, 1, 0, 0, 0, 0, 0, 0, 0]},
                {"name": "file2", "coverage": [None, 0, 1, 0, 0, 0, 0, 0, 1, 1]},
            ]
        }
    )

    myBucket = {}

    def get_bucket(acc):
        return myBucket

    monkeypatch.setattr(commit_coverage, "get_bucket", get_bucket)

    def list_reports(bucket, repo):
        assert bucket == myBucket
        assert repo == "mozilla-central"
        yield revision2, "linux", "all"
        yield revision2, "all", "xpcshell"
        yield revision2, "all", "all"
        yield revision4, "all", "all"

    monkeypatch.setattr(commit_coverage, "list_reports", list_reports)

    def download_report(report_dir, bucket, report_name):
        os.makedirs(
            os.path.join(tmp_path, report_dir, "mozilla-central", revision2),
            exist_ok=True,
        )
        with open(
            os.path.join(
                tmp_path, report_dir, "mozilla-central", revision2, "all:all.json"
            ),
            "w",
        ) as f:
            json.dump(report1, f)

        os.makedirs(
            os.path.join(tmp_path, report_dir, "mozilla-central", revision4),
            exist_ok=True,
        )
        with open(
            os.path.join(
                tmp_path, report_dir, "mozilla-central", revision4, "all:all.json"
            ),
            "w",
        ) as f:
            json.dump(report2, f)

        return True

    monkeypatch.setattr(commit_coverage, "download_report", download_report)

    commit_coverage.generate(local, out_dir=tmp_path)

    dctx = zstandard.ZstdDecompressor()
    with open(os.path.join(tmp_path, "commit_coverage.json.zst"), "rb") as zf:
        with dctx.stream_reader(zf) as reader:
            result = json.load(reader)

    assert result == {
        revision1: {
            "added": 3,
            "covered": 2,
            "unknown": 0,
        },
        revision2: {
            "added": 6,
            "covered": 0,
            "unknown": 0,
        },
        revision3: {
            "added": 3,
            "covered": 1,
            "unknown": 0,
        },
        revision4: {
            "added": 6,
            "covered": 2,
            "unknown": 0,
        },
    }


def test_generate_from_preexisting(
    monkeypatch, tmpdir, mock_secrets, mock_taskcluster, mock_phabricator, fake_hg_repo
):
    tmp_path = tmpdir.strpath

    responses.add(
        responses.HEAD,
        "https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/commit_coverage.json.zst",  # noqa
        status=200,
    )

    responses.add(
        responses.GET,
        "https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/project.relman.code-coverage.production.cron.latest/artifacts/public/commit_coverage.json.zst",  # noqa
        status=200,
        body=zstandard.ZstdCompressor().compress(
            json.dumps(
                {
                    "revision1": {
                        "added": 7,
                        "covered": 3,
                        "unknown": 0,
                    },
                    "revision2": None,
                }
            ).encode("ascii")
        ),
    )

    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    report = covdir_report(
        {
            "source_files": [
                {"name": "file", "coverage": [None, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]}
            ]
        }
    )

    myBucket = {}

    def get_bucket(acc):
        return myBucket

    monkeypatch.setattr(commit_coverage, "get_bucket", get_bucket)

    def list_reports(bucket, repo):
        assert bucket == myBucket
        assert repo == "mozilla-central"
        yield revision2, "linux", "all"
        yield revision2, "all", "xpcshell"
        yield revision2, "all", "all"

    monkeypatch.setattr(commit_coverage, "list_reports", list_reports)

    def download_report(report_dir, bucket, report_name):
        os.makedirs(
            os.path.join(tmp_path, report_dir, "mozilla-central", revision2),
            exist_ok=True,
        )
        with open(
            os.path.join(
                tmp_path, report_dir, "mozilla-central", revision2, "all:all.json"
            ),
            "w",
        ) as f:
            json.dump(report, f)

        return True

    monkeypatch.setattr(commit_coverage, "download_report", download_report)

    commit_coverage.generate(local, out_dir=tmp_path)

    dctx = zstandard.ZstdDecompressor()
    with open(os.path.join(tmp_path, "commit_coverage.json.zst"), "rb") as zf:
        with dctx.stream_reader(zf) as reader:
            result = json.load(reader)

    assert result == {
        "revision1": {"added": 7, "covered": 3, "unknown": 0},
        "revision2": None,
        revision1: {
            "added": 3,
            "covered": 2,
            "unknown": 0,
        },
        revision2: {
            "added": 6,
            "covered": 0,
            "unknown": 0,
        },
    }

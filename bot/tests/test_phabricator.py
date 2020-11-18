# -*- coding: utf-8 -*-

import json
import os
import urllib.parse

import responses

from code_coverage_bot.phabricator import PhabricatorUploader
from conftest import add_file
from conftest import changesets
from conftest import commit
from conftest import copy_pushlog_database
from conftest import covdir_report


def test_simple(mock_secrets, mock_phabricator, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision = commit(hg, 1)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision)
    report = covdir_report(
        {"source_files": [{"name": "file", "coverage": [None, 0, 1, 1, 1, 1, 0]}]}
    )
    results = phabricator.generate(report, changesets(local, revision))

    assert results == {
        revision: {
            "revision_id": 1,
            "paths": {
                "file": {
                    "coverage": "NUCCCCU",
                    "lines_added": 6,
                    "lines_covered": 4,
                    "lines_unknown": 0,
                }
            },
        }
    }

    phabricator.upload(report, changesets(local, revision))

    assert len(responses.calls) >= 3

    call = responses.calls[-5]
    assert (
        call.request.url == "http://phabricator.test/api/differential.revision.search"
    )
    params = json.loads(urllib.parse.parse_qs(call.request.body)["params"][0])
    assert params["constraints"]["ids"] == [1]

    call = responses.calls[-4]
    assert (
        call.request.url == "http://phabricator.test/api/harbormaster.queryautotargets"
    )
    params = json.loads(urllib.parse.parse_qs(call.request.body)["params"][0])
    assert params["objectPHID"] == "PHID-DIFF-test"
    assert params["targetKeys"] == ["arcanist.unit"]

    call = responses.calls[-3]
    assert call.request.url == "http://phabricator.test/api/harbormaster.sendmessage"
    params = json.loads(urllib.parse.parse_qs(call.request.body)["params"][0])
    assert params["buildTargetPHID"] == "PHID-HMBT-test"
    assert params["type"] == "pass"
    assert params["unit"] == [
        {
            "name": "Aggregate coverage information",
            "result": "pass",
            "coverage": {"file": "NUCCCCU"},
        }
    ]
    assert params["lint"] == []

    call = responses.calls[-2]
    assert (
        call.request.url == "http://phabricator.test/api/harbormaster.queryautotargets"
    )
    params = json.loads(urllib.parse.parse_qs(call.request.body)["params"][0])
    assert params["objectPHID"] == "PHID-DIFF-test"
    assert params["targetKeys"] == ["arcanist.lint"]

    call = responses.calls[-1]
    assert call.request.url == "http://phabricator.test/api/harbormaster.sendmessage"
    params = json.loads(urllib.parse.parse_qs(call.request.body)["params"][0])
    assert params["buildTargetPHID"] == "PHID-HMBT-test-lint"
    assert params["type"] == "pass"
    assert params["unit"] == []
    assert params["lint"] == []


def test_file_with_no_coverage(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision = commit(hg, 1)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision)
    report = covdir_report({"source_files": []})
    results = phabricator.generate(report, changesets(local, revision))

    assert results == {revision: {"revision_id": 1, "paths": {}}}


def test_one_commit_without_differential(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision = commit(hg)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision)
    report = covdir_report(
        {"source_files": [{"name": "file", "coverage": [None, 0, 1, 1, 1, 1, 0]}]}
    )
    results = phabricator.generate(report, changesets(local, revision))

    assert results == {
        revision: {
            "revision_id": None,
            "paths": {
                "file": {
                    "coverage": "NUCCCCU",
                    "lines_added": 6,
                    "lines_covered": 4,
                    "lines_unknown": 0,
                }
            },
        }
    }


def test_two_commits_two_files(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file1_commit1", "1\n2\n3\n4\n5\n6\n7\n")
    add_file(hg, local, "file2_commit1", "1\n2\n3\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file3_commit2", "1\n2\n3\n4\n5\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision2)
    report = covdir_report(
        {
            "source_files": [
                {"name": "file1_commit1", "coverage": [None, 0, 1, 1, 1, 1, 0]},
                {"name": "file2_commit1", "coverage": [1, 1, 0]},
                {"name": "file3_commit2", "coverage": [1, 1, 0, 1, None]},
            ]
        }
    )
    results = phabricator.generate(report, changesets(local, revision2))

    assert results == {
        revision1: {
            "revision_id": 1,
            "paths": {
                "file1_commit1": {
                    "coverage": "NUCCCCU",
                    "lines_added": 6,
                    "lines_covered": 4,
                    "lines_unknown": 0,
                },
                "file2_commit1": {
                    "coverage": "CCU",
                    "lines_added": 3,
                    "lines_covered": 2,
                    "lines_unknown": 0,
                },
            },
        },
        revision2: {
            "revision_id": 2,
            "paths": {
                "file3_commit2": {
                    "coverage": "CCUCN",
                    "lines_added": 4,
                    "lines_covered": 3,
                    "lines_unknown": 0,
                }
            },
        },
    }


def test_changesets_overwriting(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file", "1\n2\n3\n42\n5\n6\n7\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision2)
    report = covdir_report(
        {"source_files": [{"name": "file", "coverage": [None, 0, 1, 1, 1, 1, 0]}]}
    )
    results = phabricator.generate(report, changesets(local, revision2))

    assert results == {
        revision1: {
            "revision_id": 1,
            "paths": {
                "file": {
                    "coverage": "NUCXCCU",
                    "lines_added": 6,
                    "lines_covered": 3,
                    "lines_unknown": 1,
                }
            },
        },
        revision2: {
            "revision_id": 2,
            "paths": {
                "file": {
                    "coverage": "NUCCCCU",
                    "lines_added": 1,
                    "lines_covered": 1,
                    "lines_unknown": 0,
                }
            },
        },
    }


def test_changesets_displacing(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file", "-1\n-2\n1\n2\n3\n4\n5\n6\n7\n8\n9\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision2)
    report = covdir_report(
        {
            "source_files": [
                {"name": "file", "coverage": [0, 1, None, 0, 1, 1, 1, 1, 0, 1, 0]}
            ]
        }
    )
    results = phabricator.generate(report, changesets(local, revision2))

    assert results == {
        revision1: {
            "revision_id": 1,
            "paths": {
                "file": {
                    "coverage": "NUCCCCU",
                    "lines_added": 6,
                    "lines_covered": 4,
                    "lines_unknown": 0,
                }
            },
        },
        revision2: {
            "revision_id": 2,
            "paths": {
                "file": {
                    "coverage": "UCNUCCCCUCU",
                    "lines_added": 4,
                    "lines_covered": 2,
                    "lines_unknown": 0,
                }
            },
        },
    }


def test_changesets_reducing_size(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n")
    revision2 = commit(hg, 2)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision2)
    report = covdir_report(
        {"source_files": [{"name": "file", "coverage": [None, 0, 1, 1, 1]}]}
    )
    results = phabricator.generate(report, changesets(local, revision2))

    assert results == {
        revision1: {
            "revision_id": 1,
            "paths": {
                "file": {
                    "coverage": "NUCCCXX",
                    "lines_added": 6,
                    "lines_covered": 3,
                    "lines_unknown": 2,
                }
            },
        },
        revision2: {
            "revision_id": 2,
            "paths": {
                "file": {
                    "coverage": "NUCCC",
                    "lines_added": 0,
                    "lines_covered": 0,
                    "lines_unknown": 0,
                }
            },
        },
    }


def test_changesets_overwriting_one_commit_without_differential(
    mock_secrets, fake_hg_repo
):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision1 = commit(hg, 1)

    add_file(hg, local, "file", "1\n2\n3\n42\n5\n6\n7\n")
    revision2 = commit(hg)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision2)

    report = covdir_report(
        {"source_files": [{"name": "file", "coverage": [None, 0, 1, 1, 1, 1, 0]}]}
    )
    results = phabricator.generate(report, changesets(local, revision2))

    assert results == {
        revision1: {
            "revision_id": 1,
            "paths": {
                "file": {
                    "coverage": "NUCXCCU",
                    "lines_added": 6,
                    "lines_covered": 3,
                    "lines_unknown": 1,
                }
            },
        },
        revision2: {
            "revision_id": None,
            "paths": {
                "file": {
                    "coverage": "NUCCCCU",
                    "lines_added": 1,
                    "lines_covered": 1,
                    "lines_unknown": 0,
                }
            },
        },
    }


def test_removed_file(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision1 = commit(hg, 1)

    hg.remove(files=[bytes(os.path.join(local, "file"), "ascii")])
    revision2 = commit(hg)

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision2)
    report = covdir_report({"source_files": []})
    results = phabricator.generate(report, changesets(local, revision2))

    assert results == {
        revision1: {"revision_id": 1, "paths": {}},
        revision2: {"revision_id": None, "paths": {}},
    }


def test_backout_removed_file(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision1 = commit(hg, 1)

    hg.remove(files=[bytes(os.path.join(local, "file"), "ascii")])
    revision2 = commit(hg, 2)

    hg.backout(rev=revision2, message="backout", user="marco")
    revision3 = hg.log(limit=1)[0][1].decode("ascii")

    hg.push(dest=bytes(remote, "ascii"))

    copy_pushlog_database(remote, local)

    phabricator = PhabricatorUploader(local, revision3)
    report = covdir_report(
        {"source_files": [{"name": "file", "coverage": [None, 0, 1, 1, 1, 1, 0]}]}
    )
    results = phabricator.generate(report, changesets(local, revision3))

    assert results == {
        revision1: {
            "revision_id": 1,
            "paths": {
                "file": {
                    "coverage": "NUCCCCU",
                    "lines_added": 6,
                    "lines_covered": 4,
                    "lines_unknown": 0,
                }
            },
        },
        revision2: {"revision_id": 2, "paths": {}},
        revision3: {"revision_id": None, "paths": {}},
    }


def test_third_party(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "tools/rewriting/ThirdPartyPaths.txt", "third_party\nsome/path")
    revision = commit(hg, 1)

    phabricator = PhabricatorUploader(local, revision)

    assert phabricator.third_parties == ["third_party", "some/path"]

    assert phabricator.is_third_party("js/src/xx.cpp") is False
    assert phabricator.is_third_party("dom/media/yyy.h") is False
    assert phabricator.is_third_party("third_party/test.cpp") is True
    assert phabricator.is_third_party("some/test.cpp") is False
    assert phabricator.is_third_party("some/path/test.cpp") is True


def test_supported_extensions(mock_secrets, fake_hg_repo):
    hg, local, remote = fake_hg_repo

    add_file(hg, local, "file", "1\n2\n3\n4\n5\n6\n7\n")
    revision = commit(hg, 1)

    phabricator = PhabricatorUploader(local, revision)

    assert phabricator.is_supported_extension("README") is False
    assert phabricator.is_supported_extension("requirements.txt") is False
    assert phabricator.is_supported_extension("tools/Cargo.toml") is False
    assert phabricator.is_supported_extension("tools/Cargo.lock") is False
    assert phabricator.is_supported_extension("dom/feature.idl") is False
    assert phabricator.is_supported_extension("dom/feature.webidl") is False
    assert phabricator.is_supported_extension("xpcom/moz.build") is False
    assert phabricator.is_supported_extension("payload.json") is False
    assert phabricator.is_supported_extension("inline.patch") is False
    assert phabricator.is_supported_extension("README.mozilla") is False
    assert phabricator.is_supported_extension("config.yml") is False
    assert phabricator.is_supported_extension("config.yaml") is False
    assert phabricator.is_supported_extension("config.ini") is False
    assert phabricator.is_supported_extension("tooling.py") is False

    assert phabricator.is_supported_extension("test.cpp") is True
    assert phabricator.is_supported_extension("some/path/to/test.cpp") is True
    assert phabricator.is_supported_extension("xxxYYY.h") is True
    assert phabricator.is_supported_extension("test.c") is True
    assert phabricator.is_supported_extension("test.cc") is True
    assert phabricator.is_supported_extension("test.cxx") is True
    assert phabricator.is_supported_extension("test.hh") is True
    assert phabricator.is_supported_extension("test.hpp") is True
    assert phabricator.is_supported_extension("test.hxx") is True
    assert phabricator.is_supported_extension("test.js") is True
    assert phabricator.is_supported_extension("test.jsm") is True
    assert phabricator.is_supported_extension("test.xul") is True
    assert phabricator.is_supported_extension("test.xml") is True
    assert phabricator.is_supported_extension("test.html") is True
    assert phabricator.is_supported_extension("test.xhtml") is True
    assert phabricator.is_supported_extension("test.rs") is True

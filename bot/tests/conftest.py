# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager

import hglib
import pytest
import responses

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def copy_pushlog_database(remote, local):
    shutil.copyfile(
        os.path.join(remote, ".hg/pushlog2.db"), os.path.join(local, ".hg/pushlog2.db")
    )


def add_file(hg, repo_dir, name, contents):
    path = os.path.join(repo_dir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w") as f:
        f.write(contents)

    hg.add(files=[bytes(path, "ascii")])


def commit(hg, diff_rev=None):
    commit_message = "Commit {}".format(hg.status())
    if diff_rev is not None:
        commit_message += "Differential Revision: https://phabricator.services.mozilla.com/D{}".format(
            diff_rev
        )

    i, revision = hg.commit(message=commit_message, user="Moz Illa <milla@mozilla.org>")

    return str(revision, "ascii")


def changesets(repo_dir, revision):
    from code_coverage_bot import hgmo

    with hgmo.HGMO(repo_dir) as hgmo_server:
        return hgmo_server.get_automation_relevance_changesets(revision)


def load_file(path):
    with open(os.path.join(FIXTURES_DIR, path)) as f:
        return f.read()


def load_json(path):
    with open(os.path.join(FIXTURES_DIR, path)) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def TASK_NOT_FOUND():
    return load_json("task_not_found.json")


@pytest.fixture(scope="session")
def DECISION_TASK_ID():
    return "OuvSoOjkSvKYLbaGMknMfA"


@pytest.fixture(scope="session")
def DECISION_TASK():
    return load_json("decision_task.json")


@pytest.fixture(scope="session")
def LATEST_DECISION():
    return load_json("latest_decision.json")


@pytest.fixture(scope="session")
def LINUX_TASK_ID():
    return "MCIO1RWTRu2GhiE7_jILBw"


@pytest.fixture(scope="session")
def LINUX_TASK():
    return load_json("linux_task.json")


@pytest.fixture(scope="session")
def LINUX_TASK_STATUS():
    return load_json("linux_task_status.json")


@pytest.fixture(scope="session")
def LINUX_TASK_ARTIFACTS():
    return load_json("linux_task_artifacts.json")


@pytest.fixture(scope="session")
def GROUP_TASKS_1():
    return load_json("task-group_1.json")


@pytest.fixture(scope="session")
def GROUP_TASKS_2():
    return load_json("task-group_2.json")


@pytest.fixture(scope="session")
def LINUX_TEST_TASK_ARTIFACTS():
    return load_json("linux_test_task_artifacts.json")


@pytest.fixture(scope="session")
def TEST_TASK_FROM_GROUP():
    return load_json("test_task_from_group.json")


@pytest.fixture()
def MERCURIAL_COMMIT():
    hg_commit = "0d1e55d87931fe70ec1d007e886bcd58015ff770"

    responses.add(
        responses.GET,
        f"https://mapper.mozilla-releng.net/gecko-dev/rev/hg/{hg_commit}",
        body=f"40e8eb46609dcb8780764774ec550afff1eed3a5 {hg_commit}",
        status=200,
    )

    return hg_commit


@pytest.fixture()
def GITHUB_COMMIT():
    git_commit = "40e8eb46609dcb8780764774ec550afff1eed3a5"

    responses.add(
        responses.GET,
        f"https://mapper.mozilla-releng.net/gecko-dev/rev/git/{git_commit}",
        body=f"{git_commit} 0d1e55d87931fe70ec1d007e886bcd58015ff770",
        status=200,
    )

    return git_commit


@contextmanager
def generate_coverage_artifact(name):
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = os.path.join(tmp_dir, name + ".zip")
        with zipfile.ZipFile(zip_path, "w") as z:
            z.write(os.path.join(FIXTURES_DIR, name))
        yield zip_path


@pytest.fixture(scope="session")
def grcov_artifact():
    with generate_coverage_artifact("grcov.info") as f:
        yield f


@pytest.fixture(scope="session")
def jsvm_artifact():
    with generate_coverage_artifact("jsvm.info") as f:
        yield f


@pytest.fixture(scope="session")
def grcov_existing_file_artifact():
    with generate_coverage_artifact("grcov_existing_file.info") as f:
        yield f


@pytest.fixture(scope="session")
def grcov_uncovered_artifact():
    with generate_coverage_artifact("grcov_uncovered_file.info") as f:
        yield f


@pytest.fixture(scope="session")
def jsvm_uncovered_artifact():
    with generate_coverage_artifact("jsvm_uncovered_file.info") as f:
        yield f


@pytest.fixture(scope="session")
def grcov_uncovered_function_artifact():
    with generate_coverage_artifact("grcov_uncovered_function.info") as f:
        yield f


@pytest.fixture(scope="session")
def jsvm_uncovered_function_artifact():
    with generate_coverage_artifact("jsvm_uncovered_function.info") as f:
        yield f


@pytest.fixture(scope="session")
def mock_secrets():
    from code_coverage_bot.secrets import secrets

    secrets.update(
        {
            "PHABRICATOR_ENABLED": True,
            "PHABRICATOR_URL": "http://phabricator.test/api/",
            "PHABRICATOR_TOKEN": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "EMAIL_ADDRESSES": ["admin@allizom.org"],
        }
    )


@pytest.fixture()
def codecov_commits():
    dir_path = os.path.join(FIXTURES_DIR, "codecov_commits")
    for fname in os.listdir(dir_path):
        with open(os.path.join(dir_path, fname)) as f:
            data = json.load(f)
            status = data["meta"]["status"]

            responses.add(
                responses.GET,
                f"https://codecov.io/api/gh/marco-c/gecko-dev/commit/{fname[:-5]}",
                json=data,
                status=status,
            )


@pytest.fixture
def fake_hg_repo(tmpdir):
    tmp_path = tmpdir.strpath
    dest = os.path.join(tmp_path, "repos")
    local = os.path.join(dest, "local")
    remote = os.path.join(dest, "remote")
    for d in [local, remote]:
        os.makedirs(d)
        hglib.init(d)

    os.environ["USER"] = "app"
    hg = hglib.open(local)

    responses.add_passthru("http://localhost:8000")

    yield hg, local, remote

    hg.close()


@pytest.fixture
def fake_hg_repo_with_contents(fake_hg_repo):
    hg, local, remote = fake_hg_repo

    files = [
        {"name": "mozglue/build/dummy.cpp", "size": 1},
        {"name": "toolkit/components/osfile/osfile.jsm", "size": 2},
        {"name": "js/src/jit/JIT.cpp", "size": 3},
        {"name": "toolkit/components/osfile/osfile-win.jsm", "size": 4},
        {"name": "js/src/jit/BitSet.cpp", "size": 5},
        {"name": "code_coverage_bot/cli.py", "size": 6},
    ]

    for c in "?!":
        for f in files:
            fname = os.path.join(local, f["name"])
            parent = os.path.dirname(fname)
            if not os.path.exists(parent):
                os.makedirs(parent)
            with open(fname, "w") as Out:
                Out.write(c * f["size"])
            hg.add(files=[bytes(fname, "ascii")])
            hg.commit(
                message=f"Commit file {fname} with {c} inside",
                user="Moz Illa <milla@mozilla.org>",
            )
            hg.push(dest=bytes(remote, "ascii"))

    shutil.copyfile(
        os.path.join(remote, ".hg/pushlog2.db"), os.path.join(local, ".hg/pushlog2.db")
    )

    return local


@pytest.fixture
def mock_phabricator():
    """
    Mock phabricator authentication process
    """

    def _response(name):
        path = os.path.join(FIXTURES_DIR, f"phabricator_{name}.json")
        assert os.path.exists(path)
        return open(path).read()

    responses.add(
        responses.POST,
        "http://phabricator.test/api/user.whoami",
        body=_response("auth"),
        content_type="application/json",
    )

    responses.add(
        responses.POST,
        "http://phabricator.test/api/differential.revision.search",
        body=_response("revision_search"),
        content_type="application/json",
    )

    responses.add(
        responses.POST,
        "http://phabricator.test/api/harbormaster.queryautotargets",
        body=_response("harbormaster_queryautotargets"),
        content_type="application/json",
    )

    responses.add(
        responses.POST,
        "http://phabricator.test/api/harbormaster.sendmessage",
        body=_response("harbormaster_sendmessage"),
        content_type="application/json",
    )

    responses.add(
        responses.POST,
        "http://phabricator.test/api/harbormaster.queryautotargets",
        body=_response("harbormaster_queryautotargets_lint"),
        content_type="application/json",
    )

    responses.add(
        responses.POST,
        "http://phabricator.test/api/harbormaster.sendmessage",
        body=_response("harbormaster_sendmessage_lint"),
        content_type="application/json",
    )


@pytest.fixture
def fake_source_dir(tmpdir):
    tmpdir_path = tmpdir.strpath

    os.makedirs(os.path.join(tmpdir_path, "code_coverage_bot"))

    with open(os.path.join(tmpdir_path, "code_coverage_bot", "cli.py"), "w") as f:
        f.write("1\n2\n")

    return tmpdir_path


@pytest.fixture
def mock_taskcluster():
    """
    Mock a taskcluster proxy usage
    """
    from code_coverage_bot.taskcluster import taskcluster_config

    responses.add(
        responses.POST,
        "http://taskcluster.test/api/notify/v1/email",
        body="{}",
        content_type="application/json",
    )

    taskcluster_config.options = {"rootUrl": "http://taskcluster.test"}


def covdir_report(codecov):
    """
    Convert source files to covdir format
    """
    assert isinstance(codecov, dict)
    assert "source_files" in codecov

    out = {}
    for cov in codecov["source_files"]:
        assert "/" not in cov["name"]
        coverage = cov["coverage"]
        total = len(coverage)
        covered = sum(l is not None and l > 0 for l in coverage)
        out[cov["name"]] = {
            "children": {},
            "name": cov["name"],
            "coverage": coverage,
            "coveragePercent": 100.0 * covered / total,
            "linesCovered": covered,
            "linesMissed": total - covered,
            "linesTotal": total,
        }

    # Covdir has a root level
    def _sum(name):
        return sum(c[name] for c in out.values())

    return {
        "children": out,
        "name": "src",
        "coverage": [],
        "coveragePercent": _sum("coveragePercent") / len(out) if out else 0,
        "linesCovered": _sum("linesCovered"),
        "linesMissed": _sum("linesMissed"),
        "linesTotal": _sum("linesTotal"),
    }

# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

import responses

from code_coverage_bot.artifacts import Artifact
from code_coverage_bot.hooks.repo import RepositoryHook


def test_jsvm_content(tmpdir, jsvm_artifact, jsvm_obj_artifact):
    """
    Test that a jsvm artifact contains valid files
    """
    task_id = "xx"
    rev = "deadbeef1234"
    branch = "testbot"

    # Provide same task for all platforms
    responses.add(
        responses.GET,
        re.compile(
            f"https://index.taskcluster.net/v1/task/gecko.v2.{branch}.revision.{rev}"
        ),
        json={"taskId": task_id},
        status=200,
    )

    cache = tmpdir.mkdir("cache")
    repo = cache.mkdir(branch)
    hook = RepositoryHook(
        f"https://hg.mozilla.org/{branch}", rev, "*", cache, tmpdir.mkdir("build")
    )

    # Use jsvm artifact without any file in the repo
    hook.artifactsHandler.artifacts = [
        Artifact(jsvm_artifact, task_id, "linux", "crashtest", "1")
    ]
    assert hook.check_javascript_files() == 1

    # Now that the file is in the repo, the check should pass
    assert repo.join("toolkit/components/osfile/osfile.jsm").ensure(file=True)
    assert hook.check_javascript_files() == 0

    # Using the artifact with an obj file should yield the same result
    hook.artifactsHandler.artifacts = [
        Artifact(jsvm_obj_artifact, task_id, "linux", "crashtest", "1")
    ]
    assert hook.check_javascript_files() == 0

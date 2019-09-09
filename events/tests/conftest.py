# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
import responses
from libmozevent import taskcluster_config


@pytest.fixture
def mock_taskcluster():
    """
    Mock Tasklcuster authentication
    """
    taskcluster_config.options = {"rootUrl": "http://taskcluster.test"}

    responses.add(
        responses.GET,
        "https://queue.taskcluster.net/v1/task-group/aGroup/list",
        json={"taskGroupId": "aGroup", "tasks": []},
    )

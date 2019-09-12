# -*- coding: utf-8 -*-
import json
import os

import jsone
import jsonschema
import pytest

HOOK_REPO = os.path.join(os.path.dirname(__file__), "../taskcluster-hook-repo.json")
HOOK_CRON = os.path.join(os.path.dirname(__file__), "../taskcluster-hook-cron.json")

payloads = [
    # Trigger by interface or API
    (HOOK_REPO, {"firedBy": "triggerHook", "taskId": "xxx", "payload": {}}),
    (
        HOOK_REPO,
        {
            "firedBy": "triggerHook",
            "taskId": "xxx",
            "payload": {"taskName": "Custom task name", "taskGroupId": "yyyy"},
        },
    ),
    # Cron trigger
    (HOOK_CRON, {"firedBy": "schedule", "taskId": "xxx"}),
]


@pytest.mark.parametrize("hook_path, payload", payloads)
def test_hook_syntax(hook_path, payload):
    """
    Validate the Taskcluster hook syntax
    """
    assert os.path.exists(hook_path)

    with open(hook_path, "r") as f:
        # Patch the hook as in the taskboot deployment
        content = f.read()
        content = content.replace("REVISION", "deadbeef1234")
        content = content.replace("CHANNEL", "test")

        # Now parse it as json
        hook_content = json.loads(content)

    jsonschema.validate(instance=payload, schema=hook_content["triggerSchema"])

    jsone.render(hook_content, context=payload)

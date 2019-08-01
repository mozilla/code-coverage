# -*- coding: utf-8 -*-
import json
import os

import jsone
import jsonschema
import pytest

HOOK = os.path.join(os.path.dirname(__file__), '../taskcluster-hook.json')

payloads = [
    # Trigger by interface or API
    {
        'firedBy': 'triggerHook',
        'taskId': 'xxx',
        'payload': {},
    },
    {
        'firedBy': 'triggerHook',
        'taskId': 'xxx',
        'payload': {
            'taskName': 'Custom task name',
            'taskGroupId': 'yyyy',
        },
    },

    # Cron trigger
    {
        'firedBy': 'schedule',
        'taskId': 'xxx',
    },
]


@pytest.mark.parametrize('payload', payloads)
def test_hook_syntax(payload):
    '''
    Validate the Taskcluster hook syntax
    '''
    assert os.path.exists(HOOK)

    with open(HOOK, 'r') as f:
        # Patch the hook as in the taskboot deployment
        content = f.read()
        content = content.replace('REVISION', 'deadbeef1234')
        content = content.replace('CHANNEL', 'test')

        # Now parse it as json
        hook_content = json.loads(content)

    jsonschema.validate(instance=payload, schema=hook_content['triggerSchema'])

    jsone.render(hook_content, context=payload)

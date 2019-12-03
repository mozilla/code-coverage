# -*- coding: utf-8 -*-

from taskcluster.helper import TaskclusterConfig

taskcluster_config = TaskclusterConfig("https://firefox-ci-tc.services.mozilla.com")

QUEUE_MONITORING = "monitoring"
QUEUE_PULSE = "pulse"

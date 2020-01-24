# -*- coding: utf-8 -*-

from taskcluster.helper import TaskclusterConfig

taskcluster = TaskclusterConfig("https://firefox-ci-tc.services.mozilla.com")

# Force root url to avoid proxy as grcov is not available on Community instance
taskcluster.options = {"rootUrl": taskcluster.default_url}

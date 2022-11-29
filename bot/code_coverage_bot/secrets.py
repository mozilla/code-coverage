# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from code_coverage_bot.taskcluster import taskcluster_config


class Secrets(dict):
    EMAIL_ADDRESSES = "EMAIL_ADDRESSES"
    APP_CHANNEL = "APP_CHANNEL"
    BACKEND_HOST = "BACKEND_HOST"
    PHABRICATOR_ENABLED = "PHABRICATOR_ENABLED"
    PHABRICATOR_URL = "PHABRICATOR_URL"
    PHABRICATOR_TOKEN = "PHABRICATOR_TOKEN"
    GOOGLE_CLOUD_STORAGE = "GOOGLE_CLOUD_STORAGE"
    CHECK_JAVASCRIPT_FILES = "CHECK_JAVASCRIPT_FILES"

    def load(self, taskcluster_secret=None, local_secrets=None):
        taskcluster_config.load_secrets(
            taskcluster_secret,
            prefixes=["common", "bot"],
            required=[
                Secrets.APP_CHANNEL,
                Secrets.BACKEND_HOST,
                Secrets.GOOGLE_CLOUD_STORAGE,
                Secrets.PHABRICATOR_ENABLED,
                Secrets.PHABRICATOR_URL,
                Secrets.PHABRICATOR_TOKEN,
            ],
            local_secrets=local_secrets,
        )
        self.update(taskcluster_config.secrets)


secrets = Secrets()

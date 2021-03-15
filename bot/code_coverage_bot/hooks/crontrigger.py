# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import structlog

from code_coverage_bot import config
from code_coverage_bot import trigger_missing
from code_coverage_bot import uploader
from code_coverage_bot.cli import setup_cli
from code_coverage_bot.hooks.base import Hook
from code_coverage_bot.secrets import secrets

logger = structlog.get_logger(__name__)


class CronTriggerHook(Hook):
    """
    This function is executed when the bot is triggered via cron.
    """

    def __init__(self, *args, **kwargs):
        # Retrieve latest ingested revision
        try:
            revision = uploader.gcp_latest("mozilla-central")[0]["revision"]
        except Exception as e:
            logger.warn("Failed to retrieve the latest reports ingested: {}".format(e))
            raise

        super().__init__(config.MOZILLA_CENTRAL_REPOSITORY, revision, *args, **kwargs)

    def run(self) -> None:
        trigger_missing.trigger_missing(config.MOZILLA_CENTRAL_REPOSITORY)

        # Index the task in the TaskCluster index at the given revision and as "latest".
        # Given that all tasks have the same rank, the latest task that finishes will
        # overwrite the "latest" entry.
        self.index_task(
            [
                "project.relman.code-coverage.{}.crontrigger.{}".format(
                    secrets[secrets.APP_CHANNEL], self.revision
                ),
                "project.relman.code-coverage.{}.crontrigger.latest".format(
                    secrets[secrets.APP_CHANNEL]
                ),
            ]
        )


def main() -> None:
    logger.info("Starting code coverage bot for crontrigger")
    args = setup_cli(ask_revision=False, ask_repository=False)
    hook = CronTriggerHook(args.task_name_filter, None, args.working_dir)
    hook.run()

# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import structlog

from code_coverage_bot import chunk_mapping
from code_coverage_bot import config
from code_coverage_bot import uploader
from code_coverage_bot.cli import setup_cli
from code_coverage_bot.hooks.base import Hook
from code_coverage_bot.secrets import secrets
from code_coverage_bot.zero_coverage import ZeroCov

logger = structlog.get_logger(__name__)


class CronHook(Hook):
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

    def run(self):
        self.retrieve_source_and_artifacts()

        logger.info("Generating zero coverage reports")
        zc = ZeroCov(self.repo_dir)
        zc.generate(self.artifactsHandler.get(), self.revision)

        logger.info("Generating chunk mapping")
        chunk_mapping.generate(self.repo_dir, self.revision, self.artifactsHandler)

        # Index the task in the TaskCluster index at the given revision and as "latest".
        # Given that all tasks have the same rank, the latest task that finishes will
        # overwrite the "latest" entry.
        self.index_task(
            [
                "project.releng.services.project.{}.code_coverage_bot.{}".format(
                    secrets[secrets.APP_CHANNEL], self.revision
                ),
                "project.releng.services.project.{}.code_coverage_bot.latest".format(
                    secrets[secrets.APP_CHANNEL]
                ),
                "project.relman.code-coverage.{}.cron.{}".format(
                    secrets[secrets.APP_CHANNEL], self.revision
                ),
                "project.relman.code-coverage.{}.cron.latest".format(
                    secrets[secrets.APP_CHANNEL]
                ),
            ]
        )


def main():
    logger.info("Starting code coverage bot for cron")
    args = setup_cli(ask_revision=False, ask_repository=False)
    hook = CronHook(args.task_name_filter, args.cache_root)
    hook.run()

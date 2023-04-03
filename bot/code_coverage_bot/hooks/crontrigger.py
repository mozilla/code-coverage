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

logger = structlog.get_logger(__name__)


class CronTriggerHook(Hook):
    """
    This function is executed when the bot is triggered via cron.
    """

    HOOK_NAME = "crontrigger"

    def __init__(self, namespace, project, repository, *args, **kwargs):
        # Retrieve latest ingested revision
        try:
            revision = uploader.gcp_latest(project)[0]["revision"]
        except Exception as e:
            logger.warn("Failed to retrieve the latest reports ingested: {}".format(e))
            raise

        super().__init__(namespace, repository, revision, *args, **kwargs)

    def run(self) -> None:
        trigger_missing.trigger_missing(self.repository, self.namespace, self.project)

        # Index the task in the TaskCluster index at the given revision and as "latest".
        # Given that all tasks have the same rank, the latest task that finishes will
        # overwrite the "latest" entry.

        # Preserve the original path if we're using mozilla-central as the project,
        # otherwise append the project name after 'crontrigger'
        self.index_task(
            [
                "{}.{}".format(self.hook, self.revision),
                "{}.latest".format(self.hook),
            ]
        )


def main() -> None:
    logger.info("Starting code coverage bot for crontrigger")
    args = setup_cli(ask_revision=False, ask_repository=True)

    namespace = args.namespace or config.DEFAULT_NAMESPACE
    project = args.project or config.DEFAULT_PROJECT
    repository = args.repository or config.DEFAULT_REPOSITORY
    upstream = args.upstream or config.DEFAULT_UPSTREAM

    hook = CronTriggerHook(
        namespace,
        project,
        repository,
        upstream,
        args.task_name_filter,
        None,
        args.working_dir,
    )
    hook.run()

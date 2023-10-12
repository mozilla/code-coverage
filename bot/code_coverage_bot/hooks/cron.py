# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import structlog

from code_coverage_bot import commit_coverage
from code_coverage_bot import config
from code_coverage_bot import uploader
from code_coverage_bot.cli import setup_cli
from code_coverage_bot.hooks.base import Hook
from code_coverage_bot.zero_coverage import ZeroCov

logger = structlog.get_logger(__name__)


class CronHook(Hook):
    """
    This function is executed when the bot is triggered via cron.
    """

    HOOK_NAME = "cron"

    def __init__(
        self, namespace, project, repository, upstream, prefix, *args, **kwargs
    ):
        # Retrieve latest ingested revision
        try:
            revision = uploader.gcp_latest(project)[0]["revision"]
        except Exception as e:
            logger.warn("Failed to retrieve the latest reports ingested: {}".format(e))
            raise

        super().__init__(
            namespace, project, repository, upstream, revision, prefix, *args, **kwargs
        )

    def run(self) -> None:
        self.retrieve_source_and_artifacts()

        commit_coverage.generate(self.repository, self.project, self.repo_dir)

        logger.info("Generating zero coverage reports")
        zc = ZeroCov(self.repo_dir)
        zc.generate(self.artifactsHandler.get(), self.revision, prefix=self.prefix)

        # This is disabled as it is not used yet.
        # logger.info("Generating chunk mapping")
        # chunk_mapping.generate(self.repo_dir, self.revision, self.artifactsHandler)

        # Index the task in the TaskCluster index at the given revision and as "latest".
        # Given that all tasks have the same rank, the latest task that finishes will
        # overwrite the "latest" entry.
        print(self.hook)
        self.index_task(
            [
                "{}.{}".format(self.hook, self.revision),
                "{}.latest".format(self.hook),
            ]
        )


def main() -> None:
    logger.info("Starting code coverage bot for cron")
    args = setup_cli(ask_revision=False, ask_repository=True)

    namespace = args.namespace or config.DEFAULT_NAMESPACE
    project = args.project or config.DEFAULT_PROJECT
    repository = args.repository or config.DEFAULT_REPOSITORY
    upstream = args.upstream or config.DEFAULT_UPSTREAM
    prefix = args.prefix or None

    hook = CronHook(
        namespace,
        project,
        repository,
        upstream,
        prefix,
        args.task_name_filter,
        args.cache_root,
        args.working_dir,
    )
    hook.run()

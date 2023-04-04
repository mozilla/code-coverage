# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import re

import requests
import structlog
from requests import HTTPError

from code_coverage_bot import commit_coverage
from code_coverage_bot import config
from code_coverage_bot import uploader
from code_coverage_bot.cli import setup_cli
from code_coverage_bot.hooks.base import Hook
from code_coverage_bot.secrets import secrets
from code_coverage_bot.zero_coverage import ZeroCov
from code_coverage_tools import gcp

logger = structlog.get_logger(__name__)


class CronThunderbirdHook(Hook):
    """
    This cron class handles all report generation for Thunderbird's comm-central
    """

    def upload_reports(self, reports):
        """
        Upload all provided covdir reports on GCP
        """
        for (platform, suite), path in reports.items():
            report = open(path, "rb").read()
            uploader.gcp(
                self.branch, self.revision, report, suite=suite, platform=platform
            )

    def __init__(
        self, namespace, project, repository, upstream, prefix, *args, **kwargs
    ):

        tip_response = requests.get(f"{repository}/raw-rev/tip")
        # Yell if there's any issues
        try:
            tip_response.raise_for_status()
        except HTTPError as e:
            logger.error(f"Could not access raw revision for {project} tip: {e}")
            raise

        # Node ID == Revision
        revision_regex = r"^# Node ID ([\w\d]*)$"
        matches = re.search(revision_regex, tip_response.text[:2048], re.MULTILINE)

        if len(matches.groups()) == 0:
            error = "Failed to retrieve revision from tip, no match within 2048 bytes!"
            logger.error(error)
            raise Exception(error)

        # Grab that revision
        revision = matches.groups()[0]

        logger.info(f"Using revision id {revision} from tip")

        super().__init__(
            namespace, project, repository, upstream, revision, prefix, *args, **kwargs
        )

    def run(self) -> None:
        # Check the covdir report does not already exists
        bucket = gcp.get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])
        if uploader.gcp_covdir_exists(bucket, self.branch, self.revision, "all", "all"):
            logger.warn("Full covdir report already on GCP")
            return

        self.retrieve_source_and_artifacts()

        logger.info("Generating full report")
        reports = self.build_reports(only=[("all", "all")])

        # Generate all reports except the full one which we generated earlier.
        all_report_combinations = self.artifactsHandler.get_combinations()
        del all_report_combinations[("all", "all")]
        reports.update(self.build_reports())
        logger.info("Built all covdir reports", nb=len(reports))

        # Upload reports on GCP
        self.upload_reports(reports)
        logger.info("Uploaded all covdir reports", nb=len(reports))

        # Commit cov is automatically uploaded to GCP...for reasons
        logger.info("Generating commit coverage reports")
        commit_coverage.generate(self.repository, self.project, self.repo_dir)

        logger.info("Generating zero coverage reports")
        zc = ZeroCov(self.repo_dir)
        zc.generate(
            self.artifactsHandler.get(), self.revision, self.reports_dir, self.prefix
        )

        # Upload zero cov on GCP
        self.upload_reports(
            {
                (
                    "zero-coverage",
                    "zero-coverage",
                ): f"{self.reports_dir}/zero_coverage_report.json"
            }
        )
        logger.info("Uploaded zero coverage report", nb=len(reports))


def main() -> None:
    logger.info("Starting code coverage bot for cron thunderbird")
    args = setup_cli(ask_revision=False, ask_repository=True)

    namespace = args.namespace or config.DEFAULT_NAMESPACE
    project = args.project or config.DEFAULT_PROJECT
    repository = args.repository or config.DEFAULT_REPOSITORY
    upstream = args.upstream or config.DEFAULT_UPSTREAM
    prefix = args.prefix or None

    hook = CronThunderbirdHook(
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

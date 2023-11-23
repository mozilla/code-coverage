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
from code_coverage_bot import taskcluster
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

    # The last revision that we checked to see if it was usable (for fail exception use only)
    last_revision_tested = None

    def upload_reports(self, reports, zero_cov=False):
        """
        Upload all provided covdir reports on GCP
        """
        for (platform, suite), path in reports.items():
            report = open(path, "rb").read()

            if zero_cov:
                uploader.gcp_zero_coverage(report)
            else:
                uploader.gcp(
                    self.branch, self.revision, report, suite=suite, platform=platform
                )

    def has_revision_been_processed_before(self, branch, revision):
        """Returns True if the revision is in our storage bucket."""
        bucket = gcp.get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])
        return uploader.gcp_covdir_exists(bucket, branch, revision, "all", "all")

    def is_revision_usable(self, namespace, branch, revision):
        """Checks if a given revision (from branch, and namespace) is usable (tasks==completed, and exists)"""
        self.last_revision_tested = revision

        # Load coverage tasks for all platforms
        decision_task_id = taskcluster.get_decision_task(namespace, branch, revision)

        # No build!
        if decision_task_id is None:
            return False

        group = taskcluster.get_task_details(decision_task_id)["taskGroupId"]

        test_tasks = [
            task
            for task in taskcluster.get_tasks_in_group(group)
            if taskcluster.is_coverage_task(task["task"])
        ]

        if len(test_tasks) == 0:
            return False

        # Find a task that isn't pending (this includes failed tasks btw)
        for test_task in test_tasks:
            status = test_task["status"]["state"]
            if status not in taskcluster.FINISHED_STATUSES:
                return False

        return True

    def search_for_latest_built_revision(self, namespace, branch, project, repository):
        """Pulls down raw-log and goes through each changeset until we find a revision that is built (or not and return None)"""
        log_response = requests.get(f"{repository}/raw-log")

        # Yell if there's any issues
        try:
            log_response.raise_for_status()
        except HTTPError as e:
            logger.error(f"Could not access raw log for {project}: {e}")
            raise

        # Changeset == Revision
        revision_regex = r"^changeset:[\s]*([\w\d]*)$"
        matches = re.findall(revision_regex, log_response.text[:10240], re.MULTILINE)

        if len(matches) == 0:
            error = (
                "Failed to retrieve revision from raw-log, no match within 10240 bytes!"
            )
            logger.error(error)
            raise Exception(error)

        for revision in matches:
            # If we hit a revision we've processed before, we don't want to process anything past that!
            if self.has_revision_been_processed_before(branch, revision):
                break

            # Is this revision usable (has a build/artifacts, and not a pending build)
            if self.is_revision_usable(namespace, branch, revision):
                return revision

        return None

    def __init__(
        self, namespace, project, repository, upstream, prefix, *args, **kwargs
    ):
        # Assign early so we can get self.branch property working
        self.repository = repository

        revision = self.search_for_latest_built_revision(
            namespace, self.branch, project, repository
        )

        if revision is None:
            error = f"No available revision has been found, exiting! Last revision tested: {self.last_revision_tested}."
            logger.error(error)
            raise Exception(error)

        logger.info(f"Using revision id {revision} for coverage stats.")

        super().__init__(
            namespace, project, repository, upstream, revision, prefix, *args, **kwargs
        )

    def run(self) -> None:
        # Check the covdir report does not already exists
        if self.has_revision_been_processed_before(self.branch, self.revision):
            logger.warn("Full covdir report already on GCP")

            # Ping the backend to ingest any reports that may have failed
            uploader.gcp_ingest(self.branch, self.revision, "all", "all")

            return

        self.retrieve_source_and_artifacts()

        # Commit cov is automatically uploaded to GCP...for reasons
        logger.info("Generating commit coverage reports")
        commit_coverage.generate(self.repository, self.project, self.repo_dir)

        try:
            logger.info("Generating zero coverage reports")
            zc = ZeroCov(self.repo_dir)
            zc.generate(
                self.artifactsHandler.get(),
                self.revision,
                self.reports_dir,
                self.prefix,
            )

            # Upload zero cov on GCP
            self.upload_reports(
                {
                    (
                        "zero-coverage",
                        "zero-coverage",
                    ): f"{self.reports_dir}/zero_coverage_report.json"
                },
                True,
            )
            logger.info("Uploaded zero coverage report")
        except Exception as e:
            # Can occur on grcov failure
            logger.error("Zero coverage report failed: {0}".format(e))

        logger.info("Generating full report")

        reports = {}

        try:
            reports = self.build_reports(only=[("all", "all")])
        except Exception as e:
            # Can occur on grcov failure
            logger.error("All covdir coverage report failed: {0}".format(e))

        try:
            # Generate all reports except the full one which we generated earlier.
            all_report_combinations = self.artifactsHandler.get_combinations()
            del all_report_combinations[("all", "all")]

            reports.update(self.build_reports())
            logger.info("Built all covdir reports", nb=len(reports))
        except Exception as e:
            # Can occur on grcov failure
            logger.error("Covdir coverage report failed: {0}".format(e))

        if len(reports) == 0:
            logger.warning("No reports to upload...")
            return

        # Upload reports on GCP
        self.upload_reports(reports)
        logger.info("Uploaded all covdir reports", nb=len(reports))


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

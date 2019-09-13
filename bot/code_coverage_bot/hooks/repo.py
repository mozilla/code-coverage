# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import os
import zipfile

import structlog

from code_coverage_bot import config
from code_coverage_bot import hgmo
from code_coverage_bot import uploader
from code_coverage_bot.cli import setup_cli
from code_coverage_bot.hooks.base import Hook
from code_coverage_bot.notifier import notify_email
from code_coverage_bot.phabricator import PhabricatorUploader
from code_coverage_bot.phabricator import parse_revision_id

logger = structlog.get_logger(__name__)


class RepositoryHook(Hook):
    """
    Base class to support specific workflows per repository
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

    def check_javascript_files(self):
        """
        Check that all JavaScript files present in the coverage artifacts actually exist.
        If they don't, there might be a bug in the LCOV rewriter.
        """
        for artifact in self.artifactsHandler.get():
            if "jsvm" not in artifact:
                continue

            with zipfile.ZipFile(artifact, "r") as zf:
                for file_name in zf.namelist():
                    with zf.open(file_name, "r") as fl:
                        source_files = [
                            line[3:].decode("utf-8").rstrip()
                            for line in fl
                            if line.startswith(b"SF:")
                        ]
                        missing_files = [
                            f
                            for f in source_files
                            if not os.path.exists(os.path.join(self.repo_dir, f))
                        ]
                        if len(missing_files) != 0:
                            logger.warn(
                                f"{missing_files} are present in coverage reports, but missing from the repository"
                            )

    def upload_phabricator(self, report, use_local_clone=True):
        phabricatorUploader = PhabricatorUploader(self.repo_dir, self.revision)

        # Build HGMO config according to this repo's configuration
        hgmo_config = {}
        if use_local_clone:
            hgmo_config["repo_dir"] = self.repo_dir
        else:
            hgmo_config["server_address"] = self.repository

        with hgmo.HGMO(**hgmo_config) as hgmo_server:
            changesets = hgmo_server.get_automation_relevance_changesets(self.revision)

        if not any(
            parse_revision_id(changeset["desc"]) is not None for changeset in changesets
        ):
            logger.info(
                "None of the commits in the try push are linked to a Phabricator revision"
            )
            return

        logger.info("Upload changeset coverage data to Phabricator")
        coverage = phabricatorUploader.upload(report, changesets)

        return changesets, coverage


class MozillaCentralHook(RepositoryHook):
    """
    Code coverage hook for mozilla-central
    * Check coverage artifacts content
    * Build all covdir reports possible
    * Upload all reports on GCP
    * Upload main reports on Phabrictaor
    * Send an email to admins on low coverage
    """

    def __init__(self, *args, **kwargs):
        super().__init__(
            config.MOZILLA_CENTRAL_REPOSITORY,
            # On mozilla-central, we want to assert that every platform was run (except for android platforms
            # as they are unstable).
            required_platforms=["linux", "windows"],
            *args,
            **kwargs,
        )

    def run(self):
        # Check the covdir report does not already exists
        if uploader.gcp_covdir_exists(self.branch, self.revision, "all", "all"):
            logger.warn("Full covdir report already on GCP")
            return

        self.retrieve_source_and_artifacts()

        self.check_javascript_files()

        reports = self.build_reports()
        logger.info("Built all covdir reports", nb=len(reports))

        # Retrieve the full report
        full_path = reports.get(("all", "all"))
        assert full_path is not None, "Missing full report (all:all)"
        report = json.load(open(full_path))

        # Check extensions
        paths = uploader.covdir_paths(report)
        for extension in [".js", ".cpp"]:
            assert any(
                path.endswith(extension) for path in paths
            ), "No {} file in the generated report".format(extension)

        # Upload reports on GCP
        self.upload_reports(reports)
        logger.info("Uploaded all covdir reports", nb=len(reports))

        # Upload coverage on phabricator
        changesets, coverage = self.upload_phabricator(report)

        # Send an email on low coverage
        notify_email(self.revision, changesets, coverage)
        logger.info("Sent low coverage email notification")


class TryHook(RepositoryHook):
    """
    Code coverage hook for a try push
    * Build only main covdir report
    * Upload that report on Phabrictaor
    """

    def __init__(self, *args, **kwargs):
        super().__init__(
            config.TRY_REPOSITORY,
            # On try, developers might have requested to run only one platform, and we trust them.
            required_platforms=[],
            *args,
            **kwargs,
        )

    def run(self):
        self.retrieve_source_and_artifacts()

        reports = self.build_reports(only=[("all", "all")])
        logger.info("Built all covdir reports", nb=len(reports))

        # Retrieve the full report
        full_path = reports.get(("all", "all"))
        assert full_path is not None, "Missing full report (all:all)"
        report = json.load(open(full_path))

        # Upload coverage on phabricator
        self.upload_phabricator(report, use_local_clone=False)


def main():
    logger.info("Starting code coverage bot for repository")
    args = setup_cli()

    hooks = {
        config.MOZILLA_CENTRAL_REPOSITORY: MozillaCentralHook,
        config.TRY_REPOSITORY: TryHook,
    }
    hook_class = hooks.get(args.repository)
    assert hook_class is not None, f"Unsupported repository {args.repository}"

    hook = hook_class(args.revision, args.task_name_filter, args.cache_root)
    hook.run()

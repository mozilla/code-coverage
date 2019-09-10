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
from code_coverage_bot.hooks.base import Hook
from code_coverage_bot.notifier import notify_email
from code_coverage_bot.phabricator import PhabricatorUploader

logger = structlog.get_logger(__name__)


class MozillaCentralHook(Hook):
    """
    This function is executed when the bot is triggered at the end of a mozilla-central build.
    """

    repository = config.MOZILLA_CENTRAL_REPOSITORY

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

        paths = uploader.covdir_paths(report)
        expected_extensions = [".js", ".cpp"]
        for extension in expected_extensions:
            assert any(
                path.endswith(extension) for path in paths
            ), "No {} file in the generated report".format(extension)

        self.upload_reports(reports)
        logger.info("Uploaded all covdir reports", nb=len(reports))

        # Get pushlog and ask the backend to generate the coverage by changeset
        # data, which will be cached.
        with hgmo.HGMO(self.repo_dir) as hgmo_server:
            changesets = hgmo_server.get_automation_relevance_changesets(self.revision)

        logger.info("Upload changeset coverage data to Phabricator")
        phabricatorUploader = PhabricatorUploader(self.repo_dir, self.revision)
        changesets_coverage = phabricatorUploader.upload(report, changesets)

        notify_email(self.revision, changesets, changesets_coverage)

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

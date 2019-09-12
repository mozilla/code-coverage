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


REPOSITORIES = {
    config.MOZILLA_CENTRAL_REPOSITORY: {
        # Will build all the reports possible
        "build_reports": None,
        "gcp_upload": True,
        "send_low_coverage_email": True,
        "expected_extensions": [".js", ".cpp"],
        # Use local repo to load mercurial information
        "hgmo_local": True,
        # On mozilla-central, we want to assert that every platform was run (except for android platforms
        # as they are unstable).
        "required_platforms": ["linux", "windows"],
    },
    config.TRY_REPOSITORY: {
        # Only build the main report
        "build_reports": [("all", "all")],
        "gcp_upload": False,
        "send_low_coverage_email": False,
        "expected_extensions": None,
        # Use remote try repo in order to return early if the
        # try build is not linked to Phabricator
        "hgmo_local": False,
        # On try, developers might have requested to run only one platform, and we trust them.
        "required_platforms": [],
    },
}


class RepositoryHook(Hook):
    """
    This function is executed when the bot is triggered at the end of a build and associated tests.
    """

    def __init__(self, repository, *args, **kwargs):
        assert repository in REPOSITORIES, f"Unsupported repository {repository}"
        self.config = REPOSITORIES[repository]

        for key in (
            "build_reports",
            "gcp_upload",
            "send_low_coverage_email",
            "expected_extensions",
            "hgmo_local",
            "required_platforms",
        ):
            assert key in self.config, f"Missing {key} in {repository} config"

        super().__init__(
            repository,
            required_platforms=self.config["required_platforms"],
            *args,
            **kwargs,
        )

    def run(self):
        # Check the covdir report does not already exists
        if self.config["gcp_upload"] and uploader.gcp_covdir_exists(
            self.branch, self.revision, "all", "all"
        ):
            logger.warn("Full covdir report already on GCP")
            return

        self.retrieve_source_and_artifacts()

        self.check_javascript_files()

        reports = self.build_reports(only=self.config["build_reports"])
        logger.info("Built all covdir reports", nb=len(reports))

        # Retrieve the full report
        full_path = reports.get(("all", "all"))
        assert full_path is not None, "Missing full report (all:all)"
        report = json.load(open(full_path))

        # Check extensions
        if self.config["expected_extensions"]:
            paths = uploader.covdir_paths(report)
            for extension in self.config["expected_extensions"]:
                assert any(
                    path.endswith(extension) for path in paths
                ), "No {} file in the generated report".format(extension)

        # Upload reports on GCP
        if self.config["gcp_upload"]:
            self.upload_reports(reports)
            logger.info("Uploaded all covdir reports", nb=len(reports))
        else:
            logger.info("Skipping GCP upload")

        # Upload coverage on phabricator
        changesets, coverage = self.upload_phabricator(report)

        # Send an email on low coverage
        if self.config["send_low_coverage_email"]:
            notify_email(self.revision, changesets, coverage)
            logger.info("Sent low coverage email notification")
        else:
            logger.info("Skipping low coverage email notification")

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

    def upload_phabricator(self, report):
        phabricatorUploader = PhabricatorUploader(self.repo_dir, self.revision)

        # Build HGMO config according to this repo's configuration
        hgmo_config = {}
        if self.config["hgmo_local"]:
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


def main():
    logger.info("Starting code coverage bot for repository")
    args = setup_cli()
    hook = RepositoryHook(
        args.repository, args.revision, args.task_name_filter, args.cache_root
    )
    hook.run()

# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json

import structlog

from code_coverage_bot import config
from code_coverage_bot import hgmo
from code_coverage_bot.hooks.base import Hook
from code_coverage_bot.phabricator import PhabricatorUploader
from code_coverage_bot.phabricator import parse_revision_id

logger = structlog.get_logger(__name__)


class TryHook(Hook):
    """
    This function is executed when the bot is triggered at the end of a try build.
    """

    repository = config.TRY_REPOSITORY

    def run(self):
        phabricatorUploader = PhabricatorUploader(self.repo_dir, self.revision)

        with hgmo.HGMO(server_address=config.TRY_REPOSITORY) as hgmo_server:
            changesets = hgmo_server.get_automation_relevance_changesets(self.revision)

        if not any(
            parse_revision_id(changeset["desc"]) is not None for changeset in changesets
        ):
            logger.info(
                "None of the commits in the try push are linked to a Phabricator revision"
            )
            return

        self.retrieve_source_and_artifacts()

        reports = self.build_reports(only=[("all", "all")])
        full_path = reports.get(("all", "all"))
        assert full_path is not None, "Missing full report (all:all)"
        report = json.load(open(full_path))

        logger.info("Upload changeset coverage data to Phabricator")
        phabricatorUploader.upload(report, changesets)

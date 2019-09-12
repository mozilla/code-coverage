# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import tempfile

import hglib
import structlog

from code_coverage_bot import config
from code_coverage_bot import grcov
from code_coverage_bot import taskcluster
from code_coverage_bot.artifacts import ArtifactsHandler
from code_coverage_bot.utils import ThreadPoolExecutorResult

logger = structlog.get_logger(__name__)


PLATFORMS = ["linux", "windows", "android-test", "android-emulator"]


class Hook(object):
    def __init__(
        self,
        repository,
        revision,
        task_name_filter,
        cache_root,
        fail,
        required_platforms=[],
    ):
        temp_dir = tempfile.mkdtemp()
        self.artifacts_dir = os.path.join(temp_dir, "ccov-artifacts")
        self.reports_dir = os.path.join(temp_dir, "ccov-reports")

        self.repository = repository
        self.revision = revision
        assert (
            self.revision is not None and self.repository is not None
        ), "Missing repo/revision"
        logger.info(
            "Mercurial setup", repository=self.repository, revision=self.revision
        )

        assert os.path.isdir(cache_root), f"Cache root {cache_root} is not a dir."
        self.repo_dir = os.path.join(cache_root, self.branch)

        # Load current coverage task for all platforms
        task_ids = {
            platform: taskcluster.get_task(self.branch, self.revision, platform)
            for platform in PLATFORMS
        }

        # Check the required platforms are present
        for platform in required_platforms:
            if not task_ids[platform]:
                raise Exception(
                    f"Code coverage build on {platform} failed and was not indexed."
                )

        self.artifactsHandler = ArtifactsHandler(
            task_ids, self.artifacts_dir, task_name_filter
        )

    @property
    def branch(self):
        return self.repository[len(config.HG_BASE) :]

    def clone_repository(self):
        cmd = hglib.util.cmdbuilder(
            "robustcheckout",
            self.repository,
            self.repo_dir,
            purge=True,
            sharebase="hg-shared",
            upstream="https://hg.mozilla.org/mozilla-unified",
            revision=self.revision,
            networkattempts=7,
        )

        cmd.insert(0, hglib.HGPATH)

        proc = hglib.util.popen(cmd)
        out, err = proc.communicate()
        if proc.returncode:
            raise hglib.error.CommandError(cmd, proc.returncode, out, err)

        logger.info("{} cloned".format(self.repository))

    def retrieve_source_and_artifacts(self):
        with ThreadPoolExecutorResult(max_workers=2) as executor:
            # Thread 1 - Download coverage artifacts.
            executor.submit(self.artifactsHandler.download_all)

            # Thread 2 - Clone repository.
            executor.submit(self.clone_repository)

    def build_reports(self, only=None):
        """
        Build all the possible covdir reports using current artifacts
        """
        os.makedirs(self.reports_dir, exist_ok=True)

        reports = {}
        for (
            (platform, suite),
            artifacts,
        ) in self.artifactsHandler.get_combinations().items():

            if only is not None and (platform, suite) not in only:
                continue

            # Generate covdir report for that suite & platform
            logger.info(
                "Building covdir suite report",
                suite=suite,
                platform=platform,
                artifacts=len(artifacts),
            )
            output = grcov.report(
                artifacts, source_dir=self.repo_dir, out_format="covdir"
            )

            # Write output on FS
            path = os.path.join(self.reports_dir, f"{platform}.{suite}.json")
            with open(path, "wb") as f:
                f.write(output)

            reports[(platform, suite)] = path

        return reports

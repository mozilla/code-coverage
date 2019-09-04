# -*- coding: utf-8 -*-

import json
import os
import tempfile
import zipfile
from datetime import datetime
from datetime import timedelta

import hglib
import structlog

from code_coverage_bot import chunk_mapping
from code_coverage_bot import grcov
from code_coverage_bot import hgmo
from code_coverage_bot import taskcluster
from code_coverage_bot import uploader
from code_coverage_bot.artifacts import ArtifactsHandler
from code_coverage_bot.notifier import notify_email
from code_coverage_bot.phabricator import PhabricatorUploader
from code_coverage_bot.phabricator import parse_revision_id
from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config
from code_coverage_bot.utils import ThreadPoolExecutorResult
from code_coverage_bot.zero_coverage import ZeroCov

logger = structlog.get_logger(__name__)


HG_BASE = "https://hg.mozilla.org/"
MOZILLA_CENTRAL_REPOSITORY = "{}mozilla-central".format(HG_BASE)
TRY_REPOSITORY = "{}try".format(HG_BASE)


class CodeCov(object):
    def __init__(self, repository, revision, task_name_filter, cache_root):
        # List of test-suite, sorted alphabetically.
        # This way, the index of a suite in the array should be stable enough.
        self.suites = ["web-platform-tests"]

        self.cache_root = cache_root

        temp_dir = tempfile.mkdtemp()
        self.artifacts_dir = os.path.join(temp_dir, "ccov-artifacts")
        self.reports_dir = os.path.join(temp_dir, "ccov-reports")

        self.index_service = taskcluster_config.get_service("index")

        if revision is None:
            # Retrieve latest ingested revision
            self.repository = MOZILLA_CENTRAL_REPOSITORY
            try:
                self.revision = uploader.gcp_latest("mozilla-central")[0]["revision"]
            except Exception as e:
                logger.warn(
                    "Failed to retrieve the latest reports ingested: {}".format(e)
                )
                raise
            self.from_pulse = False
        else:
            self.repository = repository
            self.revision = revision
            self.from_pulse = True

        self.branch = self.repository[len(HG_BASE) :]

        assert os.path.isdir(cache_root), "Cache root {} is not a dir.".format(
            cache_root
        )
        self.repo_dir = os.path.join(cache_root, self.branch)

        logger.info("Mercurial revision", revision=self.revision)

        task_ids = {}
        for platform in ["linux", "windows", "android-test", "android-emulator"]:
            task = taskcluster.get_task(self.branch, self.revision, platform)

            # On try, developers might have requested to run only one platform, and we trust them.
            # On mozilla-central, we want to assert that every platform was run (except for android platforms
            # as they are unstable).
            if task is not None:
                task_ids[platform] = task
            elif (
                self.repository == MOZILLA_CENTRAL_REPOSITORY
                and not platform.startswith("android")
            ):
                raise Exception("Code coverage build failed and was not indexed.")

        self.artifactsHandler = ArtifactsHandler(
            task_ids, self.artifacts_dir, task_name_filter
        )

    def clone_repository(self, repository, revision):
        cmd = hglib.util.cmdbuilder(
            "robustcheckout",
            repository,
            self.repo_dir,
            purge=True,
            sharebase="hg-shared",
            upstream="https://hg.mozilla.org/mozilla-unified",
            revision=revision,
            networkattempts=7,
        )

        cmd.insert(0, hglib.HGPATH)

        proc = hglib.util.popen(cmd)
        out, err = proc.communicate()
        if proc.returncode:
            raise hglib.error.CommandError(cmd, proc.returncode, out, err)

        logger.info("{} cloned".format(repository))

    def retrieve_source_and_artifacts(self):
        with ThreadPoolExecutorResult(max_workers=2) as executor:
            # Thread 1 - Download coverage artifacts.
            executor.submit(self.artifactsHandler.download_all)

            # Thread 2 - Clone repository.
            executor.submit(self.clone_repository, self.repository, self.revision)

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

    # This function is executed when the bot is triggered at the end of a mozilla-central build.
    def go_from_trigger_mozilla_central(self):
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

    # This function is executed when the bot is triggered at the end of a try build.
    def go_from_trigger_try(self):
        phabricatorUploader = PhabricatorUploader(self.repo_dir, self.revision)

        with hgmo.HGMO(server_address=TRY_REPOSITORY) as hgmo_server:
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

    # This function is executed when the bot is triggered via cron.
    def go_from_cron(self):
        self.retrieve_source_and_artifacts()

        logger.info("Generating zero coverage reports")
        zc = ZeroCov(self.repo_dir)
        zc.generate(self.artifactsHandler.get(), self.revision)

        logger.info("Generating chunk mapping")
        chunk_mapping.generate(self.repo_dir, self.revision, self.artifactsHandler)

        # Index the task in the TaskCluster index at the given revision and as "latest".
        # Given that all tasks have the same rank, the latest task that finishes will
        # overwrite the "latest" entry.
        namespaces = [
            "project.releng.services.project.{}.code_coverage_bot.{}".format(
                secrets[secrets.APP_CHANNEL], self.revision
            ),
            "project.releng.services.project.{}.code_coverage_bot.latest".format(
                secrets[secrets.APP_CHANNEL]
            ),
        ]

        for namespace in namespaces:
            self.index_service.insertTask(
                namespace,
                {
                    "taskId": os.environ["TASK_ID"],
                    "rank": 0,
                    "data": {},
                    "expires": (datetime.utcnow() + timedelta(180)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                },
            )

    def go(self):
        if not self.from_pulse:
            self.go_from_cron()
        elif self.repository == TRY_REPOSITORY:
            self.go_from_trigger_try()
        elif self.repository == MOZILLA_CENTRAL_REPOSITORY:
            self.go_from_trigger_mozilla_central()
        else:
            assert False, "We shouldn't be here!"

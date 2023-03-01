# -*- coding: utf-8 -*-
import calendar
import math
import os
import tempfile
from datetime import datetime
from typing import List
from typing import Optional

import redis
import structlog
from dateutil.relativedelta import relativedelta

from code_coverage_backend import covdir
from code_coverage_backend import taskcluster
from code_coverage_backend.hgmo import hgmo_pushes
from code_coverage_backend.hgmo import hgmo_revision_details
from code_coverage_backend.report import DEFAULT_FILTER
from code_coverage_backend.report import Report
from code_coverage_tools.gcp import download_report
from code_coverage_tools.gcp import get_bucket
from code_coverage_tools.gcp import list_reports

logger = structlog.get_logger(__name__)
__cache = None

KEY_REPORTS = "reports:{repository}:{platform}:{suite}"
KEY_CHANGESET = "changeset:{repository}:{changeset}"
KEY_HISTORY = "history:{repository}"
KEY_PLATFORMS = "platforms:{repository}"
KEY_SUITES = "suites:{repository}"

REPOSITORIES = ("mozilla-central",)

MIN_PUSH = 0
MAX_PUSH = math.inf


def load_cache():
    """
    Manage singleton instance of GCPCache when configuration is available
    """
    global __cache

    if taskcluster.secrets["GOOGLE_CLOUD_STORAGE"] is None:
        return

    if __cache is None:
        __cache = GCPCache()

    return __cache


class GCPCache(object):
    """
    Cache on Redis GCP results
    """

    def __init__(self, reports_dir=None):
        # Open redis connection
        redis_url = taskcluster.secrets["REDIS_URL"]
        # Are we dealing with a redis ssl/tls connection?
        if redis_url.startswith("rediss:"):
            # The cert is self signed so do not check it
            self.redis = redis.from_url(redis_url, ssl_cert_reqs="none")
        else:
            # No we are not, we are connecting transparently
            self.redis = redis.from_url(redis_url)
        assert self.redis.ping(), "Redis server does not ping back"

        # Open gcp connection to bucket
        assert (
            taskcluster.secrets["GOOGLE_CLOUD_STORAGE"] is not None
        ), "Missing GOOGLE_CLOUD_STORAGE secret"
        self.bucket = get_bucket(taskcluster.secrets["GOOGLE_CLOUD_STORAGE"])

        # Local storage for reports
        self.reports_dir = reports_dir or os.path.join(
            tempfile.gettempdir(), "ccov-reports"
        )
        os.makedirs(self.reports_dir, exist_ok=True)
        logger.info("Reports will be stored in {}".format(self.reports_dir))

        # Load most recent reports in cache
        for repo in REPOSITORIES:
            for report in self.list_reports(repo, nb=1):
                download_report(self.reports_dir, self.bucket, report.name)

    def ingest_pushes(self, repository, platform, suite, min_push_id=None, nb_pages=3):
        """
        Ingest HGMO changesets and pushes into our Redis Cache
        The pagination goes from oldest to newest, starting from the optional min_push_id
        """
        ingested = False
        for push_id, push in hgmo_pushes(repository, min_push_id, nb_pages):
            for changeset in push["changesets"]:
                report = Report(
                    self.reports_dir,
                    repository,
                    changeset,
                    platform,
                    suite,
                    push_id=push_id,
                    date=push["date"],
                )

                # Always link changeset to push to find closest available report
                self.redis.hmset(
                    KEY_CHANGESET.format(
                        repository=report.repository, changeset=report.changeset
                    ),
                    {"push": report.push_id, "date": report.date},
                )

                if not ingested and self.ingest_report(report):
                    logger.info(
                        "Found report in that push", push_id=push_id, report=str(report)
                    )

                    # Only ingest first report found in a push in order to stay below 30s response time
                    ingested = True

    def ingest_report(self, report: Report) -> bool:
        """
        When a report exist for a changeset, download it and update redis data
        """
        # Download the report
        if not download_report(self.reports_dir, self.bucket, report.name):
            logger.info("Report not available", report=str(report))
            return False

        # Read overall coverage for history
        data = covdir.open_report(report.path)
        assert data is not None, "No report to ingest"
        overall_coverage = covdir.get_overall_coverage(data)
        assert len(overall_coverage) > 0, "No overall coverage"
        self.redis.hmset(report.key_overall, overall_coverage)

        # Apply expiry for overall report
        if report.ttl is not None:
            self.redis.expire(report.key_overall, report.ttl)

        # Add the changeset to the sorted sets of known reports
        # The numeric push_id is used as a score to keep the ingested
        # changesets ordered
        self.redis.zadd(
            KEY_REPORTS.format(
                repository=report.repository,
                platform=report.platform,
                suite=report.suite,
            ),
            {report.changeset: report.push_id},
        )

        # Add the changeset to the sorted sets of known reports by date
        self.redis.zadd(
            KEY_HISTORY.format(repository=report.repository),
            {report.changeset: report.date},
        )

        # Store the filters
        if report.platform != DEFAULT_FILTER:
            self.redis.sadd(
                KEY_PLATFORMS.format(repository=report.repository), report.platform
            )
        if report.suite != DEFAULT_FILTER:
            self.redis.sadd(
                KEY_SUITES.format(repository=report.repository), report.suite
            )

        logger.info("Ingested report", report=str(report))
        return True

    def find_report(
        self,
        repository,
        platform=DEFAULT_FILTER,
        suite=DEFAULT_FILTER,
        push_range=(MAX_PUSH, MIN_PUSH),
    ):
        """
        Find the first report available before that push
        """
        results = self.list_reports(
            repository, platform, suite, nb=1, push_range=push_range
        )
        if not results:
            raise Exception("No report found")
        return results[0]

    def find_closest_report(
        self, repository, changeset, platform=DEFAULT_FILTER, suite=DEFAULT_FILTER
    ):
        """
        Find the closest report from specified changeset:
        1. Lookup the changeset push in cache
        2. Lookup the changeset push in HGMO
        3. Find the first report after that push
        """

        # Lookup push from cache (fast)
        key = KEY_CHANGESET.format(repository=repository, changeset=changeset)
        push_id = self.redis.hget(key, "push")
        if push_id:
            # Redis lib uses bytes for all output
            push_id = int(push_id.decode("utf-8"))
            date = self.redis.hget(key, "date").decode("utf-8")

            # Check the report variant is available locally
            report = Report(
                self.reports_dir,
                repository,
                changeset,
                platform,
                suite,
                push_id=push_id,
                date=date,
            )
            if not os.path.exists(report.path):
                self.ingest_report(report)
        else:

            # Lookup push from HGMO (slow)
            push_id, _ = hgmo_revision_details(repository, changeset)

            # Ingest pushes as we clearly don't have it in cache
            self.ingest_pushes(
                repository, platform, suite, min_push_id=push_id - 1, nb_pages=1
            )

        # Load report from that push
        return self.find_report(
            repository, platform, suite, push_range=(push_id, MAX_PUSH)
        )

    def list_reports(
        self,
        repository,
        platform=DEFAULT_FILTER,
        suite=DEFAULT_FILTER,
        nb=5,
        push_range=(MAX_PUSH, MIN_PUSH),
    ):
        """
        List the last reports available on the server, ordered by push
        by default from newer to older
        The order is detected from the push range
        """
        assert isinstance(nb, int)
        assert nb > 0
        assert isinstance(push_range, tuple) and len(push_range) == 2

        # Detect ordering from push range
        start, end = push_range
        op = self.redis.zrangebyscore if start < end else self.redis.zrevrangebyscore

        reports = op(
            KEY_REPORTS.format(repository=repository, platform=platform, suite=suite),
            start,
            end,
            start=0,
            num=nb,
            withscores=True,
        )

        return [
            Report(
                self.reports_dir,
                repository,
                changeset.decode("utf-8"),
                platform,
                suite,
                push_id=push,
            )
            for changeset, push in reports
        ]

    def get_coverage(self, report: Report, path: str) -> dict:
        """
        Load a report and its coverage for a specific path
        and build a serializable representation
        """
        data = covdir.open_report(report.path)
        if data is None:
            # Try to download the report if it's missing locally
            assert download_report(
                self.reports_dir, self.bucket, report.name
            ), "Missing report {}".format(report)

            data = covdir.open_report(report.path)
            assert data

        out = covdir.get_path_coverage(data, path)
        out["changeset"] = report.changeset
        return out

    def get_history(
        self,
        repository,
        path="",
        start=None,
        end=None,
        platform=DEFAULT_FILTER,
        suite=DEFAULT_FILTER,
    ):
        """
        Load the history overall coverage from the redis cache
        Default to date range from now back to a year
        """
        if end is None:
            end = calendar.timegm(datetime.utcnow().timetuple())
        if start is None:
            start = datetime.fromtimestamp(end) - relativedelta(years=1)
            start = int(datetime.timestamp(start))
        assert isinstance(start, int)
        assert isinstance(end, int)
        assert end > start, f"Bad timestamps: {start} should come before {end}"

        # Load changesets ordered by date, in that range
        history = self.redis.zrevrangebyscore(
            KEY_HISTORY.format(repository=repository), end, start, withscores=True
        )

        def _coverage(changeset, date):
            # Load overall coverage for specified path
            changeset = changeset.decode("utf-8")

            report = Report(
                self.reports_dir, repository, changeset, platform, suite, date=date
            )
            coverage = self.redis.hget(report.key_overall, path)
            if coverage is not None:
                coverage = float(coverage)
            return {"changeset": changeset, "date": int(date), "coverage": coverage}

        return [_coverage(changeset, date) for changeset, date in history]

    def get_platforms(self, repository: str) -> List[str]:
        """List all available platforms for a repository"""
        platforms = self.redis.smembers(KEY_PLATFORMS.format(repository=repository))
        return sorted(map(lambda x: x.decode("utf-8"), platforms))

    def get_suites(self, repository: str) -> List[str]:
        """List all available suites for a repository"""
        suites = self.redis.smembers(KEY_SUITES.format(repository=repository))
        return sorted(map(lambda x: x.decode("utf-8"), suites))

    def ingest_available_reports(
        self, repository: str, until: Optional[datetime] = None
    ) -> None:
        """
        Ingest all the available reports for a repository
        """
        assert isinstance(repository, str)

        for changeset, platform, suite in list_reports(self.bucket, repository, until):
            # Build report instance and ingest it
            report = Report(self.reports_dir, repository, changeset, platform, suite)
            self.ingest_report(report)

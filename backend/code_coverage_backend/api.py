# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import structlog
from flask import abort

from code_coverage_backend.config import COVERAGE_EXTENSIONS
from code_coverage_backend.gcp import load_cache
from code_coverage_backend.report import DEFAULT_FILTER

DEFAULT_REPOSITORY = "mozilla-central"
logger = structlog.get_logger(__name__)


def coverage_supported_extensions():
    """
    List all the file extensions we currently support
    """
    return COVERAGE_EXTENSIONS


def coverage_latest(repository=DEFAULT_REPOSITORY):
    """
    List the last 10 reports available on the server
    """
    gcp = load_cache()
    if gcp is None:
        logger.error("No GCP cache available")
        abort(500)

    try:
        return [
            {"revision": revision, "push": push_id}
            for revision, push_id in gcp.list_reports(repository, 10)
        ]
    except Exception as e:
        logger.warn("Failed to retrieve latest reports: {}".format(e))
        abort(404)


def coverage_for_path(
    path="",
    changeset=None,
    repository=DEFAULT_REPOSITORY,
    platform=DEFAULT_FILTER,
    suite=DEFAULT_FILTER,
):
    """
    Aggregate coverage for a path, regardless of its type:
    * file, gives its coverage percent
    * directory, gives coverage percent for its direct sub elements
      files and folders (recursive average)
    """
    gcp = load_cache()
    if gcp is None:
        logger.error("No GCP cache available")
        abort(500)

    try:
        if changeset:
            # Find closest report matching this changeset
            report = gcp.find_closest_report(repository, changeset, platform, suite)
        else:
            # Fallback to latest report
            report = gcp.find_report(repository, platform, suite)
    except Exception as e:
        logger.warn("Failed to retrieve report: {}".format(e))
        abort(404)

    # Load tests data from GCP
    try:
        return gcp.get_coverage(report, path)
    except Exception as e:
        logger.warn(
            "Failed to load coverage",
            repo=repository,
            changeset=changeset,
            path=path,
            error=str(e),
        )
        abort(400)


def coverage_history(
    repository=DEFAULT_REPOSITORY,
    path="",
    start=None,
    end=None,
    platform=DEFAULT_FILTER,
    suite=DEFAULT_FILTER,
):
    """
    List overall coverage from ingested reports over a period of time
    """
    gcp = load_cache()
    if gcp is None:
        logger.error("No GCP cache available")
        abort(500)

    try:
        return gcp.get_history(repository, path, start, end, platform, suite)
    except Exception as e:
        logger.warn(
            "Failed to load history",
            repo=repository,
            path=path,
            start=start,
            end=end,
            error=str(e),
        )
        abort(400)


def coverage_filters(repository=DEFAULT_REPOSITORY):
    """
    List all available filters for that repository
    """
    gcp = load_cache()
    if gcp is None:
        logger.error("No GCP cache available")
        abort(500)

    try:
        return {
            "platforms": gcp.get_platforms(repository),
            "suites": gcp.get_suites(repository),
        }
    except Exception as e:
        logger.warn("Failed to load filters", repo=repository, error=str(e))
        abort(400)

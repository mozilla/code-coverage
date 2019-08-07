# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os.path

import structlog

import code_coverage_backend.datadog
import code_coverage_backend.gcp
from code_coverage_backend import taskcluster
from code_coverage_tools.log import init_logger

from .build import build_flask_app


def create_app():
    # Load secrets from Taskcluster
    taskcluster.auth()
    taskcluster.load_secrets(
        os.environ.get("TASKCLUSTER_SECRET"),
        code_coverage_backend.config.PROJECT_NAME,
        required=["GOOGLE_CLOUD_STORAGE", "APP_CHANNEL"],
        existing={"REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379")},
    )

    # Configure logger
    init_logger(
        code_coverage_backend.config.PROJECT_NAME,
        PAPERTRAIL_HOST=taskcluster.secrets.get("PAPERTRAIL_HOST"),
        PAPERTRAIL_PORT=taskcluster.secrets.get("PAPERTRAIL_PORT"),
        sentry_dsn=taskcluster.secrets.get("SENTRY_DSN"),
    )
    logger = structlog.get_logger(__name__)

    app = build_flask_app(
        project_name=code_coverage_backend.config.PROJECT_NAME,
        app_name=code_coverage_backend.config.APP_NAME,
        openapi=os.path.join(os.path.dirname(__file__), "../api.yml"),
    )

    # Setup datadog stats
    code_coverage_backend.datadog.get_stats()

    # Warm up GCP cache
    try:
        code_coverage_backend.gcp.load_cache()
    except Exception as e:
        logger.warn("GCP cache warmup failed: {}".format(e))

    return app

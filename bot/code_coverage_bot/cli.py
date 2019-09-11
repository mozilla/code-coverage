# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os

from code_coverage_bot import config
from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config
from code_coverage_tools.log import init_logger


def setup_cli(ask_repository=True, ask_revision=True):
    """
    Setup CLI options parser and taskcluster bootstrap
    """
    parser = argparse.ArgumentParser(description="Mozilla Code Coverage Bot")
    if ask_repository:
        parser.add_argument("--repository", default=os.environ.get("REPOSITORY"))
    if ask_revision:
        parser.add_argument("--revision", default=os.environ.get("REVISION"))
    parser.add_argument(
        "--cache-root", required=True, help="Cache root, used to pull changesets"
    )
    parser.add_argument(
        "--task-name-filter",
        default="*",
        help="Filter Taskcluster tasks using a glob expression",
    )
    parser.add_argument(
        "--taskcluster-secret",
        help="Taskcluster Secret path",
        default=os.environ.get("TASKCLUSTER_SECRET"),
    )
    parser.add_argument("--taskcluster-client-id", help="Taskcluster Client ID")
    parser.add_argument("--taskcluster-access-token", help="Taskcluster Access token")
    args = parser.parse_args()

    # Auth on Taskcluster
    taskcluster_config.auth(args.taskcluster_client_id, args.taskcluster_access_token)

    # Then load secrets
    secrets.load(args.taskcluster_secret)

    init_logger(
        config.PROJECT_NAME,
        channel=secrets.get("APP_CHANNEL", "dev"),
        PAPERTRAIL_HOST=secrets.get("PAPERTRAIL_HOST"),
        PAPERTRAIL_PORT=secrets.get("PAPERTRAIL_PORT"),
        sentry_dsn=secrets.get("SENTRY_DSN"),
    )

    return args

# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os

import structlog

from code_coverage_bot import config
from code_coverage_bot.hooks.cron import CronHook
from code_coverage_bot.hooks.mc import MozillaCentralHook
from code_coverage_bot.hooks.try_repo import TryHook
from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config
from code_coverage_tools.log import init_logger


def parse_cli():
    """
    Setup CLI options parser
    """
    parser = argparse.ArgumentParser(description="Mozilla Code Coverage Bot")
    parser.add_argument("--repository", default=os.environ.get("REPOSITORY"))
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
    return parser.parse_args()


def main():
    args = parse_cli()

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

    logger = structlog.get_logger(__name__)

    if args.revision is None:
        logger.info("Running cron hook")
        hook = CronHook(args.task_name_filter, args.cache_root)

    elif args.repository == config.MOZILLA_CENTRAL_REPOSITORY:
        logger.info("Running Mozilla Central hook")
        hook = MozillaCentralHook(args.task_name_filter, args.cache_root, args.revision)

    elif args.repository == config.TRY_REPOSITORY:
        logger.info("Running Try hook")
        hook = TryHook(args.task_name_filter, args.cache_root, args.revision)

    else:
        raise Exception(f"Invalid configuration for {args.repository}/{args.revision}")

    hook.run()


if __name__ == "__main__":
    main()

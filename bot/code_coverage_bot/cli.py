# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os

import yaml

from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config
from code_coverage_bot.libmozdata import setup as setup_libmozdata
from code_coverage_bot.log import init_logger


def setup_cli(parameters=True):
    """
    Setup CLI options parser and taskcluster bootstrap
    """
    parser = argparse.ArgumentParser(description="Mozilla Code Coverage Bot")
    if parameters:
        parser.add_argument("--repository", default=os.environ.get("REPOSITORY"))

        parser.add_argument("--task-group-id", default=os.environ.get("TASK_GROUP_ID"))

        parser.add_argument("--revision", default=os.environ.get("REVISION"))

    parser.add_argument(
        "--cache-root", required=True, help="Cache root, used to pull changesets"
    )
    parser.add_argument(
        "--working-dir",
        required=True,
        help="Working dir to download artifacts and build reports",
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
    parser.add_argument(
        "--local-configuration",
        help="Path to a local YAML configuration file",
        type=open,
    )
    parser.add_argument("--taskcluster-client-id", help="Taskcluster Client ID")
    parser.add_argument("--taskcluster-access-token", help="Taskcluster Access token")
    args = parser.parse_args()

    if parameters:
        if args.task_group_id and (args.repository or args.revision):
            parser.error(
                "Provide either --task-group-id or --repository/--revision, not both."
            )

        if args.repository and not args.revision:
            parser.error("--repository requires --revision")

        if not args.task_group_id and not args.repository:
            parser.error("Provide either --task-group-id or --repository/--revision.")

    # Auth on Taskcluster
    taskcluster_config.auth(args.taskcluster_client_id, args.taskcluster_access_token)

    # Then load secrets
    secrets.load(
        args.taskcluster_secret,
        local_secrets=yaml.safe_load(args.local_configuration)
        if args.local_configuration
        else None,
    )

    init_logger(
        "bot",
        channel=secrets.get("APP_CHANNEL", "dev"),
        PAPERTRAIL_HOST=secrets.get("PAPERTRAIL_HOST"),
        PAPERTRAIL_PORT=secrets.get("PAPERTRAIL_PORT"),
        SENTRY_DSN=secrets.get("SENTRY_DSN"),
    )

    # Setup libmozdata configuration.
    setup_libmozdata("code_coverage_bot")

    return args

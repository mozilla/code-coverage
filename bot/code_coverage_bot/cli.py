# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging
import os

import yaml

from code_coverage_bot.secrets import secrets
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
    parser.add_argument("--namespace", default=os.environ.get("NAMESPACE"))
    parser.add_argument("--project", default=os.environ.get("PROJECT"))
    parser.add_argument("--upstream", default=os.environ.get("UPSTREAM"))
    parser.add_argument("--prefix", default=os.environ.get("PREFIX"))
    parser.add_argument(
        "--hook",
        help="Which hook mode you want repo to run in, either 'central' or 'try'",
    )
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

    # Auth on Taskcluster - We don't need this for now
    # taskcluster_config.auth(args.taskcluster_client_id, args.taskcluster_access_token)

    local_secrets_aws = os.environ.get("LOCAL_SECRETS")
    local_secrets = None

    if local_secrets_aws:
        local_secrets = json.loads(local_secrets_aws)
        # Fix our secrets, GCS needs to be json decoded, and everything needs to be wrapped in common
        local_secrets["GOOGLE_CLOUD_STORAGE"] = json.loads(
            local_secrets.get("GOOGLE_CLOUD_STORAGE")
        )
        local_secrets = {"common": local_secrets}
    elif args.local_configuration:
        local_secrets = yaml.safe_load(args.local_configuration)

    # Then load secrets
    secrets.load(args.taskcluster_secret, local_secrets=local_secrets)

    init_logger(
        "bot",
        level=logging.INFO,
        channel=secrets.get("APP_CHANNEL", "dev"),
        PAPERTRAIL_HOST=secrets.get("PAPERTRAIL_HOST"),
        PAPERTRAIL_PORT=secrets.get("PAPERTRAIL_PORT"),
        SENTRY_DSN=secrets.get("SENTRY_DSN"),
    )

    return args

# -*- coding: utf-8 -*-
import argparse
import os

import structlog
from libmozevent import taskcluster_config
from libmozevent.log import init_logger

from code_coverage_events.workflow import Events

logger = structlog.get_logger(__name__)


def parse_cli():
    """
    Setup CLI options parser
    """
    parser = argparse.ArgumentParser(description="Mozilla Code Review Bot")
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
    taskcluster_config.auth(args.taskcluster_client_id, args.taskcluster_access_token)
    taskcluster_config.load_secrets(
        args.taskcluster_secret,
        "events",
        required=("pulse_user", "pulse_password", "hook_id", "hook_group_id"),
        existing=dict(admins=["babadie@mozilla.com", "mcastelluccio@mozilla.com"]),
    )

    init_logger(
        "code_coverage_events",
        PAPERTRAIL_HOST=taskcluster_config.secrets.get("PAPERTRAIL_HOST"),
        PAPERTRAIL_PORT=taskcluster_config.secrets.get("PAPERTRAIL_PORT"),
        SENTRY_DSN=taskcluster_config.secrets.get("SENTRY_DSN"),
    )

    events = Events()
    events.run()


if __name__ == "__main__":
    main()

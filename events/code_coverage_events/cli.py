# -*- coding: utf-8 -*-
import argparse
import asyncio
import os

import structlog
from libmozevent import taskcluster_config
from libmozevent.bus import MessageBus
from libmozevent.log import init_logger
from libmozevent.monitoring import Monitoring
from libmozevent.pulse import PulseListener
from libmozevent.pulse import run_consumer

from code_coverage_events import QUEUE_MONITORING
from code_coverage_events import QUEUE_PULSE
from code_coverage_events.workflow import CodeCoverage

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


class Events(object):
    """
    Listen to pulse events and trigger new code coverage tasks
    """

    def __init__(self):
        # Create message bus shared amongst process
        self.bus = MessageBus()

        # Build code coverage workflow
        self.workflow = CodeCoverage(
            taskcluster_config.secrets["hook_id"],
            taskcluster_config.secrets["hook_group_id"],
            self.bus,
        )

        # Setup monitoring for newly created tasks
        self.monitoring = Monitoring(
            QUEUE_MONITORING, taskcluster_config.secrets["admins"], 7 * 3600
        )
        self.monitoring.register(self.bus)

        # Create pulse listener for code coverage
        self.pulse = PulseListener(
            QUEUE_PULSE,
            "exchange/taskcluster-queue/v1/task-group-resolved",
            "#",
            taskcluster_config.secrets["pulse_user"],
            taskcluster_config.secrets["pulse_password"],
        )
        self.pulse.register(self.bus)

    def run(self):

        consumers = [
            # Code coverage main workflow
            self.workflow.run(),
            # Add monitoring task
            self.monitoring.run(),
            # Add pulse task
            self.pulse.run(),
        ]

        # Run all tasks concurrently
        run_consumer(asyncio.gather(*consumers))


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

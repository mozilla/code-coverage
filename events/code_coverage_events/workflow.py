# -*- coding: utf-8 -*-

import asyncio

import requests
import structlog
from libmozevent.bus import MessageBus
from libmozevent.monitoring import Monitoring
from libmozevent.pulse import PulseListener
from libmozevent.utils import retry
from libmozevent.utils import run_tasks

from code_coverage_events import QUEUE_MONITORING
from code_coverage_events import QUEUE_PULSE
from code_coverage_events import taskcluster_config

logger = structlog.get_logger(__name__)


class CodeCoverage(object):
    """
    Taskcluster hook handling the code coverage
    """

    def __init__(self, hook_id, hook_group_id, bus):
        self.triggered_groups = set()
        self.group_id = hook_group_id
        self.hook_id = hook_id
        self.bus = bus

        # Setup TC services
        self.queue = taskcluster_config.get_service("queue")
        self.hooks = taskcluster_config.get_service("hooks")

    async def run(self):
        """
        Main consumer, running queued payloads from the pulse listener
        """
        while True:
            # Get next payload from pulse messages
            payload = await self.bus.receive(QUEUE_PULSE)

            # Parse the payload to extract a new task's environment
            envs = await self.parse(payload["body"])
            if envs is None:
                continue

            for env in envs:
                # Trigger new tasks
                task = self.hooks.triggerHook(self.group_id, self.hook_id, env)
                task_id = task["status"]["taskId"]
                logger.info("Triggered a new code coverage task", id=task_id)

                # Send task to monitoring
                await self.bus.send(
                    QUEUE_MONITORING, (self.group_id, self.hook_id, task_id)
                )

    def is_coverage_task(self, task):
        return "ccov" in task["task"]["metadata"]["name"].split("/")[0].split("-")

    async def get_coverage_task_in_group(self, group_id):
        if group_id in self.triggered_groups:
            logger.info(
                "Received duplicated groupResolved notification", group=group_id
            )
            return None

        def maybe_trigger(tasks):
            logger.info(
                "Checking code coverage tasks", group_id=group_id, nb=len(tasks)
            )
            for task in tasks:
                if self.is_coverage_task(task):
                    self.triggered_groups.add(group_id)
                    return task

            return None

        def load_tasks(limit=200, continuationToken=None):
            query = {"limit": limit}
            if continuationToken is not None:
                query["continuationToken"] = continuationToken
            reply = retry(lambda: self.queue.listTaskGroup(group_id, query=query))
            return maybe_trigger(reply["tasks"]), reply.get("continuationToken")

        async def retrieve_coverage_task():
            task, token = load_tasks()

            while task is None and token is not None:
                task, token = load_tasks(continuationToken=token)

                # Let other tasks run on long batches
                await asyncio.sleep(0)

            return task

        try:
            return await retrieve_coverage_task()
        except requests.exceptions.HTTPError:
            return None

    async def parse(self, body):
        """
        Extract revisions from payload
        """
        taskGroupId = body["taskGroupId"]
        scheduler = body["schedulerId"]

        # Check the scheduler name before loading all tasks in the group
        # We are only interested in Mozilla gecko builds
        if not scheduler.startswith("gecko-level-"):
            logger.info(
                "Skipping task, unsupported scheduler",
                group_id=taskGroupId,
                scheduler=scheduler,
            )
            return None

        coverage_task = await self.get_coverage_task_in_group(taskGroupId)
        if coverage_task is None:
            return None

        repository = coverage_task["task"]["payload"]["env"]["GECKO_HEAD_REPOSITORY"]

        if repository not in [
            "https://hg.mozilla.org/mozilla-central",
            "https://hg.mozilla.org/try",
        ]:
            logger.warn(
                "Received groupResolved notification for a coverage task in an unexpected branch",
                repository=repository,
            )
            return None

        revision = coverage_task["task"]["payload"]["env"]["GECKO_HEAD_REV"]

        logger.info(
            "Received groupResolved notification for coverage builds",
            repository=repository,
            revision=revision,
            group=taskGroupId,
        )

        return [{"REPOSITORY": repository, "REVISION": revision}]


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
            taskcluster_config,
            QUEUE_MONITORING,
            taskcluster_config.secrets["admins"],
            7 * 3600,
        )
        self.monitoring.register(self.bus)

        # Create pulse listener for code coverage
        self.pulse = PulseListener(
            {
                QUEUE_PULSE: [
                    ("exchange/taskcluster-queue/v1/task-group-resolved", ["#"])
                ]
            },
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
        run_tasks(consumers)

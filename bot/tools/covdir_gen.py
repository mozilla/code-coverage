# -*- coding: utf-8 -*-
import argparse
import json
import os
from datetime import datetime

from taskcluster.utils import slugId

from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config

MC_REPO = "https://hg.mozilla.org/mozilla-central"
HOOK_GROUP = "project-relman"
HOOK_ID = "code-coverage-{app_channel}"


def trigger_task(task_group_id, commit):
    """
    Trigger a code coverage task to build covdir at a specified revision
    """
    date = datetime.fromtimestamp(commit["date"]).strftime("%Y-%m-%d")
    name = "covdir with suites on {} - {} - {}".format(
        secrets[secrets.APP_CHANNEL], date, commit["changeset"]
    )
    hooks = taskcluster_config.get_service("hooks")
    payload = {
        "REPOSITORY": MC_REPO,
        "REVISION": commit["changeset"],
        "taskGroupId": task_group_id,
        "taskName": name,
    }
    hook_id = HOOK_ID.format(app_channel=secrets[secrets.APP_CHANNEL])
    return hooks.triggerHook(HOOK_GROUP, hook_id, payload)


def main():
    # CLI args
    parser = argparse.ArgumentParser()
    parser.add_argument("--nb-tasks", type=int, default=5, help="NB of tasks to create")
    parser.add_argument(
        "--group", type=str, default=slugId(), help="Task group to create/update"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List actions without triggering any new task",
    )
    parser.add_argument(
        "history", type=open, help="JSON payload of /v2/history endpoint"
    )
    args = parser.parse_args()

    # Setup Taskcluster
    taskcluster_config.auth()
    secrets.load(os.environ["TASKCLUSTER_SECRET"])

    # List existing tags & commits
    print("Group", args.group)
    queue = taskcluster_config.get_service("queue")
    try:
        group = queue.listTaskGroup(args.group)
        commits = [
            task["task"]["payload"]["env"]["REVISION"]
            for task in group["tasks"]
            if task["status"]["state"] not in ("failed", "exception")
        ]
        print(
            "Found {} commits processed in task group {}".format(
                len(commits), args.group
            )
        )
    except Exception as e:
        print("Invalid task group : {}".format(e))
        commits = []

    # Read the history file
    history = json.load(args.history)

    # Load initial dates from our history
    history_dates = {
        item["changeset"]: datetime.fromtimestamp(item["date"]).date()
        for item in history
    }
    dates = [history_dates[commit] for commit in commits if commit in history_dates]

    # Trigger a task for each commit
    nb = 0
    for commit in history:
        date = datetime.fromtimestamp(commit["date"])
        if nb >= args.nb_tasks:
            break
        if commit["changeset"] in commits:
            print(
                f"Skipping commit {commit['changeset']} from {date} : already processed"
            )
            continue

        if date.date() in dates:
            print(f"Skipping commit {commit['changeset']} from {date} : same day")
            continue

        print(f"Triggering commit {commit['changeset']} from {date}")
        if args.dry_run:
            print(">>> No trigger on dry run")
        else:
            out = trigger_task(args.group, commit)
            print(">>>", out["status"]["taskId"])
        nb += 1
        dates.append(date.date())


if __name__ == "__main__":
    main()

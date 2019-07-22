# -*- coding: utf-8 -*-
import argparse
import os

from taskcluster.utils import slugId

from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config

CODECOV_URL = 'https://codecov.io/api/gh/marco-c/gecko-dev/commit'
HOOK_GROUP = 'project-relman'
HOOK_ID = 'code-coverage-{app_channel}'

taskcluster_config.auth(
    os.environ.get('TASKCLUSTER_CLIENT_ID'),
    os.environ.get('TASKCLUSTER_ACCESS_TOKEN'),
)
secrets.load(
    os.environ['TASKCLUSTER_SECRET'],
)
queue = taskcluster_config.get_service('queue')


def list_commits(tasks):
    '''
    Read the revision from an existing code coverage task
    '''
    for task_id in tasks:
        try:
            task = queue.task(task_id)
            env = task['payload']['env']
            yield env['REPOSITORY'], env['REVISION']
        except Exception as e:
            print('Failed to load task {}: {}'.format(task_id, e))


def trigger_task(task_group_id, repository, commit):
    '''
    Trigger a code coverage task to build covdir at a specified revision
    '''
    assert isinstance(commit, str)
    name = 'covdir {} - {} - {}'.format(secrets[secrets.APP_CHANNEL], repository, commit)
    hooks = taskcluster_config.get_service('hooks')
    payload = {
        'REPOSITORY': repository,
        'REVISION': commit,
        'taskGroupId': task_group_id,
        'taskName': name,
    }
    hook_id = HOOK_ID.format(app_channel=secrets[secrets.APP_CHANNEL])
    return hooks.triggerHook(HOOK_GROUP, hook_id, payload)


def main():
    # CLI args
    parser = argparse.ArgumentParser()
    parser.add_argument('--nb-tasks', type=int, default=5, help='NB of tasks to create')
    parser.add_argument('--group', type=str, default=slugId(), help='Task group to create/update')
    parser.add_argument('--dry-run', action='store_true', default=False, help='List actions without triggering any new task')
    parser.add_argument('tasks', nargs='+', help='Existing tasks to retrigger')
    args = parser.parse_args()

    # List existing tags & commits
    print('Group', args.group)
    try:
        group = queue.listTaskGroup(args.group)
        commits = [
            task['task']['payload']['env']['REVISION']
            for task in group['tasks']
            if task['status']['state'] not in ('failed', 'exception')
        ]
        print('Found {} commits processed in task group {}'.format(len(commits), args.group))
    except Exception as e:
        print('Invalid task group : {}'.format(e))
        commits = []

    # Trigger a task for each commit
    triggered = 0
    for repository, commit in list_commits(args.tasks):
        if (repository, commit) in commits:
            print('Skipping existing commit {} {}'.format(repository, commit))
            continue

        print('Triggering {} : {}'.format(repository, commit))
        if args.dry_run:
            print('>>> No trigger on dry run')
        else:
            out = trigger_task(args.group, repository, commit)
            print('>>>', out['status']['taskId'])
            triggered += 1

        commits.append((repository, commit))
        if triggered >= args.nb_tasks:
            print('Max nb tasks reached !')
            break


if __name__ == '__main__':
    main()

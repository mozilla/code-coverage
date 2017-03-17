import os
import shutil
import subprocess
import time
import argparse
import requests


def get_last_task():
    r = requests.get('https://index.taskcluster.net/v1/task/gecko.v2.mozilla-central.latest.firefox.linux64-ccov-opt')
    last_task = r.json()
    return last_task['taskId']


def get_task(branch, revision):
    r = requests.get('https://index.taskcluster.net/v1/task/gecko.v2.%s.revision.%s.firefox.linux64-ccov-opt' % (branch, revision))
    task = r.json()
    return task['taskId']


def get_task_details(task_id):
    r = requests.get('https://queue.taskcluster.net/v1/task/' + task_id)
    return r.json()


def get_task_artifacts(task_id):
    r = requests.get('https://queue.taskcluster.net/v1/task/' + task_id + '/artifacts')
    return r.json()['artifacts']


def get_tasks_in_group(group_id):
    r = requests.get('https://queue.taskcluster.net/v1/task-group/' + group_id + '/list', params={
        'limit': 200
    })
    reply = r.json()
    tasks = reply['tasks']
    while 'continuationToken' in reply:
        r = requests.get('https://queue.taskcluster.net/v1/task-group/' + group_id + '/list', params={
            'limit': 200,
            'continuationToken': reply['continuationToken']
        })
        reply = r.json()
        tasks += reply['tasks']
    return tasks


def download_artifact(task_id, artifact):
    r = requests.get('https://queue.taskcluster.net/v1/task/' + task_id + '/artifacts/' + artifact['name'], stream=True)
    with open(os.path.join('ccov-artifacts', task_id + '_' + os.path.basename(artifact['name'])), 'wb') as f:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, f)


def download_coverage_artifacts(build_task_id):
    try:
        shutil.rmtree("ccov-artifacts")
    except:
        pass

    try:
        os.mkdir("ccov-artifacts")
    except:
        pass

    task_data = get_task_details(build_task_id)

    artifacts = get_task_artifacts(build_task_id)
    for artifact in artifacts:
        if 'target.code-coverage-gcno.zip' in artifact['name']:
            download_artifact(build_task_id, artifact)

    test_tasks = [t for t in get_tasks_in_group(task_data['taskGroupId']) if t['task']['metadata']['name'].startswith('test-linux64-ccov')]
    for test_task in test_tasks:
        artifacts = get_task_artifacts(test_task['status']['taskId'])
        for artifact in artifacts:
            if 'code-coverage-gcda.zip' in artifact['name']:
                download_artifact(test_task['status']['taskId'], artifact)


def generate_info(grcov_path):
    files = os.listdir("ccov-artifacts")
    ordered_files = []
    for fname in files:
        if not fname.endswith('.zip'):
            continue

        if 'gcno' in fname:
            ordered_files.insert(0, "ccov-artifacts/" + fname)
        else:
            ordered_files.append("ccov-artifacts/" + fname)

    fout = open("output.info", 'w')
    cmd = [grcov_path, '-z', '-t', 'lcov', '-s', '/home/worker/workspace/build/src/']
    cmd.extend(ordered_files)
    proc = subprocess.Popen(cmd, stdout=fout, stderr=subprocess.PIPE)
    i = 0
    while proc.poll() is None:
        print('Running grcov... ' + str(i))
        i += 1
        time.sleep(60)

    if proc.poll() != 0:
        raise Exception("Error while running grcov:\n" + proc.stderr.read())


def generate_report(src_dir, auto_use_gecko_dev, revision):
    cwd = os.getcwd()
    os.chdir(src_dir)
    ret = subprocess.call(["genhtml", "-o", os.path.join(cwd, "report"), "--show-details", "--highlight", "--ignore-errors", "source", "--legend", os.path.join(cwd, "output.info"), "--prefix", src_dir])
    if ret != 0:
        raise Exception("Error while running genhtml.")
    os.chdir(cwd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src_dir", action="store", help="Path to the source directory")
    parser.add_argument("branch", action="store", nargs='?', help="Branch on which jobs ran")
    parser.add_argument("commit", action="store", nargs='?', help="Commit hash for push")
    parser.add_argument("--grcov", action="store", nargs='?', default="grcov", help="Path to grcov")
    parser.add_argument("--no-download", action="store_true", help="Use already downloaded coverage files")
    parser.add_argument("--no-grcov", action="store_true", help="Use already generated grcov output (implies --no-download)")
    args = parser.parse_args()

    if args.no_grcov:
        args.no_download = True

    if (args.branch is None) != (args.commit is None) and not args.no_download:
        parser.print_help()
        return

    if not args.no_download:
        if args.branch is None and args.commit is None:
            task_id = get_last_task()
        else:
            task_id = get_task(args.branch, args.commit)

            download_coverage_artifacts(task_id)

    if not args.no_grcov:
        generate_info(args.grcov)

    generate_report(os.path.abspath(args.src_dir))


if __name__ == "__main__":
    main()

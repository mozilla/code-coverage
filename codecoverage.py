import argparse
import errno
import json
import os
import shutil
import subprocess
import tarfile
import time
try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen
import warnings


def get_json(url, params=None):
    if params is not None:
        url += '?' + urlencode(params)

    r = urlopen(url).read().decode('utf-8')

    return json.loads(r)


def get_last_task():
    last_task = get_json('https://index.taskcluster.net/v1/task/gecko.v2.mozilla-central.latest.firefox.linux64-ccov-opt')
    return last_task['taskId']


def get_task(branch, revision):
    task = get_json('https://index.taskcluster.net/v1/task/gecko.v2.%s.revision.%s.firefox.linux64-ccov-opt' % (branch, revision))
    return task['taskId']


def get_task_details(task_id):
    task_details = get_json('https://queue.taskcluster.net/v1/task/' + task_id)
    return task_details


def get_task_artifacts(task_id):
    artifacts = get_json('https://queue.taskcluster.net/v1/task/' + task_id + '/artifacts')
    return artifacts['artifacts']


def get_tasks_in_group(group_id):
    reply = get_json('https://queue.taskcluster.net/v1/task-group/' + group_id + '/list', {
        'limit': '200',
    })
    tasks = reply['tasks']
    while 'continuationToken' in reply:
        reply = get_json('https://queue.taskcluster.net/v1/task-group/' + group_id + '/list', {
            'limit': '200',
            'continuationToken': reply['continuationToken'],
        })
        tasks += reply['tasks']
    return tasks


def download_artifact(task_id, artifact):
    fname = os.path.join('ccov-artifacts', task_id + '_' + os.path.basename(artifact['name']))
    urlretrieve('https://queue.taskcluster.net/v1/task/' + task_id + '/artifacts/' + artifact['name'], fname)


def suite_name_from_task_name(name):
    name = name[len('test-linux64-ccov/opt-'):]
    parts = [p for p in name.split('-') if p != 'e10s' and not p.isdigit()]
    return '-'.join(parts)


def download_coverage_artifacts(build_task_id, suites):
    shutil.rmtree('ccov-artifacts', ignore_errors=True)

    try:
        os.mkdir('ccov-artifacts')
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e

    task_data = get_task_details(build_task_id)

    artifacts = get_task_artifacts(build_task_id)
    for artifact in artifacts:
        if 'target.code-coverage-gcno.zip' in artifact['name']:
            download_artifact(build_task_id, artifact)

    # Returns True if the task is a test-related task.
    def _is_test_task(t):
        return t['task']['metadata']['name'].startswith('test-linux64-ccov')

    # Returns True if the task is part of one of the suites chosen by the user.
    def _is_chosen_task(t):
        return suites is None or suite_name_from_task_name(t['task']['metadata']['name']) in suites

    test_tasks = [t for t in get_tasks_in_group(task_data['taskGroupId']) if _is_test_task(t) and _is_chosen_task(t)]

    for suite in suites:
        if not any(suite in t['task']['metadata']['name'] for t in test_tasks):
            warnings.warn('Suite %s not found' % suite)

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

    # Assume we're on a one-click loaner.
    mod_env = os.environ.copy()
    if os.path.isdir('/home/worker/workspace/build/src/gcc/bin'):
        mod_env['PATH'] = '/home/worker/workspace/build/src/gcc/bin:' + mod_env['PATH']

    fout = open("output.info", 'w')
    cmd = [grcov_path, '-z', '-t', 'lcov', '-s', '/home/worker/workspace/build/src/']
    cmd.extend(ordered_files)
    proc = subprocess.Popen(cmd, stdout=fout, stderr=subprocess.PIPE, env=mod_env)
    i = 0
    while proc.poll() is None:
        print('Running grcov... ' + str(i))
        i += 1
        time.sleep(60)

    if proc.poll() != 0:
        raise Exception("Error while running grcov:\n" + proc.stderr.read())


def generate_report(src_dir):
    cwd = os.getcwd()
    os.chdir(src_dir)
    ret = subprocess.call(["genhtml", "-o", os.path.join(cwd, "report"), "--show-details", "--highlight", "--ignore-errors", "source", "--legend", os.path.join(cwd, "output.info"), "--prefix", src_dir])
    if ret != 0:
        raise Exception("Error while running genhtml.")
    os.chdir(cwd)


def download_grcov():
    r = get_json('https://api.github.com/repos/marco-c/grcov/releases/latest')
    latest_tag = r['tag_name']

    if os.path.exists('grcov') and os.path.exists('grcov_ver'):
        with open('grcov_ver', 'r') as f:
            installed_ver = f.read()

        if installed_ver == latest_tag:
            return

    urlretrieve('https://github.com/marco-c/grcov/releases/download/%s/grcov-linux-standalone-x86_64.tar.bz2' % latest_tag, 'grcov.tar.bz2')

    tar = tarfile.open('grcov.tar.bz2', 'r:bz2')
    tar.extractall()
    tar.close()

    os.remove('grcov.tar.bz2')

    with open('grcov_ver', 'w') as f:
        f.write(latest_tag)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src_dir", action="store", help="Path to the source directory")
    parser.add_argument("branch", action="store", nargs='?', help="Branch on which jobs ran")
    parser.add_argument("commit", action="store", nargs='?', help="Commit hash for push")
    parser.add_argument("--grcov", action="store", nargs='?', default="grcov", help="Path to grcov")
    parser.add_argument("--no-download", action="store_true", help="Use already downloaded coverage files")
    parser.add_argument("--no-grcov", action="store_true", help="Use already generated grcov output (implies --no-download)")
    parser.add_argument("--suite", action="store", nargs='+', help="List of test suites to include (by default they are all included). E.g. 'mochitest', 'mochitest-chrome', 'gtest', etc.")
    args = parser.parse_args()

    if args.no_grcov:
        args.no_download = True

    if (args.branch is None) != (args.commit is None) and not args.no_download:
        parser.print_help()
        return

    if not args.no_download:
        if args.branch and args.commit:
            task_id = get_task(args.branch, args.commit)
        elif 'MH_BRANCH' in os.environ and 'GECKO_HEAD_REV' in os.environ:
            task_id = get_task(os.environ['MH_BRANCH'], os.environ['GECKO_HEAD_REV'])
        else:
            task_id = get_last_task()

        download_coverage_artifacts(task_id, args.suite)

    if not args.no_grcov:
        if args.grcov:
            grcov_path = args.grcov
        else:
            download_grcov()
            grcov_path = './grcov'

        generate_info(grcov_path)

    generate_report(os.path.abspath(args.src_dir))


if __name__ == "__main__":
    main()

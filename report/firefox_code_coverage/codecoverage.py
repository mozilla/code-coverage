# -*- coding: utf-8 -*-

import argparse
import errno
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import warnings

import requests

from firefox_code_coverage import taskcluster

FINISHED_STATUSES = ["completed", "failed", "exception"]
ALL_STATUSES = FINISHED_STATUSES + ["unscheduled", "pending", "running"]
STATUS_VALUE = {"exception": 1, "failed": 2, "completed": 3}

GRCOV_INDEX = "gecko.cache.level-3.toolchains.v3.linux64-grcov.latest"
GRCOV_ARTIFACT = "public/build/grcov.tar.xz"


def is_taskcluster_loaner():
    return "TASKCLUSTER_INTERACTIVE" in os.environ


def get_task(branch, revision):
    index = taskcluster.get_service("index")
    task = index.findTask(f"gecko.v2.{branch}.revision.{revision}.firefox.decision")
    return task["taskId"]


def get_last_task():
    resp = requests.get(
        "https://api.coverage.moz.tools/v2/latest?repository=mozilla-central"
    )
    resp.raise_for_status()
    data = resp.json()
    revision = data[0]["revision"]
    return get_task("mozilla-central", revision)


def get_task_details(task_id):
    queue = taskcluster.get_service("queue")
    return queue.task(task_id)


def get_task_artifacts(task_id):
    queue = taskcluster.get_service("queue")
    response = queue.listLatestArtifacts(task_id)
    return response["artifacts"]


def get_tasks_in_group(group_id):
    tasks = []

    def _save_tasks(response):
        tasks.extend(response["tasks"])

    queue = taskcluster.get_service("queue")
    queue.listTaskGroup(group_id, paginationHandler=_save_tasks)

    return tasks


def download_binary(url, path, retries=5):
    """Download a binary file from an url"""
    for i in range(1, retries + 1):
        try:
            artifact = requests.get(url, stream=True)
            artifact.raise_for_status()

            with open(path, "wb") as f:
                for chunk in artifact.iter_content(chunk_size=8192):
                    f.write(chunk)
            break
        except:  # noqa: E722
            try:
                os.remove(path)
            except OSError:
                pass

            if i == retries:
                raise Exception(
                    "Download failed after {} retries - {}".format(retries, url)
                )

            time.sleep(7 * i)


def download_artifact(task_id, artifact, artifacts_path):
    fname = os.path.join(
        artifacts_path, task_id + "_" + os.path.basename(artifact["name"])
    )

    # As recommended by Taskcluster doc, use requests to download
    # from the artifact public url instead of relying on the client method
    queue = taskcluster.get_service("queue")
    url = queue.buildUrl("getLatestArtifact", task_id, artifact["name"])

    if not os.path.exists(fname):
        download_binary(url, fname)

    return fname


def get_chunk(task_name):
    # Some tests are run on build machines, we define placeholder chunks for those.
    if task_name.startswith("build-signing-"):
        return "build-signing"
    elif task_name.startswith("build-"):
        return "build"

    task_name = task_name[task_name.find("/") + 1 :]
    return "-".join(
        p for p in task_name.split("-") if p not in ("opt", "debug", "e10s", "1proc")
    )


def get_suite(task_name):
    return "-".join(p for p in get_chunk(task_name).split("-") if not p.isdigit())


def get_platform(task_name):
    if "linux" in task_name:
        return "linux"
    elif "win" in task_name:
        return "windows"
    elif "macosx" in task_name:
        return "macos"
    else:
        raise Exception(f"Unknown platform for {task_name}")


def get_task_status(task_id):
    queue = taskcluster.get_service("queue")
    status = queue.status(task_id)
    return status["status"]["state"]


def download_coverage_artifacts(
    decision_task_id,
    suites,
    platforms,
    artifacts_path,
    suites_to_ignore=["talos", "awsy"],
):
    try:
        os.mkdir(artifacts_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e

    task_data = get_task_details(decision_task_id)

    # Returns True if the task is a test-related coverage task (build tasks are included).
    def _is_test_task(t):
        return "ccov" in t["task"]["metadata"]["name"].split("/")[0].split("-")

    # Returns True if the task is part of one of the suites chosen by the user.
    def _is_in_suites_task(t):
        suite_name = get_suite(t["task"]["metadata"]["name"])
        return (
            suites is None or suite_name in suites
        ) and suite_name not in suites_to_ignore

    def _is_in_platforms_task(t):
        platform = get_platform(t["task"]["metadata"]["name"])
        return platforms is None or platform in platforms

    test_tasks = [
        t
        for t in get_tasks_in_group(task_data["taskGroupId"])
        if _is_test_task(t) and _is_in_suites_task(t) and _is_in_platforms_task(t)
    ]

    if suites is not None:
        for suite in suites:
            if not any(suite in t["task"]["metadata"]["name"] for t in test_tasks):
                warnings.warn("Suite %s not found" % suite)

    download_tasks = {}

    for test_task in test_tasks:
        status = test_task["status"]["state"]
        assert status in ALL_STATUSES, "State '{}' not recognized".format(status)

        while status not in FINISHED_STATUSES:
            sys.stdout.write(
                "\rWaiting for task {} to finish...".format(
                    test_task["status"]["taskId"]
                )
            )
            sys.stdout.flush()
            time.sleep(60)
            status = get_task_status(test_task["status"]["taskId"])
            # Update the task status, as we will use it to compare statuses later.
            test_task["status"]["state"] = status
            assert status in ALL_STATUSES

        chunk_name = get_chunk(test_task["task"]["metadata"]["name"])
        platform_name = get_platform(test_task["task"]["metadata"]["name"])

        if (chunk_name, platform_name) not in download_tasks:
            download_tasks[(chunk_name, platform_name)] = test_task
        else:
            prev_task = download_tasks[(chunk_name, platform_name)]
            if STATUS_VALUE[status] > STATUS_VALUE[prev_task["status"]["state"]]:
                download_tasks[(chunk_name, platform_name)] = test_task

    artifact_paths = []
    for i, test_task in enumerate(download_tasks.values()):
        sys.stdout.write(
            "\rDownloading artifacts from {}/{} test task...".format(i, len(test_tasks))
        )
        sys.stdout.flush()
        artifacts = get_task_artifacts(test_task["status"]["taskId"])
        for artifact in artifacts:
            if any(
                a in artifact["name"]
                for a in ["code-coverage-grcov.zip", "code-coverage-jsvm.zip"]
            ):
                artifact_paths.append(
                    download_artifact(
                        test_task["status"]["taskId"], artifact, artifacts_path
                    )
                )
    print("")
    return artifact_paths


def generate_report(grcov_path, output_format, output_path, artifact_paths):
    mod_env = os.environ.copy()
    if is_taskcluster_loaner():
        one_click_loaner_gcc = "/home/worker/workspace/build/src/gcc/bin"
        i = 0
        while (
            not os.path.isdir(one_click_loaner_gcc)
            or len(os.listdir(one_click_loaner_gcc)) == 0
        ):
            print("Waiting one-click loaner to be ready... " + str(i))
            i += 1
            time.sleep(60)
        mod_env["PATH"] = one_click_loaner_gcc + ":" + mod_env["PATH"]
    fout = open(output_path, "w")
    cmd = [grcov_path, "-t", output_format, "-p", "/home/worker/workspace/build/src/"]
    if output_format in ["coveralls", "coveralls+"]:
        cmd += ["--token", "UNUSED", "--commit-sha", "UNUSED"]
    cmd.extend(artifact_paths)
    proc = subprocess.Popen(cmd, stdout=fout, stderr=subprocess.PIPE, env=mod_env)
    i = 0
    while proc.poll() is None:
        if i % 60 == 0:
            sys.stdout.write("\rRunning grcov... {} seconds".format(i))
            sys.stdout.flush()
        i += 1
        time.sleep(1)
    print("")

    if proc.poll() != 0:
        raise Exception("Error while running grcov: {}\n".format(proc.stderr.read()))


def generate_html_report(
    src_dir,
    info_file=os.path.join(os.getcwd(), "output.info"),
    output_dir=os.path.join(os.getcwd(), "report"),
    silent=False,
    style_file=None,
):
    cwd = os.getcwd()
    os.chdir(src_dir)

    with open(os.devnull, "w") as fnull:
        command = [
            os.path.join(cwd, "lcov-bin/usr/local/bin/genhtml"),
            "-o",
            output_dir,
            "--show-details",
            "--highlight",
            "--ignore-errors",
            "source",
            "--legend",
            info_file,
        ]
        if style_file is not None:
            command += ["--css-file", style_file]
        ret = subprocess.call(
            command, stdout=fnull if silent else None, stderr=fnull if silent else None
        )

    if ret != 0:
        raise Exception("Error while running genhtml.")

    os.chdir(cwd)


def download_grcov():
    local_path = "grcov"
    local_version = "grcov_ver"

    dest = tempfile.mkdtemp(suffix="grcov")
    archive = os.path.join(dest, "grcov.tar.xz")
    index = taskcluster.get_service("index")
    url = index.buildUrl("findArtifactFromTask", GRCOV_INDEX, GRCOV_ARTIFACT)
    download_binary(url, archive)

    # Extract archive in temp
    tar = tarfile.open(archive, "r:xz")
    tar.extractall(dest)
    tar.close()
    os.remove(archive)

    # Get version from grcov binary
    grcov = os.path.join(dest, "grcov")
    assert os.path.exists(grcov), "Missing grcov binary"
    version = subprocess.check_output([grcov, "--version"]).decode("utf-8")

    # Compare version with currently available
    if os.path.exists(local_path) and os.path.exists(local_version):
        with open(local_version, "r") as f:
            installed_ver = f.read()

        if installed_ver == version:
            return local_path

    # Promote downloaded version to installed one
    shutil.move(grcov, local_path)
    shutil.rmtree(dest)
    with open(local_version, "w") as f:
        f.write(version)

    return local_path


def download_genhtml():
    if os.path.isdir("lcov"):
        os.chdir("lcov")
        subprocess.check_call(["git", "pull"])
    else:
        subprocess.check_call(
            ["git", "clone", "https://github.com/linux-test-project/lcov.git"]
        )
        os.chdir("lcov")

    subprocess.check_call(["make", "install", "DESTDIR=../lcov-bin"])

    os.chdir("..")


def main():
    parser = argparse.ArgumentParser()

    if is_taskcluster_loaner():
        nargs = "?"
        default_src_dir = "/home/worker/workspace/build/src/"
        default_branch = os.environ["MH_BRANCH"]
        default_commit = os.environ["GECKO_HEAD_REV"]
    else:
        nargs = None
        default_src_dir = None
        default_branch = None
        default_commit = None

    parser.add_argument(
        "src_dir",
        action="store",
        nargs=nargs,
        default=default_src_dir,
        help="Path to the source directory",
    )
    parser.add_argument(
        "branch",
        action="store",
        nargs="?",
        default=default_branch,
        help="Branch on which jobs ran",
    )
    parser.add_argument(
        "commit",
        action="store",
        nargs="?",
        default=default_commit,
        help="Commit hash for push",
    )
    parser.add_argument("--grcov", action="store", nargs="?", help="Path to grcov")
    parser.add_argument(
        "--with-artifacts",
        action="store",
        nargs="?",
        default="ccov-artifacts",
        help="Path to already downloaded coverage files",
    )
    parser.add_argument(
        "--platform",
        action="store",
        nargs="+",
        help='List of platforms to include (by default they are all included). E.g. "linux", "windows", etc.',
    )
    parser.add_argument(
        "--suite",
        action="store",
        nargs="+",
        help='List of test suites to include (by default they are all included). E.g. "mochitest", "mochitest-chrome", "gtest", etc.',
    )
    parser.add_argument(
        "--ignore",
        action="store",
        nargs="+",
        help='List of test suites to ignore (by default "talos" and "awsy"). E.g. "mochitest", "mochitest-chrome", "gtest", etc.',
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Only generate high-level stats, not a full HTML report",
    )
    args = parser.parse_args()

    if (args.branch is None) != (args.commit is None):
        parser.print_help()
        return

    if args.branch and args.commit:
        task_id = get_task(args.branch, args.commit)
    else:
        task_id = get_last_task()

    if args.ignore is None:
        artifact_paths = download_coverage_artifacts(
            task_id, args.suite, args.platform, args.with_artifacts
        )
    else:
        artifact_paths = download_coverage_artifacts(
            task_id, args.suite, args.platform, args.with_artifacts, args.ignore
        )

    if args.grcov:
        grcov_path = args.grcov
    else:
        grcov_path = download_grcov()

    if args.stats:
        generate_report(grcov_path, "coveralls", "output.json", artifact_paths)

        with open("output.json", "r") as f:
            report = json.load(f)

        total_lines = 0
        total_lines_covered = 0
        for sf in report["source_files"]:
            for c in sf["coverage"]:
                if c is None:
                    continue

                total_lines += 1
                if c > 0:
                    total_lines_covered += 1

        print("Coverable lines: {}".format(total_lines))
        print("Covered lines: {}".format(total_lines_covered))
        print(
            "Coverage percentage: {}".format(
                float(total_lines_covered) / float(total_lines)
            )
        )
    else:
        generate_report(grcov_path, "lcov", "output.info", artifact_paths)

        download_genhtml()
        generate_html_report(os.path.abspath(args.src_dir))


if __name__ == "__main__":
    main()

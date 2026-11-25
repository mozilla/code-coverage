# -*- coding: utf-8 -*-
"""
Create a tree of empty files mirroring the files of a revision of Firefox.

Building covdir reports only needs to know which files exist in the
repository (to ignore coverage of files which don't, e.g. generated ones), not
their content. Instead of a full Mercurial clone (~7 GB, several minutes on a
worker without a warm cache), the list of files is retrieved from the Git
repository of Firefox, by fetching only the commit and its trees (~20 MB).
Revisions which are not in the Git repository (e.g. try pushes) can be listed
from a Mercurial clone without a working directory, which saves its
checkout.
"""

import os
import shutil
import stat
import subprocess
import tempfile

import hglib
import requests
import structlog
import tenacity

logger = structlog.get_logger(__name__)

GIT_REPOSITORY = "https://github.com/mozilla-firefox/firefox"
LANDO_HG2GIT = "https://lando.moz.tools/api/hg2git/firefox/{revision}"


@tenacity.retry(
    reraise=True,
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=30),
    stop=tenacity.stop_after_attempt(4),
)
def get_git_revision(hg_revision: str) -> str:
    """
    Map a Mercurial revision of Firefox to the corresponding Git revision
    """
    response = requests.get(LANDO_HG2GIT.format(revision=hg_revision), timeout=30)
    response.raise_for_status()
    return response.json()["git_hash"]


@tenacity.retry(
    reraise=True,
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=30),
    stop=tenacity.stop_after_attempt(4),
)
def list_files(git_revision: str, repository: str = GIT_REPOSITORY) -> list[bytes]:
    """
    List the paths of all the files at a Git revision, without downloading
    their content
    """
    with tempfile.TemporaryDirectory() as git_dir:

        def git(*args):
            return subprocess.run(
                ["git", "-C", git_dir, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout

        git("init", "--quiet")
        git(
            "fetch",
            "--quiet",
            "--depth",
            "1",
            "--filter=blob:none",
            repository,
            git_revision,
        )
        return git("ls-tree", "-r", "-z", "--name-only", "FETCH_HEAD").split(b"\0")[:-1]


def list_hg_files(repo_dir: str, revision: str) -> list[bytes]:
    """
    List the paths of all the files at a revision of a Mercurial repository,
    which doesn't need a working directory
    """
    return subprocess.run(
        [hglib.HGPATH, "files", "--rev", revision, "--print0"],
        cwd=repo_dir,
        env={**os.environ, "HGPLAIN": "1"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.split(b"\0")[:-1]


def create_from_files(files: list[bytes], path: str) -> int:
    """
    Create, at the given path, a tree of empty files with the given paths.

    Returns the number of files.
    """
    shutil.rmtree(path, ignore_errors=True)
    root = os.fsencode(path)
    directories = set()
    for name in files:
        directory = os.path.dirname(name)
        if directory not in directories:
            os.makedirs(os.path.join(root, directory), exist_ok=True)
            directories.add(directory)
        # Faster than opening and closing the file, as it takes a single
        # system call and doesn't allocate a file descriptor.
        os.mknod(os.path.join(root, name), stat.S_IFREG | 0o644)

    logger.info("Source tree created", path=path, files=len(files))
    return len(files)


def create_from_git(
    hg_revision: str, path: str, repository: str = GIT_REPOSITORY
) -> int:
    """
    Create, at the given path, a tree of empty files mirroring the files of
    the given Mercurial revision of Firefox, listed from the Git repository.

    Returns the number of files.
    """
    git_revision = get_git_revision(hg_revision)
    logger.info("Listing files", hg_revision=hg_revision, git_revision=git_revision)
    return create_from_files(list_files(git_revision, repository), path)

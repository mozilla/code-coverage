# -*- coding: utf-8 -*-
"""
Create a tree of empty files mirroring the files of a revision of Firefox.

Building covdir reports only needs to know which files exist in the
repository (to ignore coverage of files which don't, e.g. generated ones), not
their content. The files can be listed from a Mercurial clone without a
working directory, which saves checking out all of them.
"""

import os
import shutil
import subprocess

import hglib
import structlog

logger = structlog.get_logger(__name__)


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
        open(os.path.join(root, name), "wb").close()

    logger.info("Source tree created", path=path, files=len(files))
    return len(files)

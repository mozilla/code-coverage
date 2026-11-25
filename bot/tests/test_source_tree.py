# -*- coding: utf-8 -*-
import os
import subprocess

import responses

from code_coverage_bot import source_tree
from code_coverage_bot.hooks.repo import MozillaCentralHook
from code_coverage_bot.hooks.repo import TryHook

HG_REVISION = "618eadc80cdcd2b948877785453f225262c5f8df"


def git(repo, *args):
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            *args,
        ],
        check=True,
        capture_output=True,
    ).stdout


def test_create_from_git(tmp_path):
    repo = tmp_path / "repo"
    files = {
        "README.md": "readme",
        "dom/base/Document.cpp": "cpp",
        "dom/base/test/test_document.html": "html",
        "toolkit/components/ä file.js": "js",
    }
    for name, content in files.items():
        os.makedirs(repo / os.path.dirname(name), exist_ok=True)
        (repo / name).write_text(content)
    (repo / "mach").write_text("#!/usr/bin/env python3")
    (repo / "mach").chmod(0o755)
    git(repo, "init", "--quiet")
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "Initial commit")
    git_revision = git(repo, "rev-parse", "HEAD").decode().strip()

    tree = tmp_path / "tree"
    # Files from a previous tree are removed.
    os.makedirs(tree / "old")
    (tree / "old" / "file.cpp").write_text("")

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            source_tree.LANDO_HG2GIT.format(revision=HG_REVISION),
            json={"git_hash": git_revision, "hg_hash": HG_REVISION},
        )
        count = source_tree.create_from_git(
            HG_REVISION, str(tree), repository=str(repo)
        )

    assert count == len(files) + 1
    created = sorted(
        os.path.relpath(os.path.join(root, name), tree)
        for root, _, names in os.walk(tree)
        for name in names
    )
    assert created == sorted(list(files) + ["mach"])
    assert all(os.path.getsize(tree / name) == 0 for name in created)


def hg(repo, *args):
    return subprocess.run(
        ["hg", "--cwd", str(repo), *args],
        env={**os.environ, "HGPLAIN": "1", "HGRCPATH": os.devnull},
        check=True,
        capture_output=True,
    ).stdout


def test_list_hg_files(tmp_path):
    repo = tmp_path / "repo"
    os.makedirs(repo / "dom" / "base")
    (repo / "dom" / "base" / "Document.cpp").write_text("cpp")
    (repo / "README.md").write_text("readme")
    hg(tmp_path, "init", "repo")
    hg(repo, "commit", "--addremove", "-u", "Test", "-m", "First")
    first = hg(repo, "log", "-r", ".", "-T", "{node}").decode()

    # The files are listed at the given revision, whatever the working
    # directory is.
    (repo / "new.js").write_text("js")
    hg(repo, "commit", "--addremove", "-u", "Test", "-m", "Second")
    hg(repo, "update", "--quiet", "null")

    assert sorted(source_tree.list_hg_files(str(repo), first)) == [
        b"README.md",
        b"dom/base/Document.cpp",
    ]


def make_hook(cls, tmp_path, monkeypatch):
    hook = cls.__new__(cls)
    hook.revision = HG_REVISION
    hook.repo_dir = str(tmp_path / "mozilla-central")
    hook.source_tree_dir = str(tmp_path / "source-tree")

    calls = []
    monkeypatch.setattr(
        hook, "clone_repository", lambda update=True: calls.append(("clone", update))
    )
    monkeypatch.setattr(
        source_tree,
        "list_hg_files",
        lambda repo_dir, revision: calls.append(("hg files", repo_dir)) or [b"a.cpp"],
    )
    return hook, calls


def test_retrieve_source_from_git(monkeypatch, tmp_path):
    hook, calls = make_hook(MozillaCentralHook, tmp_path, monkeypatch)
    monkeypatch.setattr(source_tree, "create_from_git", lambda revision, path: 42)

    hook.retrieve_source()

    assert hook.repo_dir == hook.source_tree_dir
    assert calls == []


def test_retrieve_source_from_hg(monkeypatch, tmp_path):
    # When the files can't be listed from Git, or for try pushes which aren't
    # in the Git repository, the repository is cloned without a working
    # directory.
    def fail(revision, path):
        raise Exception("Lando is down")

    monkeypatch.setattr(source_tree, "create_from_git", fail)

    for cls in (MozillaCentralHook, TryHook):
        hook, calls = make_hook(cls, tmp_path, monkeypatch)

        hook.retrieve_source()

        assert calls == [
            ("clone", False),
            ("hg files", str(tmp_path / "mozilla-central")),
        ]
        assert hook.repo_dir == hook.source_tree_dir
        assert os.listdir(hook.source_tree_dir) == ["a.cpp"]

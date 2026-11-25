# -*- coding: utf-8 -*-
import os
import subprocess

from code_coverage_bot import source_tree
from code_coverage_bot.hooks.repo import MozillaCentralHook
from code_coverage_bot.hooks.repo import TryHook

HG_REVISION = "618eadc80cdcd2b948877785453f225262c5f8df"


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


def test_retrieve_source(monkeypatch, tmp_path):
    # The repository is cloned without a working directory, and the files are
    # listed from the store.
    for cls in (MozillaCentralHook, TryHook):
        hook, calls = make_hook(cls, tmp_path, monkeypatch)

        hook.retrieve_source()

        assert calls == [
            ("clone", False),
            ("hg files", str(tmp_path / "mozilla-central")),
        ]
        assert hook.repo_dir == hook.source_tree_dir
        assert os.listdir(hook.source_tree_dir) == ["a.cpp"]

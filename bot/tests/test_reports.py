# -*- coding: utf-8 -*-
import json
import os
import zipfile

from code_coverage_bot import grcov
from code_coverage_bot.artifacts import Artifact
from code_coverage_bot.artifacts import ArtifactsHandler
from code_coverage_bot.hooks.base import Hook


def lcov(files):
    out = ""
    for name, lines in files.items():
        out += f"SF:{name}\n"
        out += "FN:1,main\nFNDA:1,main\nFNF:1\nFNH:1\n"
        for line, count in lines.items():
            out += f"DA:{line},{count}\n"
        out += f"LF:{len(lines)}\nLH:{sum(1 for c in lines.values() if c)}\n"
        out += "end_of_record\n"
    return out


# The same files appear in several artifacts, platforms and suites, with
# different counts and lines, so aggregated reports need to sum them.
# missing.cpp doesn't exist in the source directory, and must be ignored.
ARTIFACTS = {
    ("linux", "mochitest", "mochitest-1"): {
        "dom/a.cpp": {1: 1, 2: 0, 3: 5},
        "dom/b.js": {1: 0, 2: 0},
        "missing.cpp": {1: 3},
    },
    ("linux", "mochitest", "mochitest-2"): {
        "dom/a.cpp": {1: 2, 2: 0, 3: 0, 4: 1},
    },
    ("linux", "xpcshell", "xpcshell-1"): {
        "dom/b.js": {1: 7, 2: 0},
        "js/c.cpp": {10: 0},
    },
    ("windows", "mochitest", "mochitest-1"): {
        "dom/a.cpp": {1: 6, 2: 4},
        "js/c.cpp": {10: 1, 11: 1},
    },
    ("windows", "reftest", "reftest-1"): {
        "dom/b.js": {1: 1, 2: 1},
    },
}


def test_build_reports(tmp_path):
    source_dir = tmp_path / "src"
    for path in ("dom/a.cpp", "dom/b.js", "js/c.cpp"):
        os.makedirs(source_dir / os.path.dirname(path), exist_ok=True)
        (source_dir / path).write_text("\n" * 20)

    artifacts = []
    for (platform, suite, chunk), files in ARTIFACTS.items():
        path = str(tmp_path / f"{platform}_{chunk}_code-coverage-grcov.zip")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("lcov.info", lcov(files))
        artifacts.append(Artifact(path, "task", platform, suite, chunk))

    hook = Hook.__new__(Hook)
    hook.repo_dir = str(source_dir)
    hook.reports_dir = str(tmp_path / "reports")
    hook.lines_dir = str(tmp_path / "lines")
    hook.artifactsHandler = ArtifactsHandler([])
    hook.artifactsHandler.artifacts = artifacts

    reports = list(hook.build_reports())

    # The full report is built first.
    assert reports[0][0] == ("all", "all")

    combinations = hook.artifactsHandler.get_combinations()
    assert sorted(key for key, _ in reports) == sorted(combinations)
    assert len(combinations) == 10

    # Reports built by merging are the same as the ones grcov builds from all
    # the artifacts of the combination.
    for key, path in reports:
        expected = grcov.report(
            combinations[key], source_dir=str(source_dir), out_format="covdir"
        )
        with open(path, "rb") as f:
            assert f.read() == expected, key

    # Sanity check that counts were summed across platforms and chunks, and
    # files missing from the source directory are ignored.
    with open(dict(reports)[("all", "mochitest")]) as f:
        report = json.load(f)
    assert report["children"]["dom"]["children"]["a.cpp"]["coverage"] == [9, 4, 5, 1]
    assert "missing.cpp" not in report["children"]

    # The LCOV files used to build aggregated reports don't contain functions.
    for root, _, files in os.walk(hook.lines_dir):
        for name in files:
            with open(os.path.join(root, name)) as f:
                assert not any(line.startswith("FN") for line in f), name

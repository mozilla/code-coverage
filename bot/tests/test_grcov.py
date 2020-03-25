# -*- coding: utf-8 -*-
import json

import pytest

from code_coverage_bot import grcov


def covdir_get(report, path):
    parts = path.split("/")
    for part in parts:
        report = report["children"][part]
    return report


def test_report_invalid_output_format(grcov_artifact):
    with pytest.raises(AssertionError, match="Unsupported output format"):
        grcov.report([grcov_artifact], out_format="UNSUPPORTED")
    with pytest.raises(AssertionError, match="Unsupported output format"):
        grcov.report([grcov_artifact], out_format="coveralls")


def test_report_grcov_artifact_coverallsplus(grcov_artifact):
    output = grcov.report([grcov_artifact], out_format="coveralls+")
    report = json.loads(output.decode("utf-8"))
    assert report["repo_token"] == "unused"
    assert report["git"]["branch"] == "master"
    assert report["service_number"] == ""
    assert len(report["source_files"]) == 1
    assert report["source_files"][0]["name"] == "js/src/jit/BitSet.cpp"
    assert report["source_files"][0]["coverage"] == [42, 42]
    assert report["source_files"][0]["branches"] == []
    assert "source_digest" in report["source_files"][0]
    assert len(report["source_files"][0]["functions"]) == 1
    assert report["source_files"][0]["functions"][0]["exec"]
    assert (
        report["source_files"][0]["functions"][0]["name"]
        == "_ZNK2js3jit6BitSet5emptyEv"
    )
    assert report["source_files"][0]["functions"][0]["start"] == 1


def test_report_grcov_artifact(grcov_artifact):
    output = grcov.report([grcov_artifact], out_format="covdir")
    report = json.loads(output.decode("utf-8"))
    assert report == {
        "children": {
            "js": {
                "children": {
                    "src": {
                        "children": {
                            "jit": {
                                "children": {
                                    "BitSet.cpp": {
                                        "coverage": [42, 42],
                                        "coveragePercent": 100.0,
                                        "linesCovered": 2,
                                        "linesMissed": 0,
                                        "linesTotal": 2,
                                        "name": "BitSet.cpp",
                                    }
                                },
                                "coveragePercent": 100.0,
                                "linesCovered": 2,
                                "linesMissed": 0,
                                "linesTotal": 2,
                                "name": "jit",
                            }
                        },
                        "coveragePercent": 100.0,
                        "linesCovered": 2,
                        "linesMissed": 0,
                        "linesTotal": 2,
                        "name": "src",
                    }
                },
                "coveragePercent": 100.0,
                "linesCovered": 2,
                "linesMissed": 0,
                "linesTotal": 2,
                "name": "js",
            }
        },
        "coveragePercent": 100.0,
        "linesCovered": 2,
        "linesMissed": 0,
        "linesTotal": 2,
        "name": "",
    }


def test_report_jsvm_artifact(jsvm_artifact):
    output = grcov.report([jsvm_artifact], out_format="covdir")
    report = json.loads(output.decode("utf-8"))
    assert report == {
        "children": {
            "toolkit": {
                "children": {
                    "components": {
                        "children": {
                            "osfile": {
                                "children": {
                                    "osfile.jsm": {
                                        "coverage": [42, 42],
                                        "coveragePercent": 100.0,
                                        "linesCovered": 2,
                                        "linesMissed": 0,
                                        "linesTotal": 2,
                                        "name": "osfile.jsm",
                                    }
                                },
                                "coveragePercent": 100.0,
                                "linesCovered": 2,
                                "linesMissed": 0,
                                "linesTotal": 2,
                                "name": "osfile",
                            }
                        },
                        "coveragePercent": 100.0,
                        "linesCovered": 2,
                        "linesMissed": 0,
                        "linesTotal": 2,
                        "name": "components",
                    }
                },
                "coveragePercent": 100.0,
                "linesCovered": 2,
                "linesMissed": 0,
                "linesTotal": 2,
                "name": "toolkit",
            }
        },
        "coveragePercent": 100.0,
        "linesCovered": 2,
        "linesMissed": 0,
        "linesTotal": 2,
        "name": "",
    }


def test_report_multiple_artifacts(grcov_artifact, jsvm_artifact):
    output = grcov.report([grcov_artifact, jsvm_artifact], out_format="covdir")
    report = json.loads(output.decode("utf-8"))

    assert report["linesTotal"] == 4
    assert report["linesCovered"] == 4
    assert report["coveragePercent"] == 100.0

    assert covdir_get(report, "toolkit/components/osfile/osfile.jsm") == {
        "coverage": [42, 42],
        "coveragePercent": 100.0,
        "linesCovered": 2,
        "linesMissed": 0,
        "linesTotal": 2,
        "name": "osfile.jsm",
    }
    assert covdir_get(report, "js/src/jit/BitSet.cpp") == {
        "coverage": [42, 42],
        "coveragePercent": 100.0,
        "linesCovered": 2,
        "linesMissed": 0,
        "linesTotal": 2,
        "name": "BitSet.cpp",
    }


def test_report_source_dir(
    fake_source_dir, grcov_artifact, grcov_existing_file_artifact
):
    output = grcov.report(
        [grcov_existing_file_artifact], source_dir=fake_source_dir, out_format="covdir"
    )
    report = json.loads(output.decode("utf-8"))
    assert report == {
        "children": {
            "code_coverage_bot": {
                "children": {
                    "cli.py": {
                        "coverage": [42, 42],
                        "coveragePercent": 100.0,
                        "linesCovered": 2,
                        "linesMissed": 0,
                        "linesTotal": 2,
                        "name": "cli.py",
                    }
                },
                "coveragePercent": 100.0,
                "linesCovered": 2,
                "linesMissed": 0,
                "linesTotal": 2,
                "name": "code_coverage_bot",
            }
        },
        "coveragePercent": 100.0,
        "linesCovered": 2,
        "linesMissed": 0,
        "linesTotal": 2,
        "name": "",
    }


def test_report_options(grcov_artifact, jsvm_artifact):
    output = grcov.report(
        [grcov_artifact, jsvm_artifact],
        out_format="covdir",
        options=["--ignore", "toolkit/*"],
    )
    report = json.loads(output.decode("utf-8"))
    assert report == {
        "children": {
            "js": {
                "children": {
                    "src": {
                        "children": {
                            "jit": {
                                "children": {
                                    "BitSet.cpp": {
                                        "coverage": [42, 42],
                                        "coveragePercent": 100.0,
                                        "linesCovered": 2,
                                        "linesMissed": 0,
                                        "linesTotal": 2,
                                        "name": "BitSet.cpp",
                                    }
                                },
                                "coveragePercent": 100.0,
                                "linesCovered": 2,
                                "linesMissed": 0,
                                "linesTotal": 2,
                                "name": "jit",
                            }
                        },
                        "coveragePercent": 100.0,
                        "linesCovered": 2,
                        "linesMissed": 0,
                        "linesTotal": 2,
                        "name": "src",
                    }
                },
                "coveragePercent": 100.0,
                "linesCovered": 2,
                "linesMissed": 0,
                "linesTotal": 2,
                "name": "js",
            }
        },
        "coveragePercent": 100.0,
        "linesCovered": 2,
        "linesMissed": 0,
        "linesTotal": 2,
        "name": "",
    }


def test_files_list(grcov_artifact, grcov_uncovered_artifact):
    files = grcov.files_list([grcov_artifact, grcov_uncovered_artifact])
    assert set(files) == set(["js/src/jit/BitSet.cpp"])


def test_files_list_source_dir(
    fake_source_dir, grcov_artifact, grcov_existing_file_artifact
):
    files = grcov.files_list(
        [grcov_artifact, grcov_existing_file_artifact], source_dir=fake_source_dir
    )
    assert set(files) == set(["code_coverage_bot/cli.py"])

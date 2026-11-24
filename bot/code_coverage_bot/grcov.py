# -*- coding: utf-8 -*-
import os

import structlog

from code_coverage_bot.utils import run_check

logger = structlog.get_logger(__name__)


def report(artifacts, source_dir=None, out_format="covdir", options=[]):
    assert out_format in (
        "covdir",
        "files",
        "lcov",
        "coveralls+",
    ), "Unsupported output format"
    cmd = ["grcov", "--ignore-parsing-error", "-t", out_format]

    # Coveralls+ is only needed for zero-coverage reports
    if out_format == "coveralls+":
        cmd.extend(["--token", "unused"])

    # Covdir reports don't contain functions, so there is no need to parse
    # them, which is much faster.
    if out_format == "covdir":
        cmd.append("--no-functions")

    if source_dir is not None:
        cmd.extend(["-s", source_dir])
        cmd.append("--ignore-not-existing")

    cmd.extend(artifacts)
    cmd.extend(options)

    try:
        return run_check(cmd)
    except Exception:
        logger.error("Error while running grcov")
        raise


def report_with_lines(artifacts, source_dir, out_dir):
    """
    Build a covdir report and an LCOV file holding only line coverage, in a
    single grcov run.

    The LCOV file can be used later as an input to grcov to build covdir
    reports aggregating several groups of artifacts. It is much faster than
    parsing all the original artifacts again: the LCOV file is the union of
    all the artifacts, without function records, which take ~90% of the
    artifacts but are not used in covdir reports.

    Returns the paths of the covdir report and of the LCOV file.
    """
    os.makedirs(out_dir, exist_ok=True)
    run_check(
        [
            "grcov",
            "--ignore-parsing-error",
            "--no-functions",
            "-t",
            "covdir,lcov",
            "-s",
            source_dir,
            "--ignore-not-existing",
            "-o",
            out_dir,
            *artifacts,
        ]
    )

    # grcov only accepts LCOV inputs with a .info extension.
    lines_lcov = os.path.join(out_dir, "lines.info")
    os.replace(os.path.join(out_dir, "lcov"), lines_lcov)

    return os.path.join(out_dir, "covdir"), lines_lcov


def files_list(artifacts, source_dir=None):
    options = ["--filter", "covered", "--threads", "2"]
    files = report(
        artifacts, source_dir=source_dir, out_format="files", options=options
    )
    return files.decode("utf-8").splitlines()

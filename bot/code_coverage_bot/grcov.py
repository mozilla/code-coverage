# -*- coding: utf-8 -*-
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
    cmd = ["grcov", "-t", out_format]

    # Coveralls+ is only needed for zero-coverage reports
    if out_format == "coveralls+":
        cmd.extend(
            [
                "--service-name",
                "TaskCluster",
                "--commit-sha",
                "unused",
                "--token",
                "unused",
                "--service-job-number",
                "1",
            ]
        )

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


def files_list(artifacts, source_dir=None):
    options = ["--filter", "covered", "--threads", "2"]
    files = report(
        artifacts, source_dir=source_dir, out_format="files", options=options
    )
    return files.decode("utf-8").splitlines()

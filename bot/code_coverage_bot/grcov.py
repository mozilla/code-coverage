# -*- coding: utf-8 -*-
import structlog

from code_coverage_bot.utils import run_check

logger = structlog.get_logger(__name__)


def report(artifacts, source_dir=None, out_format="covdir", threads=4, options=[]):
    assert out_format in (
        "covdir",
        "files",
        "lcov",
        "coveralls+",
    ), "Unsupported output format"
    cmd = [
        "grcov",
        "--threads",
        str(threads),
        "--ignore-parsing-error",
        "-t",
        out_format,
    ]

    # Coveralls+ is only needed for zero-coverage reports
    if out_format == "coveralls+":
        cmd.extend(["--token", "unused"])

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
    options = ["--filter", "covered"]
    files = report(
        artifacts,
        source_dir=source_dir,
        out_format="files",
        threads=2,
        options=options,
    )
    return files.decode("utf-8").splitlines()

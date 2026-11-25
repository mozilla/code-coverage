# -*- coding: utf-8 -*-
import subprocess
import sys
import threading

import pytest
import structlog

from code_coverage_bot.utils import run_check


def finished_log(logs):
    (entry,) = [e for e in logs if e["event"] == "Command finished"]
    return entry


def test_run_check_logs_memory():
    # Allocate and touch 200 MB, so they count in the resident memory.
    code = "b = bytearray(200 * 1024 * 1024); b[::4096] = b'x' * len(b[::4096])"
    with structlog.testing.capture_logs() as logs:
        run_check([sys.executable, "-c", code])

    entry = finished_log(logs)
    assert entry["command"] == sys.executable
    assert entry["exit"] == 0
    assert 200 <= entry["max_rss_mb"] < 400
    assert entry["duration"] >= 0


def test_run_check_large_output():
    # More than the capacity of a pipe on both stdout and stderr, which would
    # block if they weren't read while waiting for the process.
    code = "import sys; sys.stderr.write('e' * 10**6); sys.stdout.write('o' * 10**7)"
    assert run_check([sys.executable, "-c", code]) == b"o" * 10**7


def test_run_check_failure():
    with structlog.testing.capture_logs() as logs:
        with pytest.raises(Exception, match="failed with code: 3"):
            run_check([sys.executable, "-c", "import sys; sys.exit(3)"])

    assert finished_log(logs)["exit"] == 3


def test_run_check_doesnt_count_parent_memory():
    # Memory used by the bot itself must not be counted as used by the command.
    parent = bytearray(450 * 1024 * 1024)
    parent[::4096] = b"x" * len(parent[::4096])

    with structlog.testing.capture_logs() as logs:
        run_check([sys.executable, "-c", "pass"])

    assert finished_log(logs)["max_rss_mb"] < 100
    del parent


def test_run_check_closes_piped_stdin():
    # A command reading its input until EOF must not wait forever.
    result = {}
    thread = threading.Thread(
        target=lambda: result.update(
            output=run_check(
                [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"],
                stdin=subprocess.PIPE,
            )
        ),
        daemon=True,
    )
    thread.start()
    thread.join(timeout=60)
    assert not thread.is_alive()
    assert result["output"] == b"0\n"


def test_run_check_reader_errors():
    with pytest.raises(UnicodeDecodeError):
        run_check(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\xff')"],
            text=True,
        )


def test_run_check_missing_command():
    with pytest.raises(Exception, match="failed with code: 127"):
        run_check(["this-command-does-not-exist"])


def test_run_check_killed_by_signal():
    code = "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"
    with structlog.testing.capture_logs() as logs:
        with pytest.raises(Exception, match="failed with code: 137"):
            run_check([sys.executable, "-c", code])

    assert finished_log(logs)["exit"] == 137

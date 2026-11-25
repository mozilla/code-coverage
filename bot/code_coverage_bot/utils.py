# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import concurrent.futures
import functools
import os
import subprocess
import tempfile
import time
from compression import zstd
from zipfile import BadZipFile
from zipfile import is_zipfile

import requests
import structlog
import tenacity

log = structlog.get_logger(__name__)


@functools.cache
def _zstd_compression_options() -> dict[zstd.CompressionParameter, int]:
    # Use as many worker threads as available CPUs, if libzstd supports it.
    _, max_workers = zstd.CompressionParameter.nb_workers.bounds()
    workers = min(os.cpu_count() or 1, max_workers)
    if workers <= 1:
        return {}
    return {zstd.CompressionParameter.nb_workers: workers}


def zstd_compress(data: bytes) -> bytes:
    """
    Compress data with zstd, using multiple threads
    """
    return zstd.compress(data, options=_zstd_compression_options())


def hide_secrets(text, secrets):
    if type(text) is bytes:
        encode_secret, xxx = lambda x: bytes(x, encoding="utf-8"), b"XXX"
    elif type(text) is str:
        encode_secret, xxx = lambda x: x, "XXX"
    else:
        return text

    for secret in secrets:
        if type(secret) is not str:
            continue
        text = text.replace(encode_secret(secret), xxx)
    return text


def run_check(command, **kwargs):
    """
    Run a command through subprocess and check for output
    """
    assert isinstance(command, list)

    if len(command) == 0:
        raise Exception("Can't run an empty command.")

    _kwargs = dict(
        stdin=subprocess.DEVNULL,  # no interactions
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _kwargs.update(kwargs)

    log.info("Running command", command=" ".join(command), kwargs=_kwargs)

    # Measure the peak memory of the command with GNU time: measuring it from
    # here would also count the memory of this process, which the command is
    # forked from.
    with tempfile.NamedTemporaryFile(mode="r") as stats:
        start = time.monotonic()
        with subprocess.Popen(
            ["/usr/bin/time", "-q", "-f", "%M", "-o", stats.name, *command],
            **_kwargs,
        ) as proc:
            output, error = proc.communicate()
        duration = time.monotonic() - start
        max_rss_kb = stats.read().strip()

    log.info(
        "Command finished",
        command=command[0],
        exit=proc.returncode,
        duration=round(duration, 1),
        max_rss_mb=int(max_rss_kb) // 1024 if max_rss_kb.isdigit() else None,
    )

    if proc.returncode != 0:
        output = output and output.decode("utf-8") or ""
        error = error and error.decode("utf-8") or ""

        # Use error to send log to sentry
        log.error(
            f"Command failed with code: {proc.returncode}",
            exit=proc.returncode,
            command=" ".join(command),
            output=output.split("\n")[-1],
            error=error.split("\n")[-1],
        )
        print(f"Output:\n{output}")
        print(f"Error:\n{error}")

        raise Exception(f"`{command[0]}` failed with code: {proc.returncode}.")

    return output


class ThreadPoolExecutorResult(concurrent.futures.ThreadPoolExecutor):
    def __init__(self, *args, **kwargs):
        self.futures = []
        super(ThreadPoolExecutorResult, self).__init__(*args, **kwargs)

    def submit(self, *args, **kwargs):
        future = super(ThreadPoolExecutorResult, self).submit(*args, **kwargs)
        self.futures.append(future)
        return future

    def __exit__(self, *args):
        try:
            for future in concurrent.futures.as_completed(self.futures):
                future.result()
        except Exception as e:
            for future in self.futures:
                future.cancel()
            raise e
        return super(ThreadPoolExecutorResult, self).__exit__(*args)


def download_file(url: str, path: str) -> None:
    @tenacity.retry(
        reraise=True,
        wait=tenacity.wait_exponential(multiplier=1, min=16, max=64),
        stop=tenacity.stop_after_attempt(5),
    )
    def perform_download() -> None:
        r = requests.get(url, stream=True)
        r.raise_for_status()

        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1048576):
                f.write(chunk)

        if path.endswith(".zip") and not is_zipfile(path):
            raise BadZipFile("File is not a zip file")

    perform_download()

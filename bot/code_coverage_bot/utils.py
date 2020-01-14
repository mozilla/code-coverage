# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import concurrent.futures
import subprocess

import structlog

log = structlog.get_logger(__name__)


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

    log.debug("Running command", command=" ".join(command), kwargs=_kwargs)

    with subprocess.Popen(command, **_kwargs) as proc:
        output, error = proc.communicate()

    if proc.returncode != 0:
        output = output and output.decode("utf-8") or ""
        error = error and error.decode("utf-8") or ""

        # Use error to send log to sentry
        log.error(
            f"Command failed with code: {proc.returncode}",
            exit=proc.returncode,
            command=" ".join(command),
            output=output,
            error=error,
        )

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

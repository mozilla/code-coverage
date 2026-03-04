# -*- coding: utf-8 -*-
import os
import signal
import subprocess

import requests
import structlog

from typing import Iterable


logger = structlog.get_logger(__name__)


class HGMO(object):
    PID_FILE = "hgmo.pid"
    SERVER_ADDRESS = "http://localhost:8000"

    def __init__(self, repo_dir=None, server_address=None):
        assert (repo_dir is not None) ^ (server_address is not None)

        if server_address is not None:
            self.server_address = server_address
        else:
            self.server_address = HGMO.SERVER_ADDRESS
        self.repo_dir = repo_dir
        logger.info(
            "Configured HGMO server", address=self.server_address, dir=self.repo_dir
        )
        self.pid_file = os.path.join(os.getcwd(), HGMO.PID_FILE)

    def __get_pid(self):
        with open(self.pid_file, "r") as In:
            pid = In.read()
            return int(pid)

    def __enter__(self):
        if self.repo_dir is None:
            return self

        proc = subprocess.Popen(
            ["hg", "serve", "--hgmo", "--daemon", "--pid-file", self.pid_file],
            cwd=self.repo_dir,
            stderr=subprocess.STDOUT,
        )
        proc.wait()

        logger.info("hgmo is running", pid=self.__get_pid())

        return self

    def __exit__(self, type, value, traceback):
        if self.repo_dir is None:
            return

        pid = self.__get_pid()
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        os.remove(self.pid_file)
        logger.info("hgmo has been killed")

    def get_pushes(
        self,
        startID=None,
        endID=None,
        startDate=None,
        changeset=None,
        full=True,
        tipsonly=False,
    ):
        params = {"version": 2}

        if full:
            params["full"] = 1

        if tipsonly:
            params["tipsonly"] = 1

        if startID is not None:
            params["startID"] = startID

        if endID is not None:
            params["endID"] = endID

        if startDate is not None:
            params["startdate"] = startDate

        if changeset is not None:
            params["changeset"] = changeset

        r = requests.get(
            "{}/json-pushes".format(self.server_address),
            params=params,
            headers={"User-Agent": "code-coverage-bot"},
        )

        r.raise_for_status()
        return r.json()

    def get_automation_relevance_changesets(self, changeset):
        r = requests.get(
            "{}/json-automationrelevance/{}".format(
                self.server_address,
                changeset,
            ),
            headers={"User-Agent": "code-coverage-bot"},
        )
        r.raise_for_status()
        return r.json()["changesets"]


def iter_pushes(
    server_address: str,
) -> Iterable[tuple[int, dict]]:
    """Yield pushes from newest to oldest push-id."""
    start_id = None
    end_id = None

    with HGMO(server_address=server_address) as hgmo_server:
        while True:
            data = hgmo_server.get_pushes(
                startID=start_id, endID=end_id, full=False, tipsonly=True
            )
            pushes = data.get("pushes", {})

            if not pushes:
                return

            push_ids = sorted((int(push_id) for push_id in pushes.keys()), reverse=True)
            for push_id in push_ids:
                yield push_id, pushes[str(push_id)]

            oldest_seen = push_ids[-1]
            if oldest_seen <= 1:
                return

            # json-pushes treats startID as exclusive and endID as inclusive.
            end_id = oldest_seen - 1
            start_id = max(1, end_id - len(pushes))

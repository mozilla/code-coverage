# -*- coding: utf-8 -*-
import os
import signal
import subprocess

import requests
import structlog

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
        self, startID=None, startDate=None, changeset=None, full=True, tipsonly=False
    ):
        assert startID is not None or startDate is not None or changeset is not None

        params = {"version": 2}

        if full:
            params["full"] = 1

        if tipsonly:
            params["tipsonly"] = 1

        if startID is not None:
            params["startID"] = startID

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

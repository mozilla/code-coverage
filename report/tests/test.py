# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import errno
import os
import shutil
import tempfile
import unittest
from datetime import timedelta

from firefox_code_coverage import codecoverage


class Test(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for d in ["report", "ccov-artifacts", "lcov", "lcov-bin"]:
            shutil.rmtree(d, ignore_errors=True)

        for f in ["grcov", "grcov_ver", "output.info"]:
            try:
                os.remove(f)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise e

    def test(self):
        task_id = codecoverage.get_last_task()
        self.assertTrue(task_id)

        task_data = codecoverage.get_task_details(task_id)
        self.assertEqual(task_data["metadata"]["name"], "Gecko Decision Task")

        revision = task_data["payload"]["env"]["GECKO_HEAD_REV"]
        task_id_2 = codecoverage.get_task("mozilla-central", revision)
        self.assertEqual(task_id, task_id_2)

        artifacts = codecoverage.get_task_artifacts(task_id)
        chosen_artifact = None
        for artifact in artifacts:
            if artifact["name"] == "public/target-tasks.json":
                chosen_artifact = artifact
        self.assertIsNotNone(chosen_artifact)

        tasks = codecoverage.get_tasks_in_group(task_data["taskGroupId"])
        self.assertIsInstance(tasks, list)

        try:
            os.mkdir("ccov-artifacts")
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise e

        codecoverage.download_artifact(task_id, chosen_artifact, "ccov-artifacts")
        self.assertTrue(os.path.exists("ccov-artifacts/%s_target-tasks.json" % task_id))
        os.remove("ccov-artifacts/%s_target-tasks.json" % task_id)

        artifact_paths = codecoverage.download_coverage_artifacts(
            task_id, "gtest-1proc", None, "ccov-artifacts"
        )
        self.assertEqual(
            len([a for a in os.listdir("ccov-artifacts") if "grcov" in a]), 2
        )
        self.assertEqual(
            len([a for a in os.listdir("ccov-artifacts") if "jsvm" in a]), 2
        )
        self.assertEqual(len([a for a in artifact_paths if "grcov" in a]), 2)
        self.assertEqual(len([a for a in artifact_paths if "jsvm" in a]), 2)

        artifact_paths = codecoverage.download_coverage_artifacts(
            task_id, "cppunit-1proc", None, "ccov-artifacts"
        )
        self.assertEqual(
            len([a for a in os.listdir("ccov-artifacts") if "grcov" in a]), 4
        )
        self.assertEqual(
            len([a for a in os.listdir("ccov-artifacts") if "jsvm" in a]), 4
        )
        self.assertEqual(len([a for a in artifact_paths if "grcov" in a]), 2)
        self.assertEqual(len([a for a in artifact_paths if "jsvm" in a]), 2)

        codecoverage.download_grcov()
        codecoverage.generate_report(
            "./grcov", "lcov", None, "output.info", artifact_paths
        )
        self.assertTrue(os.path.exists("output.info"))

        codecoverage.generate_report(
            "./grcov", "html", None, "report_html", artifact_paths
        )
        self.assertTrue(os.path.isdir("report_html"))
        self.assertTrue(os.path.exists("report_html/index.html"))

    def test_suite_name_from_task_name(self):
        cases = [
            ("test-linux1804-64-ccov/opt-cppunit-1proc", "cppunit"),
            ("test-linux64-ccov/opt-gtest", "gtest"),
            ("test-linux64-ccov/opt-jsreftest-1", "jsreftest"),
            (
                "test-linux64-ccov/opt-mochitest-devtools-chrome-e10s-10",
                "mochitest-devtools-chrome",
            ),
            ("test-linux64-ccov/opt-mochitest-clipboard", "mochitest-clipboard"),
            ("test-linux64-ccov/opt-reftest-no-accel-e10s-5", "reftest-no-accel"),
            ("test-linux64-ccov/opt-mochitest-5", "mochitest"),
            ("test-windows10-64-ccov/debug-mochitest-5", "mochitest"),
            ("test-windows10-64-ccov/debug-cppunit", "cppunit"),
            ("build-linux64-ccov/opt", "build"),
            ("build-android-test-ccov/opt", "build"),
            ("build-win64-ccov/debug", "build"),
        ]
        for c in cases:
            self.assertEqual(codecoverage.get_suite(c[0]), c[1])

    def test_download_grcov(self):
        codecoverage.download_grcov()
        self.assertTrue(os.path.exists("grcov"))
        self.assertTrue(os.path.exists("grcov_ver"))

        with open("grcov_ver", "r") as f:
            ver = f.read()

        # grcov is downloaded again if the executable doesn't exist.
        os.remove("grcov")
        codecoverage.download_grcov()
        self.assertTrue(os.path.exists("grcov"))
        self.assertTrue(os.path.exists("grcov_ver"))

        # grcov isn't downloaded again if the executable exists and the version is the same.
        with open("grcov", "w") as f:
            f.write("prova")

        codecoverage.download_grcov()

        with open("grcov", "r") as f:
            self.assertEqual("prova", f.read())

        # grcov is overwritten if the version changes.
        with open("grcov_ver", "w") as f:
            f.write("v0.0.0")

        codecoverage.download_grcov()

        self.assertTrue(os.path.getsize("grcov") > 5)
        with open("grcov_ver", "r") as f:
            self.assertEqual(ver, f.read())

    def test_upload_report(self):

        # Can only run on Taskcluster
        if "TASK_ID" not in os.environ:
            return

        _dir = tempfile.mkdtemp()

        with open(os.path.join(_dir, "report.html"), "w") as f:
            f.write("<strong>This is a test</strong>")

        codecoverage.upload_html_report(str(_dir), ttl=timedelta(days=1))


if __name__ == "__main__":
    unittest.main()

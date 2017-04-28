# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
import errno
import os

import codecoverage


class Test(unittest.TestCase):
    def test(self):
        task_id = codecoverage.get_last_task()
        self.assertTrue(task_id)

        task_data = codecoverage.get_task_details(task_id)
        self.assertEqual(task_data['metadata']['name'], 'build-linux64-ccov/opt')

        revision = task_data['payload']['env']['GECKO_HEAD_REV']
        task_id_2 = codecoverage.get_task('mozilla-central', revision)
        self.assertEqual(task_id, task_id_2)

        artifacts = codecoverage.get_task_artifacts(task_id)
        chosen_artifact = None
        for artifact in artifacts:
            if artifact['name'] == 'public/build/target.txt':
                chosen_artifact = artifact
        self.assertIsNotNone(chosen_artifact)

        tasks = codecoverage.get_tasks_in_group(task_data['taskGroupId'])
        self.assertIsInstance(tasks, list)

        try:
            os.mkdir('ccov-artifacts')
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise e

        codecoverage.download_artifact(task_id, chosen_artifact)
        self.assertTrue(os.path.exists('ccov-artifacts/%s_target.txt' % task_id))

    def test_suite_name_from_task_name(self):
        cases = [
            ('test-linux64-ccov/opt-gtest', 'gtest'),
            ('test-linux64-ccov/opt-jsreftest-1', 'jsreftest'),
            ('test-linux64-ccov/opt-mochitest-devtools-chrome-e10s-10', 'mochitest-devtools-chrome'),
            ('test-linux64-ccov/opt-mochitest-clipboard', 'mochitest-clipboard'),
            ('test-linux64-ccov/opt-reftest-no-accel-e10s-5', 'reftest-no-accel'),
            ('test-linux64-ccov/opt-mochitest-5', 'mochitest'),
        ]
        for c in cases:
            self.assertEqual(c[0], c[1])

if __name__ == '__main__':
    unittest.main()

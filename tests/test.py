# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
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

        codecoverage.download_artifact(task_id, chosen_artifact)
        self.assertTrue(os.path.exists('ccov-artifacts/%s_target.txt' % task_id))


if __name__ == '__main__':
    unittest.main()

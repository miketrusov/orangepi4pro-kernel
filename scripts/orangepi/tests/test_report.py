# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reporter', Path(__file__).parents[1] / 'report-update.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class IncidentTests(unittest.TestCase):
    @patch.object(reporter, 'api')
    def test_failure_opens_one_issue_and_repeat_does_not_comment(self, api):
        api.return_value = []
        reporter.incident('failure', 'details', True)
        api.assert_any_call('/issues', {'title': 'failure', 'body': 'details'})
        api.reset_mock()
        api.return_value = [{'title': 'failure', 'body': 'details', 'number': 7}]
        reporter.incident('failure', 'details', True)
        self.assertEqual(api.call_count, 1)

    @patch.object(reporter, 'api')
    def test_changed_failure_updates_existing_issue(self, api):
        api.return_value = [{'title': 'failure', 'body': 'old', 'number': 7}]
        reporter.incident('failure', 'new details', True)
        api.assert_any_call('/issues/7', {'body': 'new details'}, 'PATCH')
        self.assertEqual(api.call_count, 2)

    @patch.object(reporter, 'api')
    def test_recovery_closes_existing_issue_only(self, api):
        api.return_value = [{'title': 'failure', 'body': 'old', 'number': 7}]
        reporter.incident('failure', 'green run', False)
        api.assert_any_call('/issues/7', {'state': 'closed'}, 'PATCH')
        api.reset_mock()
        api.return_value = []
        reporter.incident('failure', 'green run', False)
        self.assertEqual(api.call_count, 1)


if __name__ == '__main__':
    unittest.main()

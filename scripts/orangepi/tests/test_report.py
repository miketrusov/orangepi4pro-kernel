# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import io
import os
from pathlib import Path
import unittest
import urllib.error
from unittest.mock import patch, mock_open

spec = importlib.util.spec_from_file_location('reporter', Path(__file__).parents[1] / 'report-update.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class IncidentTests(unittest.TestCase):
    @patch.object(reporter, 'incident')
    @patch.object(reporter, 'api')
    def test_publication_failure_alerts_without_misreporting_compilation(self, api, incident):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_RUN_ID': '123',
                'PREPARE_RESULT': 'success', 'BUILD_RESULT': 'success', 'PUBLISH_RESULT': 'failure',
                'SOURCE_SHA': 'a' * 40, 'CANDIDATE_BRANCH': '', 'VENDOR_HEAD': '',
                'GITHUB_STEP_SUMMARY': '/unused'}, clear=True), patch('builtins.open', mock_open()):
            reporter.main()
        self.assertEqual(api.call_args.args[1]['conclusion'], 'success')
        self.assertTrue(incident.call_args.args[2])

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

class PullRequestPolicyTests(unittest.TestCase):
    @patch.object(reporter, 'incident')
    @patch.object(reporter, 'api')
    def test_policy_denial_reports_branch_without_changing_permissions(self, api, incident):
        error = urllib.error.HTTPError('https://api.github.com', 403, 'Forbidden', {},
            io.BytesIO(b'{"message":"GitHub Actions is not permitted to create or approve pull requests."}'))
        api.side_effect = [[], error]
        reporter.publish_pr('owner/repo', 'codex/update-v6.18.2-123456789abc', 'v6.18.2', 'candidate')
        self.assertTrue(incident.call_args.args[2])
        self.assertIn('/compare/', incident.call_args.args[1])
        self.assertEqual(api.call_count, 2)

    @patch.object(reporter, 'api')
    def test_unrelated_api_denial_remains_a_reporting_failure(self, api):
        error = urllib.error.HTTPError('https://api.github.com', 403, 'Forbidden', {},
                                      io.BytesIO(b'{"message":"API rate limit exceeded"}'))
        api.side_effect = [[], error]
        with self.assertRaises(urllib.error.HTTPError):
            reporter.publish_pr('owner/repo', 'codex/update-v6.18.2-123456789abc', 'v6.18.2', 'candidate')



if __name__ == '__main__':
    unittest.main()

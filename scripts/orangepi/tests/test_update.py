# SPDX-License-Identifier: GPL-2.0-only
"""Exercise release trust boundaries and actual Git merge/conflict behavior."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('updater', Path(__file__).parents[1] / 'prepare-update.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class ReleaseTests(unittest.TestCase):
    def test_numeric_release_selection_excludes_prereleases(self):
        refs = '\n'.join(f"{'a'*40} refs/tags/{tag}{suffix}"
                         for tag in ['v6.18.9', 'v6.18.10', 'v6.18.99-rc1', 'v6.19.1']
                         for suffix in ['', '^{}'])
        self.assertEqual(updater.newest_release(refs)['tag'], 'v6.18.10')

    def test_lightweight_latest_tag_is_rejected(self):
        with self.assertRaises(ValueError):
            updater.newest_release('a'*40 + ' refs/tags/v6.18.11')

    def test_only_valid_signature_from_pinned_primary_or_subkey_is_accepted(self):
        primary = sorted(updater.SIGNERS)[0]
        self.assertTrue(updater.trusted_signature(f'[GNUPG:] VALIDSIG {primary} rest'))
        self.assertTrue(updater.trusted_signature(f'[GNUPG:] VALIDSIG unknown rest {primary}'))
        self.assertFalse(updater.trusted_signature(f'[GNUPG:] GOODSIG {primary}'))
        self.assertFalse(updater.trusted_signature('[GNUPG:] VALIDSIG untrusted rest'))


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.git('init', '-q', '-b', 'port')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        (self.repo / 'upstream.c').write_text('original\n')
        self.commit('base')
        self.base = self.git('rev-parse', 'HEAD')
        (self.repo / 'scripts/orangepi').mkdir(parents=True)
        self.source = {'upstream': {'tag': 'v6.18.1', 'commit': self.base},
                       'board_support': {'commit': 'pinned'}}
        self.manifest = self.repo / 'scripts/orangepi/sources.json'
        self.manifest.write_text(json.dumps(self.source))
        (self.repo / 'bsp.c').write_text('board support\n')
        self.commit('port')

    def git(self, *args):
        return updater.git(self.repo, *args)

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)

    def release(self):
        self.git('switch', '-qc', 'upstream', self.base)
        (self.repo / 'upstream.c').write_text('stable fix\n')
        self.commit('stable update')
        release = self.git('rev-parse', 'HEAD')
        self.git('switch', '-q', 'port')
        return release

    def test_merge_preserves_bsp_and_records_upstream(self):
        release = self.release()
        old = self.git('rev-parse', 'HEAD')
        head = updater.merge_candidate(self.repo, release, 'v6.18.2', self.source)
        self.assertEqual(self.git('show', '-s', '--format=%P', head).split(), [old, release])
        self.assertEqual((self.repo / 'bsp.c').read_text(), 'board support\n')
        self.assertEqual((self.repo / 'upstream.c').read_text(), 'stable fix\n')
        self.assertEqual(json.loads(self.manifest.read_text())['upstream']['commit'], release)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_conflict_aborts_without_changing_head_or_manifest(self):
        release = self.release()
        (self.repo / 'upstream.c').write_text('conflicting port fix\n')
        self.commit('port fix')
        old, manifest = self.git('rev-parse', 'HEAD'), self.manifest.read_bytes()
        with self.assertRaises(subprocess.CalledProcessError):
            updater.merge_candidate(self.repo, release, 'v6.18.2', self.source)
        self.assertEqual(self.git('rev-parse', 'HEAD'), old)
        self.assertEqual(self.manifest.read_bytes(), manifest)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_unrelated_upstream_history_is_rejected(self):
        self.git('switch', '--orphan', 'unrelated')
        (self.repo / 'foreign').write_text('different tree')
        self.commit('unrelated')
        foreign = self.git('rev-parse', 'HEAD')
        self.git('switch', '-q', 'port')
        old = self.git('rev-parse', 'HEAD')
        with self.assertRaises(subprocess.CalledProcessError):
            updater.merge_candidate(self.repo, foreign, 'v6.18.2', self.source)
        self.assertEqual(self.git('rev-parse', 'HEAD'), old)


if __name__ == '__main__':
    unittest.main()

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('publish', Path(__file__).resolve().parents[1] / 'publish-update.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class Publication(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.art = self.root / 'artifacts'
        self.art.mkdir()
        self.source = 'a' * 40
        self.watchdog = 'b' * 64
        for name in p.FILES:
            if name != 'manifest.json':
                (self.art / name).write_bytes(name.encode())
        (self.art / '.config').write_text(''.join('CONFIG_' + s + '=y\n' for s in ('AW_WATCHDOG', 'WATCHDOG_SYSFS', 'WATCHDOG_HANDLE_BOOT_ENABLED')) + 'CONFIG_WATCHDOG_OPEN_TIMEOUT=120\n')
        self.manifest = {'source_commit': self.source, 'kernel_release': '6.18.62-opi4pro-xunlong1-g' + self.source[:12],
                         'outputs': {f.name: p.sha(f) for f in self.art.iterdir()}}
        self.save()

    def save(self):
        (self.art / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_deterministic_bundle_and_external_archive_digest(self):
        first = p.bundle(self.art, self.source, self.watchdog, self.root / 'one')
        second = p.bundle(self.art, self.source, self.watchdog, self.root / 'two')
        self.assertEqual(first, second)
        self.assertEqual((self.root / 'one/update.tar.gz').read_bytes(), (self.root / 'two/update.tar.gz').read_bytes())
        self.assertEqual(first['archive_sha256'], p.sha(self.root / 'one/update.tar.gz'))

    def test_source_and_vermagic_identity_are_required(self):
        for key, value in [('source_commit', 'c' * 40), ('kernel_release', '6.18.62-opi4pro-xunlong1-gwrong')]:
            original = self.manifest[key]
            self.manifest[key] = value
            self.save()
            with self.assertRaises(ValueError):
                p.bundle(self.art, self.source, self.watchdog, self.root / key)
            self.manifest[key] = original

    def test_corrupt_asset_never_published(self):
        (self.art / 'Image').write_bytes(b'corruption')
        with self.assertRaisesRegex(ValueError, 'checksum differs'):
            p.bundle(self.art, self.source, self.watchdog, self.root / 'out')

    def test_unbounded_takeover_is_rejected(self):
        (self.art / '.config').write_text((self.art / '.config').read_text().replace('TIMEOUT=120', 'TIMEOUT=0'))
        self.manifest['outputs']['.config'] = p.sha(self.art / '.config')
        self.save()
        with self.assertRaisesRegex(ValueError, 'Unbounded'):
            p.bundle(self.art, self.source, self.watchdog, self.root / 'out')

if __name__ == '__main__':
    unittest.main()

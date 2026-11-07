#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Publish immutable, compile-tested 6.18 candidates from the trusted workflow."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

FILES = ('Image', 'sun60i-a733-orangepi-4-pro.dtb', '.config', 'System.map', 'modules.tar.gz', 'manifest.json', 'sources.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle(artifacts, source, watchdog, output):
    if not re.fullmatch('[0-9a-f]{40}', source) or not re.fullmatch('[0-9a-f]{64}', watchdog):
        raise ValueError('Invalid release source/watchdog identity')
    manifest = json.loads((artifacts / 'manifest.json').read_text())
    release = manifest['kernel_release']
    if manifest['source_commit'] != source or not re.fullmatch(r'6\.18\.\d+-opi4pro-xunlong1-g' + source[:12], release):
        raise ValueError('Artifact identity differs from the successful exact-SHA build')
    for name, checksum in manifest['outputs'].items():
        if Path(name).name != name or sha(artifacts / name) != checksum:
            raise ValueError('Artifact checksum differs: ' + name)
    config = (artifacts / '.config').read_text()
    for symbol in ('AW_WATCHDOG', 'WATCHDOG_SYSFS', 'WATCHDOG_HANDLE_BOOT_ENABLED'):
        if 'CONFIG_' + symbol + '=y\n' not in config:
            raise ValueError('Unqualified watchdog config: ' + symbol)
    if 'CONFIG_WATCHDOG_OPEN_TIMEOUT=120\n' not in config:
        raise ValueError('Unbounded watchdog takeover')
    if (artifacts / 'Image').stat().st_size >= 0x2200000:
        raise ValueError('Kernel overlaps firmware scratch memory')
    identity = {'schema': 1, 'channel': '6.18', 'source_commit': source, 'kernel_release': release,
                'watchdog_sha256': watchdog, 'boot_qualified': False,
                'qualification': 'Compile tested; each board must pass its bounded trial before promotion.'}
    output.mkdir(parents=True, exist_ok=True)
    inner = (json.dumps(identity, sort_keys=True, indent=2) + '\n').encode()
    with (output / 'update.tar.gz').open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as zipped, tarfile.open(fileobj=zipped, mode='w') as tar:
        for name in sorted((*FILES, 'update.json')):
            contents = inner if name == 'update.json' else (artifacts / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime, info.uid, info.gid = len(contents), 0o644, 0, 0, 0
            tar.addfile(info, io.BytesIO(contents))
    identity['archive_sha256'] = sha(output / 'update.tar.gz')
    (output / 'update.json').write_text(json.dumps(identity, sort_keys=True, indent=2) + '\n')
    return identity


def gh(*args, json_output=False):
    output = subprocess.check_output(['gh', *args], text=True)
    return json.loads(output) if json_output else output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--bundle-only', action='store_true')
    a = p.parse_args()
    repo = os.environ['GITHUB_REPOSITORY']
    if repo != 'miketrusov/orangepi4pro-kernel' or os.environ.get('GITHUB_REF') != 'refs/heads/orangepi-6.18.y':
        raise ValueError('Release publication is restricted to the trusted default workflow')
    # Read the exact built commit, not the trusted workflow revision, for driver identity.
    driver = subprocess.check_output(['git', 'show', a.source + ':bsp/drivers/watchdog/sunxi_wdt.c'])
    with tempfile.TemporaryDirectory(prefix='opi-release-') as temporary:
        folder = Path(temporary)
        identity = bundle(a.artifacts, a.source, hashlib.sha256(driver).hexdigest(), folder)
        if a.bundle_only:
            print(json.dumps(identity))
            return
        version = identity['kernel_release'].split('-')[0]
        tag = 'opi4pro-v' + version + '-' + a.source[:12]
        pages = gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100', json_output=True)
        releases = [release for page in pages for release in page]
        existing = next((r for r in releases if r['tag_name'] == tag), None)
        if existing and not existing['draft']:
            old = gh('release', 'view', tag, '--repo', repo, '--json', 'assets', json_output=True)
            with tempfile.TemporaryDirectory() as check:
                gh('release', 'download', tag, '--repo', repo, '--pattern', 'update.json', '--dir', check)
                if json.loads((Path(check) / 'update.json').read_text()) != identity:
                    raise ValueError('Refusing to replace an existing candidate release')
            if not {'update.tar.gz', 'update.json', 'source.tar.gz'} <= {asset['name'] for asset in old['assets']}:
                raise ValueError('Existing release is incomplete')
            print('Existing immutable release verified: ' + tag)
            return
        notes = folder / 'notes.md'
        notes.write_text(f'Linux {version} LTS for Orange Pi 4 Pro headless NVMe servers.\n\n'
                         f'Exact source: `{a.source}`. This candidate passed compilation, not a board boot test. '
                         'The board updater must verify it, boot once under the hardware watchdog, and promote only after health passes. '
                         'eMMC remains disabled.\n\n'
                         'The release includes corresponding source and build/debug evidence. '
                         'Shared root data is not covered by kernel rollback.\n')
        if existing is None:
            gh('release', 'create', tag, '--repo', repo, '--target', a.source, '--draft', '--prerelease',
               '--title', f'Orange Pi 4 Pro Linux {version} candidate {a.source[:12]}', '--notes-file', str(notes))
        files = [folder / 'update.tar.gz', folder / 'update.json'] + [a.artifacts / name for name in
                 ('source.tar.gz', 'manifest.json', 'SHA256SUMS', 'build.log', 'builder.Dockerfile', 'builder-packages.tsv', 'vmlinux', 'Module.symvers')]
        gh('release', 'upload', tag, '--repo', repo, '--clobber', *map(str, files))
        gh('release', 'edit', tag, '--repo', repo, '--draft=false', '--prerelease', '--latest=false')
        print('Published candidate: ' + tag)

if __name__ == '__main__':
    main()

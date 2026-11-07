#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare a reviewable stable merge; never resolve conflicts or deploy it."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

SIGNERS = {'647F28654894E3BD457199BE38DBBDC86092693E',
           'E27E5D8A3403A2EF66873BBCDEA66FF797772CDC'}
UPSTREAM = 'https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git'
VENDOR = 'https://github.com/orangepi-xunlong/linux-orangepi'
VENDOR_BRANCH = 'refs/heads/orange-pi-6.6-sun60iw2'


def git(repo, *args, env=None):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, env=env,
                                   timeout=600).strip()


def network_git(repo, *args):
    for attempt in range(2):
        try:
            return git(repo, *args)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt:
                raise
            time.sleep(5)


def newest_release(refs):
    tags = {}
    for line in refs.splitlines():
        oid, ref = line.split()
        if not re.fullmatch(r'[0-9a-f]{40}', oid):
            raise ValueError('Unexpected upstream object ID')
        match = re.fullmatch(r'refs/tags/(v6\.18\.(\d+))(\^\{\})?', ref)
        if match:
            tag, number, peeled = match.groups()
            tags.setdefault(int(number), {'tag': tag})['commit' if peeled else 'tag_object'] = oid
    latest = tags[max(tags)]
    if not {'commit', 'tag_object'} <= latest.keys():
        raise ValueError('Latest release must be an annotated tag')
    return latest


def trusted_signature(status):
    return any(line.startswith('[GNUPG:] VALIDSIG ') and
               (line.split()[2] in SIGNERS or line.split()[-1] in SIGNERS)
               for line in status.splitlines())


def merge_candidate(repo, commit, tag, source):
    """A conflict leaves HEAD/manifest unchanged and the merge aborted."""
    previous = source['upstream']['commit']
    git(repo, 'merge-base', '--is-ancestor', previous, 'HEAD')
    git(repo, 'merge-base', '--is-ancestor', previous, commit)
    epoch = max(int(git(repo, 'show', '-s', '--format=%ct', ref))
                for ref in ['HEAD', commit]) + 1
    env = dict(os.environ, GIT_AUTHOR_NAME='Orange Pi kernel updater',
               GIT_AUTHOR_EMAIL='kernel-updater@users.noreply.github.com',
               GIT_COMMITTER_NAME='Orange Pi kernel updater',
               GIT_COMMITTER_EMAIL='kernel-updater@users.noreply.github.com',
               GIT_AUTHOR_DATE=f'@{epoch} +0000', GIT_COMMITTER_DATE=f'@{epoch} +0000')
    try:
        git(repo, 'merge', '--no-ff', '--no-commit', commit, env=env)
        source['upstream'].update(tag=tag, commit=commit)
        source['status'] = 'candidate; CI and hardware qualification are separate'
        path = repo / 'scripts/orangepi/sources.json'
        path.write_text(json.dumps(source, indent=2) + '\n')
        git(repo, 'add', str(path))
        git(repo, 'commit', '-m', f'Merge Linux {tag} for Orange Pi 4 Pro', env=env)
    except BaseException:
        subprocess.run(['git', '-C', str(repo), 'merge', '--abort'], check=False)
        raise
    return git(repo, 'rev-parse', 'HEAD')


def output(name, value):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(f'{name}={value}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo = args.repository.resolve()
    if git(repo, 'status', '--porcelain'):
        raise RuntimeError('Prepare an update only in a clean checkout')
    source = json.loads((repo / 'scripts/orangepi/sources.json').read_text())
    if source['upstream']['url'] != UPSTREAM or source['board_support']['url'] != VENDOR:
        raise RuntimeError('Source URLs changed; require an explicit updater review')
    current = git(repo, 'rev-parse', 'HEAD')
    latest = newest_release(network_git(repo, 'ls-remote', '--tags', UPSTREAM, 'refs/tags/v6.18.*'))
    output('target_tag', latest['tag'])
    output('previous_tag', source['upstream']['tag'])
    # Fetch exactly the resolved tag object; reject movement between discovery/fetch.
    network_git(repo, 'fetch', '--no-tags', UPSTREAM, latest['tag_object'])
    if git(repo, 'rev-parse', 'FETCH_HEAD^{commit}') != latest['commit']:
        raise RuntimeError('Fetched tag differs from resolved release')
    with tempfile.TemporaryDirectory(prefix='opi-stable-keyring-') as home:
        os.chmod(home, 0o700)
        env = dict(os.environ, GNUPGHOME=home)
        subprocess.run(['gpg', '--batch', '--import', str(Path(__file__).parent / 'ci/stable-maintainers.asc')],
                       env=env, check=True, capture_output=True)
        signature = subprocess.run(['git', '-C', str(repo), 'verify-tag', '--raw', 'FETCH_HEAD'],
                                   env=env, text=True, capture_output=True)
        if signature.returncode or not trusted_signature(signature.stderr):
            raise RuntimeError('Stable release signature is missing, invalid or untrusted')
    vendor = network_git(repo, 'ls-remote', VENDOR, VENDOR_BRANCH).split()[0]
    if not re.fullmatch(r'[0-9a-f]{40}', vendor):
        raise RuntimeError('Unexpected vendor object ID')
    output('vendor_head', vendor)
    output('vendor_pinned', source['board_support']['commit'])
    branch = ''
    if latest['commit'] != source['upstream']['commit']:
        if int(latest['tag'].rsplit('.', 1)[1]) <= int(source['upstream']['tag'].rsplit('.', 1)[1]):
            raise RuntimeError('Reject a stable release rollback or moved existing tag')
        branch = f"codex/update-{latest['tag']}-{current[:12]}"
        git(repo, 'switch', '-c', branch)
        current = merge_candidate(repo, latest['commit'], latest['tag'], source)
    output('source_sha', current)
    output('branch', branch)
    print(json.dumps(dict(latest, source_sha=current, branch=branch,
                          vendor_head=vendor, vendor_pinned=source['board_support']['commit'])))


if __name__ == '__main__':
    main()

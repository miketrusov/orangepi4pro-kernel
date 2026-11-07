#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Report an exact candidate build using trusted workflow context only."""
import json
import os
import re
import urllib.error
import urllib.request


def api(path, body=None, method=None):
    request = urllib.request.Request('https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + path,
        data=None if body is None else json.dumps(body).encode(), method=method,
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Content-Type': 'application/json',
                 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def incident(title, body, failed):
    existing, page = None, 1
    while True:
        items = api(f'/issues?state=open&per_page=100&page={page}')
        existing = next((item for item in items
                         if item['title'] == title and 'pull_request' not in item), None)
        if existing or len(items) < 100:
            break
        page += 1
    if failed and existing is None:
        api('/issues', {'title': title, 'body': body})
    elif failed and existing['body'] != body:
        # Keep one issue; updating its body does not post repeated @mentions.
        api('/issues/' + str(existing['number']), {'body': body}, 'PATCH')
    elif not failed and existing:
        api('/issues/' + str(existing['number']) + '/comments', {'body': 'Recovered. ' + body})
        api('/issues/' + str(existing['number']), {'state': 'closed'}, 'PATCH')


def publish_pr(repo, branch, tag, body):
    title = '[kernel CI] Candidate ready; draft PR creation unavailable'
    pulls = api('/pulls?state=open&head=' + repo.split('/')[0] + ':' + branch)
    try:
        if pulls:
            api('/pulls/' + str(pulls[0]['number']), {'body': body}, 'PATCH')
        else:
            api('/pulls', {'title': f'Update Orange Pi 4 Pro to Linux {tag}', 'head': branch,
                           'base': 'orangepi-6.18.y', 'body': body, 'draft': True})
    except urllib.error.HTTPError as error:
        message = error.read().decode(errors='replace')
        if error.code != 403 or 'not permitted to create or approve pull requests' not in message:
            raise
        # Respect repository policy; no settings changes, PAT or approval bypass.
        compare = f'https://github.com/{repo}/compare/orangepi-6.18.y...{branch}'
        incident(title, body + '\n\nRepository policy prevented automatic PR creation. '
                 f'[Review the candidate branch and create a PR manually]({compare}).', True)
    else:
        incident(title, body, False)


def main():
    env = os.environ
    repo, run = env['GITHUB_REPOSITORY'], env['GITHUB_RUN_ID']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not run.isdecimal():
        raise ValueError('Unexpected repository/run identity')
    link = f'https://github.com/{repo}/actions/runs/{run}'
    okay = env['PREPARE_RESULT'] == env['BUILD_RESULT'] == 'success'
    sha, branch, tag = env.get('SOURCE_SHA', ''), env.get('CANDIDATE_BRANCH', ''), env.get('TARGET_TAG', '')
    if sha and not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Invalid candidate identity')
    if branch and not re.fullmatch(r'codex/update-v6\.18\.\d+-[0-9a-f]{12}', branch):
        raise ValueError('Invalid candidate branch')
    details = (f"Upstream: `{env.get('PREVIOUS_TAG', '')}` → `{tag}`.\n\n"
               f"Port base: `{env.get('BASE_SHA', '')}`; upstream target: `{env.get('TARGET_SHA', '')}`.\n\n"
               f"Candidate: `{sha or 'not created'}`.\n\n"
               f"Prepare: **{env['PREPARE_RESULT']}**; build: **{env['BUILD_RESULT']}**.\n\n"
               f"[Run, first error and downloadable artifacts]({link}).\n\n"
               'No board installation or kernel promotion was attempted.')
    if sha:
        api('/check-runs', {'name': 'Headless candidate build', 'head_sha': sha,
            'status': 'completed', 'conclusion': 'success' if okay else 'failure',
            'details_url': link, 'output': {'title': 'Compile-only candidate result', 'summary': details}})
    incident('[kernel CI] Weekly 6.18 update needs attention', details, not okay)
    vendor, pinned = env.get('VENDOR_HEAD', ''), env.get('VENDOR_PINNED', '')
    if vendor and pinned:
        incident('[kernel CI] Vendor BSP changed; review required',
                 f'Pinned BSP: `{pinned}`.\n\nObserved vendor head: `{vendor}`.\n\n'
                 'The updater does not import vendor changes automatically.', vendor != pinned)
    if okay and branch:
        body = (f'Merge the complete signed upstream stable release into the existing port.\n\n{details}\n\n'
                'The BSP remains pinned. eMMC remains disabled because no test hardware is available.\n\n'
                'Before merging/promoting: review the diff and qualify this exact artifact on the board '
                'with the preserved recovery kernel and an active supervisor. A build is not a boot test.')
        publish_pr(repo, branch, tag, body)
    with open(env['GITHUB_STEP_SUMMARY'], 'a') as stream:
        stream.write(details + '\n')


if __name__ == '__main__':
    main()

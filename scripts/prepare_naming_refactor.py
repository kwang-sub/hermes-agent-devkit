#!/usr/bin/env python3
"""Temporary isolated branch workbench; publishes Git objects only, never refs."""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path.cwd()
EXPECTED_TREE = '83f16b65a841f05f5ea765f1d07f48363c17d0b9'
PATCH_SHA256 = 'e2890fbdc3ec2afc0b4f9b11a9c2ec41ccfb9a237acc3ad5e93e63de4019d286'
TEMP_FILES = ['.github/workflows/naming-refactor-workbench.yml', 'scripts/prepare_naming_refactor.py'] + [f'scripts/.naming-patch-{i}' for i in range(1, 6)]


def git(*args, raw=False):
    result = subprocess.check_output(['git', *args], cwd=ROOT)
    return result if raw else result.decode().strip()


def assert_context():
    assert os.environ.get('GITHUB_REPOSITORY') == 'kwang-sub/hermes-agent-devkit'
    assert os.environ.get('GITHUB_REF') == 'refs/heads/refactor/devkit-neutral-names'
    assert git('rev-parse', 'HEAD') == os.environ['GITHUB_SHA']


def transform():
    pairs=[
     ('custom-skills/lite','custom-skills/core'),
     ('dev-lite-session','dev-session'),('dev-lite-review','dev-review'),
     ('lite_default_profile','devkit_default_profile'),
     ('check_lite_repository','check_devkit_repository'),
     ('lite_image_fixture','devkit_image_fixture'),('smoke_lite_image','smoke_devkit_image'),
     ('test_lite_','test_devkit_'),
     ('018-devkit-lite-init','018-devkit-init'),
     ('/run/devkit-lite-ready','/run/devkit-ready'),
     ('init-lite.ps1','init-devkit.ps1'),
     ('hermes-lite-migration.md','devkit-migration.md'),
     ('lite-kanban-policy.md','kanban-policy.md'),
     ('lite-session-approval.md','session-approval.md'),
     ('lite-validation.md','validation-history.md'),
     ('lite-development-contract.md','development-contract.md'),
     ('lite-approval-ui.yml','approval-ui.yml'),
     ('lite-regression-results','devkit-regression-results'),
     ('lite-approval-ui-','devkit-approval-ui-'),
     ('devkit-lite','devkit-state'),
     ('lite/AGENTS.md','core/AGENTS.md'),
     ('Hermes Agent DevKit — Lite','Hermes Agent DevKit'),
     ('Hermes Lite','Hermes DevKit'),
     ('LiteSessionApprovalContractTests','SessionApprovalContractTests'),
     ('LiteStatus','DevKitStatus'),('LiteEnv','DevKitEnv'),('Lite configuration','DevKit configuration'),
    ]
    # Preserve these compatibility contracts; they are not names of active modes.
    protected=['lite_change_approval_v1','updatekit_lite.sh','updatekit_lite.ps1']
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    for rel in filter(None,paths):
     if rel in TEMP_FILES: continue
     p=ROOT/rel
     data=p.read_bytes()
     try: text=data.decode('utf-8')
     except UnicodeDecodeError: continue
     for i,key in enumerate(protected):text=text.replace(key,f'@@PRESERVED_{i}@@')
     for old,new in pairs:text=text.replace(old,new)
     # Word-sized matches never change SQLite, literal_eval, Literal, or theme names.
     text=re.sub(r'(?<![A-Za-z])Lite(?![a-z])','DevKit',text)
     text=re.sub(r'(?<![A-Za-z])lite(?![a-z])','devkit',text)
     text=text.replace("scope not in ('devkit','shared')", "scope not in ('core','shared')")
     text=text.replace("+ '/devkit'", "+ '/core'")
     text=text.replace("'/skills/devkit'", "'/skills/core'")
     text=text.replace('skills.external_dirs가 devkit와 shared', 'skills.external_dirs가 core와 shared')
     text=text.replace('tags: [dev, devkit,', 'tags: [dev, core,').replace('tags: [git, devkit,', 'tags: [git, core,').replace('tags: [dev, devkit]', 'tags: [dev, core]')
     for i,key in enumerate(protected):text=text.replace(f'@@PRESERVED_{i}@@',key)
     if text.encode('utf-8')!=data:p.write_bytes(text.encode('utf-8'))
     newrel=rel
     for old,new in pairs:newrel=newrel.replace(old,new)
     if newrel!=rel:
      dest=ROOT/newrel
      assert not dest.exists(),newrel
      dest.parent.mkdir(parents=True,exist_ok=True)
      p.rename(dest)
    # Empty source directories are not tracked; remove only now-empty directories.
    for p in sorted(ROOT.rglob('*'),key=lambda p:len(p.parts),reverse=True):
     if '.git' not in p.parts and p.is_dir() and not any(p.iterdir()):p.rmdir()


def prepare():
    assert_context()
    encoded = ''.join((ROOT / f'scripts/.naming-patch-{i}').read_text() for i in range(1, 6))
    patch = gzip.decompress(base64.b64decode(encoded, validate=True))
    assert hashlib.sha256(patch).hexdigest() == PATCH_SHA256, 'Patch checksum mismatch'
    transform()
    subprocess.run(['git', 'apply', '--check', '--unidiff-zero', '-'], input=patch, check=True)
    subprocess.run(['git', 'apply', '--unidiff-zero', '-'], input=patch, check=True)
    for name in TEMP_FILES:
        (ROOT / name).unlink()
    subprocess.run(['git', 'add', '-A'], check=True)
    subprocess.run(['git', 'diff', '--cached', '--check'], check=True)
    tree = git('write-tree')
    assert tree == EXPECTED_TREE, f'Candidate tree mismatch: {tree}'
    print(git('diff', '--cached', '--stat'))
    print('CANDIDATE_TREE=' + tree)
    (Path(os.environ['RUNNER_TEMP']) / 'naming-candidate.patch').write_bytes(git('diff', '--cached', '--binary', raw=True))


def publish_tree():
    assert_context()
    assert git('write-tree') == EXPECTED_TREE, 'Index changed after tests'
    # The job token is not allowed to change workflow files. Leave .github
    # exactly as it was; the authorized connector publishes those separately.
    old_github = git('rev-parse', 'HEAD:.github')
    root_entries = git('ls-tree', EXPECTED_TREE).splitlines()
    root_entries = [f'040000 tree {old_github}\t.github' if line.endswith('\t.github') else line for line in root_entries]
    expected_published = subprocess.check_output(['git', 'mktree'], input=('\n'.join(root_entries) + '\n').encode()).decode().strip()
    base_tree = git('rev-parse', 'HEAD^{tree}')
    known = set()
    for line in git('ls-tree', '-r', '-z', 'HEAD', raw=True).split(b'\0'):
        if line:
            known.add(line.split(b'\t', 1)[0].split()[2].decode())
    index = {}
    for line in git('ls-files', '--stage', '-z', raw=True).split(b'\0'):
        if not line:
            continue
        meta, name = line.decode().split('\t', 1)
        mode, sha, stage = meta.split()
        assert stage == '0'
        index[name] = (mode, sha)
    entries = []
    for name in git('diff', '--cached', '--name-only', '--no-renames', '-z', raw=True).decode().split('\0'):
        if not name or name.startswith('.github/'):
            continue
        if name not in index:
            entries.append({'path': name, 'mode': '100644', 'type': 'blob', 'sha': None})
            continue
        mode, sha = index[name]
        entry = {'path': name, 'mode': mode, 'type': 'blob'}
        if sha in known:
            entry['sha'] = sha
        else:
            entry['content'] = (ROOT / name).read_text(encoding='utf-8')
        entries.append(entry)
    data = json.dumps({'base_tree': base_tree, 'tree': entries}, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        'https://api.github.com/repos/kwang-sub/hermes-agent-devkit/git/trees',
        data=data, method='POST', headers={
            'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
            'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'devkit-naming-workbench'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError('Git tree creation failed: ' + exc.read().decode('utf-8')[:2000]) from None
    assert result['sha'] == expected_published, 'GitHub non-workflow tree differs from tested content'
    report = {'tree': result['sha'], 'tested_tree': EXPECTED_TREE,
              'parent': os.environ['GITHUB_SHA'], 'workflow_changes_deferred': True,
              'workflow_run': os.environ['GITHUB_RUN_ID'], 'refs_updated': False}
    (Path(os.environ['RUNNER_TEMP']) / 'naming-candidate.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    {'prepare': prepare, 'publish-tree': publish_tree}[sys.argv[1]]()

#!/usr/bin/env python3
"""One-time, checksum-pinned source transfer; never touches a deployed runtime."""
from __future__ import annotations
import base64
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

BASE = '6e70eb149f4b3e58678555b14de8485078f4ad10'
DIGEST = '5727b16595ae4f6a5285b4495cdfbc9c5ee11a7cf8cada6a621d2dce3fe62b97'
ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'refactor/lite-only-runtime'
BOOTSTRAP = '.github/workflows/lite-transition-apply.yml'


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def path(value: str) -> Path:
    p = PurePosixPath(value)
    if not value or p.is_absolute() or any(x in ('..', '.git') for x in p.parts) or '\\' in value:
        raise ValueError('Unsafe transfer path')
    result = ROOT.joinpath(*p.parts)
    for parent in (result, *result.parents):
        if parent == ROOT:
            break
        if parent.is_symlink():
            raise ValueError('Transfer path may not cross a symlink')
    result.resolve().relative_to(ROOT)
    return result


def bundle() -> dict:
    if os.environ.get('GITHUB_REPOSITORY') != 'kwang-sub/hermes-agent-devkit':
        raise ValueError('Unexpected repository')
    if os.environ.get('GITHUB_REF') != 'refs/heads/' + BRANCH:
        raise ValueError('Only the authorized feature branch can be updated')
    git('merge-base', '--is-ancestor', BASE, 'HEAD')
    delta = git('diff', '--name-only', BASE, 'HEAD').decode().splitlines()
    if any(not (p.startswith('.lite-transfer/') or p == BOOTSTRAP) for p in delta):
        raise ValueError('Branch gained other source changes; reconcile before applying')
    encoded = b''.join((ROOT / '.lite-transfer' / f'{i:02}.b64').read_bytes() for i in range(8))
    raw = lzma.decompress(base64.b64decode(encoded, validate=True), memlimit=256*1024*1024)
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError('Transfer checksum mismatch')
    data = json.loads(raw)
    if data['base'] != BASE:
        raise ValueError('Transfer baseline mismatch')
    return data


def apply(data: dict) -> None:
    # Construct and verify ALL bytes before writing a file.
    files = []
    for entry in data['changes']:
        target = path(entry['path'])
        if entry['source'] is not None:
            path(entry['source'])
            lines = git('show', BASE + ':' + entry['source']).decode('utf-8').splitlines(keepends=True)
        else:
            lines = []
        for start, end, replacement in reversed(entry['edits']):
            if not 0 <= start <= end <= len(lines):
                raise ValueError('Invalid line replacement range')
            lines[start:end] = [replacement]
        raw = ''.join(lines).encode('utf-8')
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Reconstructed file checksum mismatch: ' + entry['path'])
        mode = int(entry['mode'], 8)
        if mode not in (0o644, 0o755):
            raise ValueError('Unexpected file mode')
        files.append((target, raw, mode))
    deleted = [path(p) for p in data['delete']]
    for target in deleted:
        if target.exists() and not target.is_file():
            raise ValueError('Deletion must be a tracked regular file')
    for target in deleted:
        target.unlink(missing_ok=True)
        parent = target.parent
        while parent != ROOT:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    for target, raw, mode in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(mode)
    print(f'[PASS] verified transfer: {len(files)} writes, {len(deleted)} deletions')


def publish(data: dict) -> None:
    # Workflow changes require the connected app; stage only ordinary source here.
    approved = sorted(set(data['delete'] + [x['path'] for x in data['changes']]))
    approved = [p for p in approved if not p.startswith('.github/workflows/')]
    transfer_paths = git('ls-files', '.lite-transfer').decode().splitlines()
    for name in transfer_paths:
        path(name).unlink(missing_ok=True)
    git('add', '-A', '--', *approved, '.lite-transfer')
    staged = git('diff', '--cached', '--name-only').decode().splitlines()
    if not staged or any(p.startswith('.github/workflows/') or p not in approved + transfer_paths for p in staged):
        raise ValueError('Staged changes escape approved non-workflow paths')
    actual = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).decode().split()[0]
    head = git('rev-parse', 'HEAD').decode().strip()
    if actual != head:
        raise ValueError('Remote branch moved; refusing to overwrite it')
    git('config', 'user.name', 'github-actions[bot]')
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    git('commit', '-m', 'refactor(lite): retire role workflow and preserve standalone development runtime')
    git('push', 'origin', 'HEAD:refs/heads/' + BRANCH)
    print('PUBLISHED_COMMIT=' + git('rev-parse', 'HEAD').decode().strip())


if __name__ == '__main__':
    data = bundle()
    apply(data)
    if sys.argv[1:] == ['--publish']:
        publish(data)
    elif sys.argv[1:]:
        raise SystemExit('Unsupported transfer action')

#!/usr/bin/env python3
"""Transactional default-only migration. No board, OAuth, memory or session writes.

Apply runs at boot, after volume setup and before upstream gateway reconciliation.
Plan/status are read-only. Backups and a durable journal survive both success and
failure. Legacy role homes are renamed, never deleted or merged with archives.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile

try:
    import hermes_yaml as yaml
except ModuleNotFoundError as exc:
    if exc.name != 'hermes_yaml':
        raise
    import yaml

ROLES = ('orchestrator', 'coder', 'reviewer')
RETIRED = frozenset(('dev-workflow-orchestrate', 'dev-direct-flow', 'dev-workspace-dispatch',
    'dev-implement-plan', 'dev-code-review', 'dev-review-cycle', 'dev-flow-model-policy',
    'dev-skill-preflight', 'dev-task-recovery', 'dev-project-bootstrap', 'dev-project-resolve',
    'dev-breakdown', 'dev-tech-dispatch', 'sdlc-review'))
TOOLSETS = ('hermes-cli', 'kanban')
AUTOLOAD = 'dev-lite-session'


def safe_path(root: Path, relative: str) -> Path:
    """Reject symlink ancestors, not just the final entry (including broken links)."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Persistent data root must be an existing non-symlink directory')
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Invalid managed relative path')
    p = root
    for part in rel.parts:
        p /= part
        if p.is_symlink():
            raise ValueError('Symlink in managed migration path: ' + relative)
    return p


def mapping(path: Path) -> dict:
    if not path.exists():
        return {}
    if not path.is_file():
        raise ValueError('Configuration must be a regular file')
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError('Configuration must be a YAML mapping')
    return data


def list_value(data: dict, key: str) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError('Expected a string list: ' + key)
    return value


def fields(doc: dict) -> dict:
    skills = doc.get('skills') or {}
    if not isinstance(skills, dict):
        raise ValueError('skills must be a mapping')
    return {'dirs': list_value(skills, 'external_dirs'),
            'autoload': list_value(skills, 'auto_load'), 'tools': list_value(doc, 'toolsets')}


def desired(doc: dict, skills_root: str) -> dict:
    result = copy.deepcopy(doc)
    before = fields(doc)
    skills = result.setdefault('skills', {})
    if skills is None:
        skills = result['skills'] = {}
    roots = {skills_root.rstrip('/'), '/opt/custom-skills'}
    removed = {f'{r}/{role}' for r in roots for role in ROLES}
    def keep(path):
        normalized = os.path.normpath(path)
        return not any(normalized == old or normalized.startswith(old + '/') for old in removed)
    skills['external_dirs'] = list(dict.fromkeys(
        [p for p in before['dirs'] if keep(p)] +
        [skills_root.rstrip('/') + '/shared', skills_root.rstrip('/') + '/lite']))
    skills['auto_load'] = list(dict.fromkeys([s for s in before['autoload'] if s not in RETIRED] + [AUTOLOAD]))
    result['toolsets'] = list(dict.fromkeys(before['tools'] + list(TOOLSETS)))
    kanban = result.get('kanban')
    if kanban is None:
        kanban = result['kanban'] = {}
    if not isinstance(kanban, dict):
        raise ValueError('kanban must be a mapping')
    # Native, supported switch. No model override or task lifecycle mutation.
    kanban['dispatch_in_gateway'] = False
    return result


def active_tasks(root: Path) -> None:
    """Read known root/role board locations, never change a historical task state."""
    homes = [root]
    profiles = safe_path(root, 'profiles')
    if profiles.exists():
        if not profiles.is_dir():
            raise ValueError('profiles must be a directory')
        for role in ROLES:
            home = safe_path(root, 'profiles/' + role)
            if home.is_dir(): homes.append(home)
    found = []
    for home in homes:
        paths = [home / 'kanban.db']
        boards = home / 'kanban' / 'boards'
        safe_path(root, str(boards.relative_to(root)))
        if boards.is_dir():
            paths.extend(sorted(boards.glob('*/kanban.db')))
        for db in paths:
            safe_path(root, str(db.relative_to(root)))
            if not db.exists(): continue
            if not db.is_file(): raise ValueError('Kanban database is not a file')
            # mode=ro prevents accidentally creating or changing a SQLite DB.
            with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=3) as conn:
                rows = conn.execute("SELECT status, COUNT(*) FROM tasks WHERE status IN ('running','review') GROUP BY status").fetchall()
            found.extend(f'{status}={count}' for status, count in rows if count)
    if found:
        raise RuntimeError('Active Kanban tasks; finish or safely pause before migration: ' + ', '.join(found))


def overlay_check(root: Path, doc: dict) -> Path | None:
    marker = safe_path(root, 'devkit-lite/profile-state.json')
    if not marker.exists(): return None
    old = json.loads(marker.read_text(encoding='utf-8'))
    if not isinstance(old, dict) or old.get('schema') not in (1, 2):
        raise ValueError('Unknown Lite overlay schema')
    if old.get('phase') not in ('prepared', 'applied'):
        raise ValueError('Invalid Lite overlay phase')
    keys = ('dirs', 'tools') if old['schema'] == 1 else ('dirs', 'tools', 'autoload')
    now = fields(doc)
    candidates = [old.get('before'), old.get('applied')]
    if not all(isinstance(v, dict) for v in candidates):
        raise ValueError('Invalid Lite overlay fields')
    if not any(all(now[k] == (v.get(k) or []) for k in keys) for v in candidates):
        raise ValueError('Lite overlay managed fields changed; reconcile explicitly')
    return marker


def build_plan(root: Path, skills_root: str = '/opt/custom-skills') -> tuple[dict, dict, list, Path | None]:
    config = safe_path(root, 'config.yaml')
    before = mapping(config)
    after = desired(before, skills_root)
    marker = overlay_check(root, before)
    jobs = []
    for role in ROLES:
        src = safe_path(root, 'profiles/' + role)
        dst = safe_path(root, 'devkit-lite/legacy-profiles/' + role)
        if src.exists():
            if not src.is_dir() or dst.exists():
                raise ValueError('Active/archive profile conflict: ' + role)
            jobs.append((src, dst))
        elif dst.exists() and not dst.is_dir():
            raise ValueError('Invalid archive directory: ' + role)
    journal = safe_path(root, 'devkit-lite/migration-state.json')
    if journal.is_file():
        state = json.loads(journal.read_text())
        if state.get('phase') not in ('applied', 'rolled-back'):
            raise ValueError('Interrupted migration; inspect journal and backups before retry')
    elif journal.exists():
        raise ValueError('Invalid migration journal')
    # A completed, unchanged boot does not turn optional Kanban into a task gate.
    if before != after or jobs or marker:
        active_tasks(root)
    return before, after, jobs, marker


def atomic(path: Path, contents: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


@contextmanager
def exclusive(root: Path):
    import fcntl
    lock = safe_path(root, 'devkit-lite/migration.lock')
    lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def apply(root: Path, *, dry_run=False, skills_root='/opt/custom-skills') -> dict:
    before, after, jobs, overlay = build_plan(root, skills_root)
    info = {'status': 'planned', 'default_config_changed': before != after,
            'legacy_profile_archives': [p.name for p, _ in jobs], 'overlay_retired': bool(overlay)}
    if dry_run: return info
    if before == after and not jobs and not overlay:
        return dict(info, status='unchanged')
    with exclusive(root):
        before, after, jobs, overlay = build_plan(root, skills_root)
        config = safe_path(root, 'config.yaml')
        original = config.read_bytes() if config.exists() else None
        original_mode = stat.S_IMODE(config.stat().st_mode) if original is not None else 0o600
        encoded = yaml.safe_dump(after, allow_unicode=True, sort_keys=False).encode('utf-8')
        if yaml.safe_load(encoded.decode('utf-8')) != after:
            raise ValueError('YAML round-trip mismatch')
        tx_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = safe_path(root, 'devkit-lite/backups/' + tx_id)
        backup.mkdir(parents=True, mode=0o700)
        if original is not None: atomic(backup / 'config.yaml', original)
        overlay_dest = backup / 'profile-state.json'
        journal = safe_path(root, 'devkit-lite/migration-state.json')
        state = {'schema': 1, 'phase': 'prepared', 'backup': str(backup.relative_to(root)),
                 'moved_roles': [], 'config_sha256': hashlib.sha256(encoded).hexdigest()}
        def record(phase):
            state['phase'] = phase
            atomic(journal, (json.dumps(state, indent=2) + '\n').encode())
        record('prepared')
        moved = []
        overlay_moved = False
        wrote = False
        try:
            # Rename only to absent destinations, with all paths validated before any mutation.
            for src, dst in jobs:
                dst.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                if dst.exists(): raise ValueError('Archive appeared concurrently')
                os.rename(src, dst)
                moved.append((src, dst))
                state['moved_roles'].append(src.name)
                record('prepared')
            if before != after:
                atomic(config, encoded, original_mode)
                wrote = True
                if mapping(config) != after: raise RuntimeError('Config read-back mismatch')
            if overlay:
                os.rename(overlay, overlay_dest)
                overlay_moved = True
            record('applied')
        except Exception:
            # Only restore files this transaction wrote, and only while still unchanged.
            try:
                if overlay_moved and not overlay.exists(): os.rename(overlay_dest, overlay)
                if wrote:
                    if config.read_bytes() != encoded: raise RuntimeError('Config changed during rollback')
                    if original is None: config.unlink()
                    else: atomic(config, original, original_mode)
                for src, dst in reversed(moved):
                    if src.exists(): raise RuntimeError('Profile changed during rollback')
                    os.rename(dst, src)
                record('rolled-back')
            except Exception:
                # Leave the prepared journal and backups; never overwrite divergent data.
                raise RuntimeError('Migration interrupted; manual recovery from journal required') from None
            raise
    return dict(info, status='applied', backup=str(backup.relative_to(root)))


def status(root: Path, skills_root='/opt/custom-skills') -> dict:
    before, after, jobs, overlay = build_plan(root, skills_root)
    ready = before == after and not jobs and overlay is None
    return {'ready': ready, 'default_config_valid': before == after,
            'active_legacy_profiles': [p.name for p, _ in jobs], 'legacy_overlay': bool(overlay)}


def assert_boot_quiet() -> None:
    """Do not archive a profile beneath a live s6 gateway when invoked manually."""
    for slot in Path('/run/service').glob('gateway-*'):
        probe = subprocess.run(['/command/s6-svstat', '-o', 'up', str(slot)], capture_output=True, text=True, timeout=5)
        if probe.returncode == 0 and probe.stdout.strip() == 'true':
            raise RuntimeError('Live gateway detected; migration is only allowed before service startup')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'apply', 'status'))
    parser.add_argument('--data-root', type=Path, default=Path('/opt/data'))
    parser.add_argument('--skills-root', default=os.getenv('HERMES_CONTAINER_CUSTOM_SKILLS_PATH', '/opt/custom-skills'))
    parser.add_argument('--boot', action='store_true', help='Required for apply; run before gateway reconciliation')
    args = parser.parse_args()
    try:
        if not args.skills_root.startswith('/'):
            raise ValueError('Skill root must be absolute')
        if args.action == 'status':
            report = status(args.data_root, args.skills_root)
        else:
            if args.action == 'apply':
                if not args.boot: raise ValueError('Apply requires the quiescent boot phase (--boot)')
                assert_boot_quiet()
            report = apply(args.data_root, dry_run=args.action == 'plan', skills_root=args.skills_root)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report.get('ready', True) else 1
    except (OSError, ValueError, RuntimeError, sqlite3.Error, yaml.YAMLError, subprocess.SubprocessError) as exc:
        # YAML scanner messages can contain secret scalar values; report only category there.
        reason = type(exc).__name__ if isinstance(exc, yaml.YAMLError) else str(exc)
        print('[BLOCKED] ' + reason, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

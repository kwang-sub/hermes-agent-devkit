#!/usr/bin/env python3
"""Shared s6 checks for the Windows updater and real-image boot smoke tests."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

STATIC_SCANDIR = Path('/run/service')
S6_SVSTAT = '/package/admin/s6/command/s6-svstat'


def gateway_scandir() -> Path:
    """Use the installed Hermes contract, including legacy single-tree images."""
    try:
        from hermes_cli.service_manager import S6ServiceManager
        root = Path(S6ServiceManager().scandir)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError('Cannot resolve the installed Hermes Gateway scandir') from exc
    if not root.is_absolute():
        raise RuntimeError('Hermes Gateway scandir must be an absolute path')
    return root


def service_running(slot: Path) -> bool:
    probe = subprocess.run([S6_SVSTAT, '-o', 'up', str(slot)],
                           capture_output=True, text=True, timeout=5)
    return probe.returncode == 0 and probe.stdout.strip() == 'true'


def check_service(slot: Path) -> None:
    script = slot / 'run'
    if not script.is_file() or not os.access(script, os.X_OK):
        raise RuntimeError(f'Missing executable s6 service script: {script}')
    if not service_running(slot):
        raise RuntimeError(f's6 service is not running: {slot}')


def check_gateway() -> None:
    """Run as hermes; never grant access to the root supervisor's static tree."""
    root = gateway_scandir()
    if root != STATIC_SCANDIR and os.access(STATIC_SCANDIR, os.W_OK):
        raise RuntimeError(f'Root s6 scandir must not be hermes-writable: {STATIC_SCANDIR}')
    # Only create/remove our unique probe, preserving any pre-existing marker.
    with tempfile.TemporaryDirectory(prefix='.devkit-runtime-write-check-', dir=root):
        pass
    for name in ('control', 'lock'):
        path = root / '.s6-svscan' / name
        if not path.exists() or not os.access(path, os.W_OK):
            raise RuntimeError(f'Gateway scandir control is missing or not hermes-writable: {path}')
    check_service(root / 'gateway-default')
    print(f'[PASS] s6 Gateway scandir is hermes-writable and default is running: {root}')


def check_notifier() -> None:
    """The root-created notifier stays in the static tree and drops privileges."""
    slot = STATIC_SCANDIR / 'devkit-notifier'
    check_service(slot)
    print(f'[PASS] DevKit notifier service is running: {slot}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=('gateway', 'notifier'))
    args = parser.parse_args()
    try:
        if args.service == 'gateway':
            check_gateway()
        else:
            check_notifier()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f'[FAIL] s6 {args.service} runtime contract: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

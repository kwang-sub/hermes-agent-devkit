#!/usr/bin/env python3
"""Idempotent transition to a Lite-only default profile without deleting data.

This module is staged separately from updater/runtime changes so it can be
tested before role profiles are retired in production.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys

from lite_mode import (
    DIRS, AUTOLOAD, TOOLSETS, STANDARD_DIRS, atom, guard, load,
    merge, read_marker, replace, selected, write_yaml, migrate_legacy_overlay,
)

ROLES = ("orchestrator", "coder", "reviewer")
LEGACY_AUTOLOAD = {
    "dev-workflow-orchestrate", "dev-direct-flow", "dev-workspace-dispatch",
    "dev-implement-plan", "dev-code-review", "dev-review-cycle",
    "dev-flow-model-policy", "dev-skill-preflight", "dev-task-recovery",
}


def roots(data_root: Path) -> tuple[Path, Path]:
    if not data_root.is_dir() or data_root.is_symlink():
        raise ValueError("Persistent data root must be an existing directory, not a symlink")
    legacy = data_root / "devkit-lite" / "legacy-profiles"
    if legacy.is_symlink():
        raise ValueError("Legacy profile archive may not be a symlink")
    return data_root / "config.yaml", legacy


def archive_plan(data_root: Path) -> list[tuple[Path, Path]]:
    _, legacy = roots(data_root)
    jobs = []
    for role in ROLES:
        old = data_root / "profiles" / role
        dest = legacy / role
        if old.is_symlink() or dest.is_symlink():
            raise ValueError("Symlink profile location is not supported: " + role)
        if old.exists():
            if not old.is_dir():
                raise ValueError("Expected profile directory: " + str(old))
            if dest.exists():
                raise ValueError("Both active and archived profile exist: " + role)
            jobs.append((old, dest))
        elif dest.exists() and not dest.is_dir():
            raise ValueError("Invalid existing profile archive: " + role)
    return jobs


def desired_fields(before: dict) -> dict:
    desired = merge(before)
    desired["autoload"] = [
        name for name in desired["autoload"] if name not in LEGACY_AUTOLOAD
    ]
    return desired


def apply(data_root: Path, *, archive: bool = False, dry_run: bool = False) -> dict:
    """Change only default config and optional role directory location."""
    config, archive_root = roots(data_root)
    if config.is_symlink():
        raise ValueError("Default configuration may not be a symlink")
    # Validate both data and archive conflicts before the first mutation.
    jobs = archive_plan(data_root) if archive else []
    guard(data_root)
    overlay = read_marker(data_root)
    if overlay:
        if overlay.get("schema") not in (1, 2):
            raise ValueError("Unknown Lite overlay marker schema")
        current, _ = load(config)
        current_fields = selected(current)
        if overlay.get("schema") == 2:
            # Reject user modifications to managed fields instead of silently
            # using the stale overlay as a source of truth.
            allowed = [overlay.get("before"), overlay.get("applied")]
            if current_fields not in allowed:
                raise ValueError("Lite overlay fields were changed; manual reconciliation required")
    else:
        current, _ = load(config)
    before = selected(current)
    wanted = desired_fields(before)
    changed = before != wanted
    outcome = {
        "status": "planned" if dry_run else "ready",
        "default_config_changed": changed,
        "legacy_profile_archives": [source.name for source, _ in jobs],
        "legacy_role_dirs_remaining": sorted(STANDARD_DIRS.intersection(wanted["dirs"])),
    }
    if dry_run:
        return outcome
    if overlay and overlay.get("schema") == 1:
        migrate_legacy_overlay(data_root)
        current, _ = load(config)
        before = selected(current)
        wanted = desired_fields(before)
        changed = before != wanted
    if changed:
        backup_dir = data_root / "devkit-lite" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        if config.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backup_dir / ("lite-only-default-" + stamp + ".yaml")
            shutil.copy2(config, backup)
        write_yaml(config, replace(current, wanted))
        if selected(load(config)[0]) != wanted:
            raise RuntimeError("Default config read-back mismatch")
    if overlay:
        marker_path = data_root / "devkit-lite" / "profile-state.json"
        archive_marker = data_root / "devkit-lite" / "profile-state.lite-only-archived.json"
        if archive_marker.exists():
            raise ValueError("Legacy Lite overlay archive already exists; manual reconciliation required")
        # Do not delete the old overlay; retire the restore marker atomically.
        os.replace(marker_path, archive_marker)
    if jobs:
        archive_root.mkdir(parents=True, exist_ok=True)
        guard(data_root)
        for source, target in jobs:
            os.replace(source, target)
    outcome["status"] = "applied"
    return outcome


def status(root: Path) -> dict:
    config, archive_root = roots(root)
    fields = selected(load(config)[0])
    return {
        "default_skills_ok": all(item in (fields["dirs"] or []) for item in DIRS),
        "default_autoload_ok": all(item in (fields["autoload"] or []) for item in AUTOLOAD),
        "default_toolsets_ok": all(item in (fields["tools"] or []) for item in TOOLSETS),
        "standard_skills_active": sorted(STANDARD_DIRS.intersection(fields["dirs"] or [])),
        "legacy_role_dirs": [role for role in ROLES if (root / "profiles" / role).is_dir()],
        "archived_role_dirs": [role for role in ROLES if (archive_root / role).is_dir()],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "status", "plan"))
    parser.add_argument("--data-root", type=Path, default=Path("/opt/data"))
    parser.add_argument("--archive-legacy-profiles", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "status":
            result = status(args.data_root)
        else:
            result = apply(args.data_root, archive=args.archive_legacy_profiles,
                           dry_run=args.action == "plan")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print("[BLOCKED] " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

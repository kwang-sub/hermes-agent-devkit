#!/usr/bin/env python3
"""Lite profile overlay: never mutate boards, memories, sessions or OAuth."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
try:
    import hermes_yaml as yaml
except ModuleNotFoundError as exc:
    if exc.name != "hermes_yaml":
        raise
    import yaml

DIRS = ["/opt/custom-skills/shared", "/opt/custom-skills/lite"]
TOOLSETS = ["hermes-cli", "kanban"]
AUTOLOAD = ["dev-lite-session"]
STANDARD_DIRS = {
    "/opt/custom-skills/orchestrator",
    "/opt/custom-skills/coder",
    "/opt/custom-skills/reviewer",
}
ABSENT = object()

def load(path):
    exists = path.is_file()
    raw = path.read_text(encoding="utf-8") if exists else ""
    data = yaml.safe_load(raw) if raw.strip() else {}
    if data is None: data = {}
    if not isinstance(data, dict): raise ValueError("config must be YAML mapping")
    return data, exists

def selected(data):
    skills = data.get("skills") or {}
    if not isinstance(skills, dict): raise ValueError("skills must be mapping")
    result = {}
    for key, value in (("dirs", skills.get("external_dirs", ABSENT)),
                       ("tools", data.get("toolsets", ABSENT)),
                       ("autoload", skills.get("auto_load", ABSENT))):
        if value is ABSENT: result[key] = None
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            result[key] = list(value)
        else: raise ValueError(f"{key} must be list of strings")
    return result

def merge(before):
    # Only the fixed Standard worker directories are excluded from Lite.
    # Preserve arbitrary user-installed skill directories and their order.
    personal_dirs = [item for item in (before["dirs"] or []) if item not in STANDARD_DIRS]
    return {
        "dirs": list(dict.fromkeys(personal_dirs + DIRS)),
        "tools": list(dict.fromkeys((before["tools"] or []) + TOOLSETS)),
        "autoload": list(dict.fromkeys((before["autoload"] or []) + AUTOLOAD)),
    }

def replace(data, fields):
    doc = copy.deepcopy(data)
    skills = doc.get("skills") or {}
    if fields["dirs"] is None: skills.pop("external_dirs", None)
    else: skills["external_dirs"] = fields["dirs"]
    if fields["autoload"] is None: skills.pop("auto_load", None)
    else: skills["auto_load"] = fields["autoload"]
    if skills: doc["skills"] = skills
    else: doc.pop("skills", None)
    if fields["tools"] is None: doc.pop("toolsets", None)
    else: doc["toolsets"] = fields["tools"]
    return doc

def atom(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix="." + path.name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def write_yaml(path, data):
    raw = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    if yaml.safe_load(raw) != data: raise ValueError("invalid YAML round trip")
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    atom(path, raw.encode("utf-8"), mode)

def marker(root): return root / "devkit-lite" / "profile-state.json"

def read_marker(root):
    path = marker(root)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

def write_marker(root, payload):
    atom(marker(root), (json.dumps(payload, indent=2) + "\n").encode())

def board_paths(root):
    paths = [root / "kanban.db"]
    folder = root / "kanban" / "boards"
    if folder.is_dir(): paths.extend(sorted(folder.glob("*/kanban.db")))
    return [p for p in paths if p.is_file()]

def guard(root):
    active = []
    for db_path in board_paths(root):
        with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3) as db:
            rows = db.execute("SELECT status, COUNT(*) FROM tasks "
                              "WHERE status IN ('running', 'review') GROUP BY status")
            active.extend(f"{db_path.parent.name}:{status}={count}" for status, count in rows if count)
    if active: raise RuntimeError("Active Kanban task(s); finish/pause before switching: " + ", ".join(active))
    print("[OK] Kanban board guard passed")

def migrate_legacy_overlay(root):
    """Safely restore v1's two modified fields before applying v2.

    v1 never changed auto_load; retaining the current auto_load preserves
    any user customizations introduced after that older update.
    """
    state = read_marker(root)
    if not state or state.get("schema") != 1:
        return
    path = root / "config.yaml"
    data, _ = load(path)
    current = selected(data)
    legacy_keys = ("dirs", "tools")
    if all(current[key] == state["applied"][key] for key in legacy_keys):
        desired = dict(state["before"], autoload=current["autoload"])
        write_yaml(path, replace(data, desired))
    elif not all(current[key] == state["before"][key] for key in legacy_keys):
        raise RuntimeError("Legacy Lite profile fields changed; manual reconciliation required")
    marker(root).unlink()
    print("[OK] Previous Lite overlay safely restored before v2 migration")


def apply(root):
    guard(root)
    migrate_legacy_overlay(root)
    path = root / "config.yaml"
    doc, existed = load(path)
    before = selected(doc)
    state = read_marker(root)
    if state:
        if before == state["applied"]:
            if state["phase"] != "applied":
                state["phase"] = "applied"
                write_marker(root, state)
            print("[OK] Lite already active")
            return
        if state["phase"] != "prepared" or before != state["before"]:
            raise RuntimeError("Profile fields changed; manual reconciliation required")
    else:
        backup = None
        if existed:
            folder = root / "devkit-lite" / "backups"
            folder.mkdir(parents=True, exist_ok=True)
            backup_path = folder / ("config-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".yaml")
            shutil.copy2(path, backup_path)
            backup = str(backup_path)
        state = {"schema": 2, "phase": "prepared", "before": before,
                 "applied": merge(before), "existed": existed, "backup": backup}
        write_marker(root, state)
    write_yaml(path, replace(doc, state["applied"]))
    if selected(load(path)[0]) != state["applied"]: raise RuntimeError("Apply readback failed")
    state["phase"] = "applied"
    write_marker(root, state)
    print("[OK] Existing default profile configured; memory, auth and boards untouched")

def restore(root):
    guard(root)
    migrate_legacy_overlay(root)
    state = read_marker(root)
    if not state:
        print("[OK] No Lite overlay to restore")
        return
    path = root / "config.yaml"
    doc, _ = load(path)
    now = selected(doc)
    if state["phase"] == "prepared" and now == state["before"]: pass
    elif now != state["applied"]:
        raise RuntimeError("Lite skill/toolset fields edited by user; refusing overwrite")
    else:
        original = replace(doc, state["before"])
        if not state["existed"] and not original: path.unlink(missing_ok=True)
        else: write_yaml(path, original)
        if selected(load(path)[0]) != state["before"]: raise RuntimeError("Restore readback failed")
    marker(root).unlink()
    print("[OK] Lite overlay restored; other default profile values unchanged")

def status(root):
    state = read_marker(root)
    val = selected(load(root / "config.yaml")[0])
    print(json.dumps({"lite": bool(state), "profile_fields_match": val == state["applied"] if state else None,
                      "shared_skills": DIRS[0] in (val["dirs"] or []),
                      "lite_skills": DIRS[1] in (val["dirs"] or []),
                      "kanban": "kanban" in (val["tools"] or []),
                      "lite_autoload": AUTOLOAD[0] in (val["autoload"] or []),
                      "standard_worker_skill_dirs": sorted(STANDARD_DIRS.intersection(val["dirs"] or []))}, indent=2))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["guard","apply","restore","status"])
    parser.add_argument("--data-root", type=Path, default=Path("/opt/data"))
    args = parser.parse_args()
    try:
        {"guard":guard,"apply":apply,"restore":restore,"status":status}[args.action](args.data_root)
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error, RuntimeError, yaml.YAMLError) as exc:
        print("[BLOCKED]", exc, file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())

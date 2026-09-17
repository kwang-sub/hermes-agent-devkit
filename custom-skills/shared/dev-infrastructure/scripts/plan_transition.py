#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_APPLICATION_RUNTIME = "CONTAINER"
DEFAULT_DATABASE_RUNTIME = "CONTAINER"
DEFAULT_DATABASE_PLATFORM = "NATIVE"
DEFAULT_DATABASE_VENDOR = "UNKNOWN"


class TransitionPlanError(RuntimeError):
    pass


def load_detector():
    script = Path(__file__).with_name("detect_infrastructure.py")
    spec = importlib.util.spec_from_file_location("devkit_detect_infrastructure", script)
    if spec is None or spec.loader is None:
        raise TransitionPlanError(f"cannot load detector: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_scalar(section: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s{{2}}{re.escape(key)}:\s*(.+?)\s*$", section)
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        value = json.loads(raw)
        if isinstance(value, str):
            return value
    except Exception:
        pass
    return raw.strip("'\"")


def top_level_section(text: str, key: str) -> str | None:
    lines = text.splitlines()
    start = None
    end = len(lines)
    for index, line in enumerate(lines):
        if line.startswith((" ", "\t")):
            continue
        if re.match(rf"^{re.escape(key)}:\s*$", line):
            start = index
            continue
        if start is not None and re.match(r"^[A-Za-z0-9_.-]+:\s*", line):
            end = index
            break
    if start is None:
        return None
    return "\n".join(lines[start:end])


def desired_state(repo: Path) -> dict[str, str]:
    path = repo / ".hermes" / "project.yaml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    section = top_level_section(text, "infrastructure") or ""

    vendor = parse_scalar(section, "database_vendor") or DEFAULT_DATABASE_VENDOR
    if vendor == "UNKNOWN":
        technology = top_level_section(text, "technology") or ""
        candidates = re.findall(r"(?m)^\s{4}-\s+[\"']?([A-Za-z0-9_-]+)[\"']?\s*$", technology)
        db_candidates = [v for v in candidates if v in {"postgresql", "mysql", "mariadb", "mssql", "oracle"}]
        if len(set(db_candidates)) == 1:
            vendor = db_candidates[0]

    return {
        "application_runtime": (parse_scalar(section, "application_runtime") or DEFAULT_APPLICATION_RUNTIME).upper(),
        "database_runtime": (parse_scalar(section, "database_runtime") or DEFAULT_DATABASE_RUNTIME).upper(),
        "database_platform": (parse_scalar(section, "database_platform") or DEFAULT_DATABASE_PLATFORM).upper(),
        "database_vendor": vendor.lower() if vendor != "UNKNOWN" else "UNKNOWN",
    }


def normalize_supabase(state: dict[str, str]) -> dict[str, str]:
    normalized = dict(state)
    if normalized["database_platform"] == "SUPABASE":
        normalized["database_vendor"] = "postgresql"
    return normalized


def compare(observed: dict[str, Any], desired: dict[str, str]) -> dict[str, Any]:
    desired = normalize_supabase(desired)
    changes: list[dict[str, str]] = []
    unknown_observed: list[str] = []

    fields = (
        ("application_runtime", "APPLICATION_RUNTIME"),
        ("database_runtime", "DATABASE_RUNTIME"),
        ("database_platform", "DATABASE_PLATFORM"),
        ("database_vendor", "DATABASE_VENDOR"),
    )
    for field, label in fields:
        before = str(observed.get(field, "UNKNOWN"))
        after = str(desired[field])
        if before == "UNKNOWN":
            unknown_observed.append(label)
            continue
        if before != after:
            changes.append({"field": label, "from": before, "to": after})

    vendor_change = any(item["field"] == "DATABASE_VENDOR" for item in changes)
    runtime_changes = [item for item in changes if item["field"].endswith("RUNTIME")]
    platform_change = any(item["field"] == "DATABASE_PLATFORM" for item in changes)

    if not changes and not unknown_observed:
        transition = "NO_CHANGE"
    elif len(changes) > 1:
        transition = "COMBINED_CHANGE"
    elif changes:
        field = changes[0]["field"]
        if field.endswith("RUNTIME"):
            transition = "RUNTIME_CHANGE"
        elif field == "DATABASE_PLATFORM":
            transition = "PLATFORM_CHANGE"
        elif field == "DATABASE_VENDOR":
            transition = "VENDOR_CHANGE"
        else:
            transition = "HOST_CHANGE"
    else:
        transition = "UNKNOWN"

    if changes:
        drift = "DETECTED"
    elif unknown_observed:
        drift = "UNKNOWN"
    else:
        drift = "NONE"

    required_skills = ["dev-infrastructure"]
    data_migration = "NOT_REQUIRED"
    if vendor_change:
        required_skills.extend(["dev-data-feature", "dev-db-migration"])
        data_migration = "REQUIRED"

    preserved = []
    detached = []
    destructive = "NONE"
    for item in runtime_changes:
        if item["field"] == "DATABASE_RUNTIME" and item["from"] == "CONTAINER" and item["to"] != "CONTAINER":
            detached.append("database container service")
            preserved.append("database persistent volume/data")

    return {
        "desired": desired,
        "observed": {
            "application_runtime": observed.get("application_runtime", "UNKNOWN"),
            "database_runtime": observed.get("database_runtime", "UNKNOWN"),
            "database_platform": observed.get("database_platform", "UNKNOWN"),
            "database_vendor": observed.get("database_vendor", "UNKNOWN"),
        },
        "drift": drift,
        "transition": transition,
        "changes": changes,
        "unknown_observed": unknown_observed,
        "required_skills": required_skills,
        "data_migration": data_migration,
        "resources_detached": detached,
        "resources_preserved": preserved,
        "destructive_operations": destructive,
        "safe_to_auto_destroy": False,
        "platform_change": platform_change,
        "vendor_change": vendor_change,
    }


def plan(repo: Path) -> dict[str, Any]:
    detector = load_detector()
    observed = detector.infer_state(repo)
    desired = desired_state(repo)
    return compare(observed, desired)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan desired/observed infrastructure transition without destructive cleanup")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}", file=sys.stderr)
        return 2

    try:
        result = plan(repo)
    except TransitionPlanError as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"DRIFT={result['drift']}")
    print(f"TRANSITION={result['transition']}")
    for item in result["changes"]:
        print(f"CHANGE={item['field']}:{item['from']}->{item['to']}")
    print(f"UNKNOWN_OBSERVED={','.join(result['unknown_observed'])}")
    print(f"REQUIRED_SKILLS={','.join(result['required_skills'])}")
    print(f"DATA_MIGRATION={result['data_migration']}")
    print(f"RESOURCES_DETACHED={','.join(result['resources_detached'])}")
    print(f"RESOURCES_PRESERVED={','.join(result['resources_preserved'])}")
    print(f"DESTRUCTIVE_OPERATIONS={result['destructive_operations']}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

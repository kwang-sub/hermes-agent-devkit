#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

RUNTIMES = {"LOCAL_HOST", "NETWORK_HOST", "CONTAINER", "UNKNOWN"}
PLATFORMS = {"NATIVE", "SUPABASE", "UNKNOWN"}
UNKNOWN_VALUES = {"UNKNOWN", "unknown", "", "None", "none"}


def load_detector():
    path = Path(__file__).with_name("detect_infrastructure.py")
    spec = importlib.util.spec_from_file_location("devkit_detect_infrastructure", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load infrastructure detector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _text(state: dict[str, Any], key: str, default: str = "unknown") -> str:
    value = state.get(key, default)
    return default if value is None else str(value).strip()


def normalize(state: dict[str, Any]) -> dict[str, str]:
    app = _text(state, "application_runtime", "UNKNOWN").upper()
    db = _text(state, "database_runtime", "UNKNOWN").upper()
    platform = _text(state, "database_platform", "UNKNOWN").upper()
    vendor = _text(state, "database_vendor", "unknown").lower()
    application_host = _text(state, "application_host")
    database_host = _text(state, "database_host")
    database_port = _text(state, "database_port")
    if app not in RUNTIMES:
        raise ValueError(f"invalid application runtime: {app}")
    if db not in RUNTIMES:
        raise ValueError(f"invalid database runtime: {db}")
    if platform not in PLATFORMS:
        raise ValueError(f"invalid database platform: {platform}")
    if platform == "SUPABASE":
        vendor = "postgresql"
    return {
        "application_runtime": app,
        "application_host": application_host,
        "database_runtime": db,
        "database_host": database_host,
        "database_port": database_port,
        "database_platform": platform,
        "database_vendor": vendor,
    }


def _known(value: str) -> bool:
    return value not in UNKNOWN_VALUES


def _endpoint_changed(before: dict[str, str], after: dict[str, str]) -> bool:
    pairs = (
        ("application_host", before["application_host"], after["application_host"]),
        ("database_host", before["database_host"], after["database_host"]),
        ("database_port", before["database_port"], after["database_port"]),
    )
    return any(_known(old) and _known(new) and old != new for _, old, new in pairs)


def plan(observed: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    before = normalize(observed)
    after = normalize(desired)
    changes: list[str] = []
    runtime_changed = False

    if before["application_runtime"] != after["application_runtime"]:
        changes.append("APPLICATION_RUNTIME")
        runtime_changed = True
    if before["database_runtime"] != after["database_runtime"]:
        changes.append("DATABASE_RUNTIME")
        runtime_changed = True
    if before["database_platform"] != after["database_platform"]:
        changes.append("PLATFORM")
    vendor_changed = (
        before["database_vendor"] != after["database_vendor"]
        and _known(before["database_vendor"])
        and _known(after["database_vendor"])
    )
    if vendor_changed:
        changes.append("VENDOR")

    host_changed = _endpoint_changed(before, after)
    if host_changed:
        changes.append("HOST")

    known_before = any(
        _known(before[key])
        for key in (
            "application_runtime",
            "application_host",
            "database_runtime",
            "database_host",
            "database_port",
            "database_vendor",
        )
    )
    if not changes:
        transition_class = "NO_CHANGE"
    elif not known_before:
        transition_class = "INITIAL_CONFIGURATION"
    elif len(changes) > 1:
        transition_class = "COMBINED_CHANGE"
    elif changes[0] in {"APPLICATION_RUNTIME", "DATABASE_RUNTIME"}:
        transition_class = "RUNTIME_CHANGE"
    elif changes[0] == "HOST":
        transition_class = "HOST_CHANGE"
    elif changes[0] == "PLATFORM":
        transition_class = "PLATFORM_CHANGE"
    else:
        transition_class = "VENDOR_CHANGE"

    detached: list[str] = []
    preserved: list[str] = []
    if before["database_runtime"] == "CONTAINER" and after["database_runtime"] != "CONTAINER":
        detached.append("database-container-service")
        preserved.append("database-persistent-volume")
    if before["application_runtime"] == "CONTAINER" and after["application_runtime"] != "CONTAINER":
        detached.append("application-container-service")

    return {
        "transition_class": transition_class,
        "changes": changes,
        "observed": before,
        "desired": after,
        "data_migration": "REQUIRED" if vendor_changed else "NOT_REQUIRED",
        "required_capabilities": ["dev-data-feature", "dev-db-migration"] if vendor_changed else [],
        "detached": detached,
        "preserved": preserved,
        "removed": [],
        "destructive_operations": "NONE",
        "runtime_changed": runtime_changed,
        "host_changed": host_changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan safe infrastructure runtime transition")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--application-runtime", default="CONTAINER")
    parser.add_argument("--application-host", default="unknown")
    parser.add_argument("--database-runtime", default="CONTAINER")
    parser.add_argument("--database-host", default="unknown")
    parser.add_argument("--database-port", default="unknown")
    parser.add_argument("--database-platform", default="NATIVE")
    parser.add_argument("--database-vendor", default="unknown")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    detector = load_detector()
    observed = detector.detect(repo)
    desired = {
        "application_runtime": args.application_runtime,
        "application_host": args.application_host,
        "database_runtime": args.database_runtime,
        "database_host": args.database_host,
        "database_port": args.database_port,
        "database_platform": args.database_platform,
        "database_vendor": args.database_vendor,
    }
    result = plan(observed, desired)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"TRANSITION_CLASS={result['transition_class']}")
        print(f"CHANGES={','.join(result['changes'])}")
        print(f"DATA_MIGRATION={result['data_migration']}")
        print(f"DESTRUCTIVE_OPERATIONS={result['destructive_operations']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

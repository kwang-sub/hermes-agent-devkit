#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

RUNTIMES = {"LOCAL_HOST", "NETWORK_HOST", "CONTAINER", "UNKNOWN"}
PLATFORMS = {"NATIVE", "SUPABASE", "UNKNOWN"}
UNKNOWN_VALUES = {"UNKNOWN", "unknown", "", None}
ENDPOINT_CHANGE_KEYS = {
    "APPLICATION_HOST",
    "APPLICATION_PORT",
    "DATABASE_HOST",
    "DATABASE_PORT",
}


def load_detector():
    path = Path(__file__).with_name("detect_infrastructure.py")
    spec = importlib.util.spec_from_file_location("devkit_detect_infrastructure", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load infrastructure detector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_endpoint(value: Any) -> str:
    raw = str(value or "unknown").strip()
    return raw.lower() if raw and raw.lower() != "unknown" else "unknown"


def normalize_port(value: Any) -> str:
    raw = str(value or "unknown").strip()
    if not raw or raw.lower() == "unknown":
        return "unknown"
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise ValueError(f"invalid port: {raw}")
    return raw


def normalize(state: dict[str, Any]) -> dict[str, str]:
    app = str(state.get("application_runtime", "UNKNOWN")).upper()
    db = str(state.get("database_runtime", "UNKNOWN")).upper()
    platform = str(state.get("database_platform", "UNKNOWN")).upper()
    vendor = str(state.get("database_vendor", "unknown")).lower()
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
        "application_host": normalize_endpoint(state.get("application_host")),
        "application_port": normalize_port(state.get("application_port")),
        "database_runtime": db,
        "database_host": normalize_endpoint(state.get("database_host")),
        "database_port": normalize_port(state.get("database_port")),
        "database_platform": platform,
        "database_vendor": vendor,
    }


def has_observed_evidence(state: dict[str, str]) -> bool:
    return any(value not in UNKNOWN_VALUES for value in state.values())


def append_endpoint_change(changes: list[str], key: str, before: str, after: str) -> None:
    if after not in UNKNOWN_VALUES and before != after:
        changes.append(key)


def plan(observed: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    before = normalize(observed)
    after = normalize(desired)
    initial_configuration = not has_observed_evidence(before)
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
        and before["database_vendor"] != "unknown"
    )
    if vendor_changed:
        changes.append("VENDOR")

    append_endpoint_change(
        changes,
        "APPLICATION_HOST",
        before["application_host"],
        after["application_host"],
    )
    append_endpoint_change(
        changes,
        "APPLICATION_PORT",
        before["application_port"],
        after["application_port"],
    )
    append_endpoint_change(
        changes,
        "DATABASE_HOST",
        before["database_host"],
        after["database_host"],
    )
    append_endpoint_change(
        changes,
        "DATABASE_PORT",
        before["database_port"],
        after["database_port"],
    )

    if not changes:
        transition_class = "NO_CHANGE"
    elif initial_configuration:
        transition_class = "INITIAL_CONFIGURATION"
    elif set(changes).issubset(ENDPOINT_CHANGE_KEYS):
        transition_class = "HOST_CHANGE"
    elif len(changes) > 1:
        transition_class = "COMBINED_CHANGE"
    elif changes[0] in {"APPLICATION_RUNTIME", "DATABASE_RUNTIME"}:
        transition_class = "RUNTIME_CHANGE"
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
        "host_changed": any(change in ENDPOINT_CHANGE_KEYS for change in changes),
        "initial_configuration": initial_configuration,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan safe infrastructure runtime transition")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--application-runtime", default="CONTAINER")
    parser.add_argument("--application-host", default="unknown")
    parser.add_argument("--application-port", default="unknown")
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
        "application_port": args.application_port,
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

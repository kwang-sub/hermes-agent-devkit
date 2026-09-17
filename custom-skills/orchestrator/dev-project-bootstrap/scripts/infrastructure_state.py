#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
INFRASTRUCTURE_VERSION = "1"
SUPPORTED_VENDORS = {"postgresql", "mysql", "mariadb", "mssql", "oracle"}
DEFAULT_APPLICATION_RUNTIME = "CONTAINER"
DEFAULT_DATABASE_RUNTIME = "CONTAINER"
DEFAULT_DATABASE_PLATFORM = "NATIVE"
DEFAULT_DATABASE_VENDOR = "UNKNOWN"


class InfrastructureStateError(RuntimeError):
    pass


def load_infrastructure_detector():
    script = (
        Path(__file__).resolve().parents[3]
        / "shared"
        / "dev-infrastructure"
        / "scripts"
        / "detect_infrastructure.py"
    )
    if not script.is_file():
        raise InfrastructureStateError(f"infrastructure detector is missing: {script}")
    spec = importlib.util.spec_from_file_location("devkit_detect_infrastructure", script)
    if spec is None or spec.loader is None:
        raise InfrastructureStateError(f"cannot load infrastructure detector: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split_top_level_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines(keepends=True)
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.startswith((" ", "\t")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s.*)?(?:\r?\n)?$", line)
        if match:
            starts.append((index, match.group(1)))
    if not starts:
        return text, []
    header = "".join(lines[: starts[0][0]])
    sections: list[tuple[str, str]] = []
    for pos, (start, key) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        sections.append((key, "".join(lines[start:end])))
    return header, sections


def metadata_path(repo: Path) -> Path:
    return repo / ".hermes" / "project.yaml"


def technology_vendors(sections: list[tuple[str, str]]) -> list[str]:
    body = next((body for key, body in sections if key == "technology"), "")
    if not body:
        return []
    lines = body.splitlines()
    inside = False
    values: list[str] = []
    for line in lines:
        if re.fullmatch(r"\s{2}database_vendors:\s*(?:\[\])?\s*", line):
            if line.rstrip().endswith("[]"):
                return []
            inside = True
            continue
        if not inside:
            continue
        if re.match(r"^\s{2}\S", line):
            break
        match = re.match(r"^\s{4}-\s+(.+?)\s*$", line)
        if not match:
            continue
        raw = match.group(1).strip()
        try:
            decoded = json.loads(raw)
            value = str(decoded)
        except Exception:
            value = raw.strip("'\"")
        if value in SUPPORTED_VENDORS:
            values.append(value)
    return list(dict.fromkeys(values))


def initial_state(repo: Path, sections: list[tuple[str, str]]) -> tuple[dict[str, str], dict[str, Any]]:
    detector = load_infrastructure_detector()
    observed = detector.infer_state(repo)

    runtime_candidates = list(observed.get("database_runtime_candidates", []))
    if observed.get("database_runtime") == "UNKNOWN" and len(runtime_candidates) > 1:
        raise InfrastructureStateError(
            "conflicting database runtime evidence prevents safe bootstrap default: "
            + ",".join(str(value) for value in runtime_candidates)
        )

    vendors = technology_vendors(sections)
    technology_vendor = vendors[0] if len(vendors) == 1 else DEFAULT_DATABASE_VENDOR

    observed_vendor = str(observed.get("database_vendor", "UNKNOWN"))
    vendor = observed_vendor if observed_vendor != "UNKNOWN" else technology_vendor

    platform = str(observed.get("database_platform", "UNKNOWN"))
    if platform == "UNKNOWN":
        platform = DEFAULT_DATABASE_PLATFORM

    if platform == "SUPABASE":
        vendor = "postgresql"

    state = {
        "application_runtime": (
            str(observed.get("application_runtime", "UNKNOWN"))
            if observed.get("application_runtime") != "UNKNOWN"
            else DEFAULT_APPLICATION_RUNTIME
        ),
        "database_runtime": (
            str(observed.get("database_runtime", "UNKNOWN"))
            if observed.get("database_runtime") != "UNKNOWN"
            else DEFAULT_DATABASE_RUNTIME
        ),
        "database_platform": platform,
        "database_vendor": vendor,
    }
    return state, observed


def infrastructure_section(state: dict[str, str]) -> str:
    return "\n".join([
        "infrastructure:",
        f"  version: {json.dumps(INFRASTRUCTURE_VERSION)}",
        f"  application_runtime: {json.dumps(state['application_runtime'])}",
        f"  database_runtime: {json.dumps(state['database_runtime'])}",
        f"  database_platform: {json.dumps(state['database_platform'])}",
        f"  database_vendor: {json.dumps(state['database_vendor'])}",
    ]) + "\n"


def ensure(repo: Path) -> tuple[str, dict[str, str], dict[str, Any] | None]:
    path = metadata_path(repo)
    if not path.is_file():
        raise InfrastructureStateError(
            f"bootstrap-managed metadata is missing; run bootstrap_project first: {path}"
        )
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise InfrastructureStateError(f"metadata is not managed by dev-project-bootstrap: {path}")

    header, sections = split_top_level_sections(text)
    existing = next((body for key, body in sections if key == "infrastructure"), None)
    if existing is not None:
        return "preserved", {}, None

    state, observed = initial_state(repo, sections)
    parts = [body.rstrip() for _, body in sections if body.strip()]
    parts.append(infrastructure_section(state).rstrip())
    updated = header.rstrip("\r\n")
    if updated:
        updated += "\n"
    updated += "\n\n".join(parts) + "\n"
    path.write_text(updated, encoding="utf-8")
    return "created", state, observed


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure bootstrap-managed Infrastructure Desired State. "
            "Explicit repository evidence wins; missing axes use safe defaults."
        )
    )
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}", file=sys.stderr)
        return 2
    try:
        status, state, observed = ensure(repo)
    except InfrastructureStateError as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2

    print(f"INFRASTRUCTURE_STATE={status}")
    if status == "preserved":
        print("INFRASTRUCTURE_INITIALIZATION=existing-desired-state-preserved")
    else:
        assert observed is not None
        print(f"APPLICATION_RUNTIME_OBSERVED={observed.get('application_runtime', 'UNKNOWN')}")
        print(f"DATABASE_RUNTIME_OBSERVED={observed.get('database_runtime', 'UNKNOWN')}")
        print(f"DATABASE_PLATFORM_OBSERVED={observed.get('database_platform', 'UNKNOWN')}")
        print(f"DATABASE_VENDOR_OBSERVED={observed.get('database_vendor', 'UNKNOWN')}")
        print(f"APPLICATION_RUNTIME_INITIAL={state['application_runtime']}")
        print(f"DATABASE_RUNTIME_INITIAL={state['database_runtime']}")
        print(f"DATABASE_PLATFORM_INITIAL={state['database_platform']}")
        print(f"DATABASE_VENDOR_INITIAL={state['database_vendor']}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

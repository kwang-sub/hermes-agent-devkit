#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re

MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
DESIRED_KEYS = (
    "application_runtime",
    "database_runtime",
    "database_platform",
    "database_vendor",
)


class InfrastructureCacheError(RuntimeError):
    pass


def load_detector():
    script = (
        Path(__file__).resolve().parents[3]
        / "shared"
        / "dev-infrastructure"
        / "scripts"
        / "detect_infrastructure.py"
    )
    if not script.is_file():
        raise InfrastructureCacheError(f"infrastructure detector is missing: {script}")
    spec = importlib.util.spec_from_file_location("devkit_detect_infrastructure", script)
    if spec is None or spec.loader is None:
        raise InfrastructureCacheError(f"cannot load infrastructure detector: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metadata_path(repo: Path) -> Path:
    return repo / ".hermes" / "project.yaml"


def section_body(text: str, key: str) -> str | None:
    match = re.search(
        rf"(?ms)^{re.escape(key)}:\s*(?:#.*)?\n(?P<body>.*?)(?=^[A-Za-z0-9_.-]+:\s*(?:#.*)?$|\Z)",
        text,
    )
    return match.group("body") if match else None


def has_section(text: str, key: str) -> bool:
    return section_body(text, key) is not None


def parse_scalar(value: str) -> str:
    raw = value.strip()
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return raw.strip("'\"")


def existing_desired(text: str) -> dict[str, str] | None:
    body = section_body(text, "infrastructure")
    if body is None:
        return None

    desired_match = re.search(
        r"(?ms)^\s{2}desired:\s*\n(?P<body>(?:\s{4}[^\n]*\n?)*)",
        body,
    )
    if desired_match is None:
        return None

    desired_body = desired_match.group("body")
    result: dict[str, str] = {}
    for key in DESIRED_KEYS:
        match = re.search(
            rf"(?m)^\s{{4}}{re.escape(key)}:\s*(.+?)\s*$",
            desired_body,
        )
        if match is not None:
            result[key] = parse_scalar(match.group(1))

    return result if len(result) == len(DESIRED_KEYS) else None


def technology_vendor(text: str) -> str:
    match = re.search(
        r"(?ms)^technology:\s*.*?^\s{2}database_vendors:\s*\n(?P<body>(?:\s{4}-.*\n?)*)",
        text,
    )
    if not match:
        return "unknown"
    values = re.findall(r"(?m)^\s{4}-\s+[\"']?([^\"'\s]+)", match.group("body"))
    return values[0].lower() if len(values) == 1 else "unknown"


def desired_from_observed(observed: dict[str, object], metadata_text: str) -> dict[str, str]:
    app = str(observed.get("application_runtime", "UNKNOWN"))
    db = str(observed.get("database_runtime", "UNKNOWN"))
    platform = str(observed.get("database_platform", "NATIVE"))
    vendor = str(observed.get("database_vendor", "unknown"))

    if app == "UNKNOWN":
        app = "CONTAINER"
    if db == "UNKNOWN":
        db = "CONTAINER"
    if platform == "UNKNOWN":
        platform = "NATIVE"
    if vendor == "unknown":
        vendor = technology_vendor(metadata_text)

    if platform == "SUPABASE":
        vendor = "postgresql"

    return {
        "application_runtime": app,
        "database_runtime": db,
        "database_platform": platform,
        "database_vendor": vendor,
    }


def render(desired: dict[str, str]) -> str:
    lines = [
        "infrastructure:",
        '  version: "1"',
        "  defaults:",
        '    application_runtime: "CONTAINER"',
        '    database_runtime: "CONTAINER"',
        "  desired:",
    ]
    for key in DESIRED_KEYS:
        lines.append(f"    {key}: {json.dumps(desired[key], ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def initialize(repo: Path) -> tuple[str, dict[str, str]]:
    path = metadata_path(repo)
    if not path.is_file():
        raise InfrastructureCacheError(f"bootstrap-managed metadata is missing: {path}")
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise InfrastructureCacheError(f"metadata is not managed by dev-project-bootstrap: {path}")

    preserved = existing_desired(text)
    if has_section(text, "infrastructure"):
        if preserved is None:
            raise InfrastructureCacheError(
                "existing infrastructure section is incomplete; refusing to infer over explicit desired state"
            )
        return "reused", preserved

    detector = load_detector()
    observed = detector.detect(repo)
    desired = desired_from_observed(observed, text)

    updated = text.rstrip() + "\n\n" + render(desired)
    path.write_text(updated, encoding="utf-8")
    return "created", desired


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize infrastructure desired-state metadata without overwriting existing state")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}")
        return 2
    try:
        status, desired = initialize(repo)
    except InfrastructureCacheError as exc:
        print(f"ERROR={exc}")
        return 2
    print(f"INFRASTRUCTURE_CACHE={status}")
    print(f"APPLICATION_RUNTIME={desired['application_runtime']}")
    print(f"DATABASE_RUNTIME={desired['database_runtime']}")
    print(f"DATABASE_PLATFORM={desired['database_platform']}")
    print(f"DATABASE_VENDOR={desired['database_vendor']}")
    print("INFRA_ENTRY_CANDIDATE=dev-infrastructure")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

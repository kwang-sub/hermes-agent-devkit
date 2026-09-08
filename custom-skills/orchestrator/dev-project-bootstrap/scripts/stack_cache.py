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
SCHEMA_VERSION = "3"
TECHNOLOGY_KEY = "technology"


class StackCacheError(RuntimeError):
    pass


def load_detector():
    script = (
        Path(__file__).resolve().parents[2]
        / "dev-tech-dispatch"
        / "scripts"
        / "detect_capabilities.py"
    )
    if not script.is_file():
        raise StackCacheError(f"stack detector is missing: {script}")
    spec = importlib.util.spec_from_file_location("devkit_detect_capabilities", script)
    if spec is None or spec.loader is None:
        raise StackCacheError(f"cannot load stack detector: {script}")
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


def scalar(section: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s{{2}}{re.escape(key)}:\s*(.+?)\s*$", section)
    if not match:
        return None
    value = match.group(1).strip()
    try:
        decoded = json.loads(value)
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return value.strip("'\"")


def list_value(section: str, key: str) -> list[str]:
    lines = section.splitlines()
    start = None
    values: list[str] = []
    for index, line in enumerate(lines):
        if re.fullmatch(rf"\s{{2}}{re.escape(key)}:\s*(?:\[\])?\s*", line):
            start = index + 1
            if line.rstrip().endswith("[]"):
                return []
            break
    if start is None:
        return []
    for line in lines[start:]:
        if re.match(r"^\s{2}\S", line):
            break
        match = re.match(r"^\s{4}-\s+(.+?)\s*$", line)
        if not match:
            continue
        raw = match.group(1)
        try:
            decoded = json.loads(raw)
            values.append(str(decoded))
        except Exception:
            values.append(raw.strip("'\""))
    return values


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(lines: list[str], values: list[str]) -> None:
    if not values:
        lines[-1] += " []"
        return
    for value in values:
        lines.append(f"    - {yaml_scalar(value)}")


def technology_section(result: dict[str, Any]) -> str:
    lines = [
        "technology:",
        f"  detector_version: {yaml_scalar(str(result['detector_version']))}",
        f"  fingerprint: {yaml_scalar(str(result['fingerprint']))}",
        "  inputs:",
    ]
    yaml_list(lines, [str(value) for value in result.get("inputs", [])])
    lines.append("  stacks:")
    yaml_list(lines, [str(value) for value in result.get("stacks", [])])
    lines.append("  backend_skills:")
    yaml_list(lines, [str(value) for value in result.get("backend_skills", [])])
    lines.extend([
        f"  frontend_entry: {yaml_scalar(str(result.get('frontend_entry', '')))}",
        "  frontend_hints:",
    ])
    yaml_list(lines, [str(value) for value in result.get("frontend_hints", [])])
    lines.extend([
        f"  ui_candidate: {yaml_scalar(str(result.get('ui_candidate', '')))}",
        f"  cross_stack_candidate: {yaml_scalar(str(result.get('cross_stack_candidate', '')))}",
    ])
    return "\n".join(lines) + "\n"


def metadata_path(repo: Path) -> Path:
    return repo / ".hermes" / "project.yaml"


def read_metadata(repo: Path) -> tuple[Path, str, list[tuple[str, str]]]:
    path = metadata_path(repo)
    if not path.is_file():
        raise StackCacheError(
            f"bootstrap-managed metadata is missing; run dev-project-bootstrap first: {path}"
        )
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise StackCacheError(f"metadata is not managed by dev-project-bootstrap: {path}")
    header, sections = split_top_level_sections(text)
    return path, header, sections


def rewrite_version(section: str) -> str:
    if re.search(r"(?m)^version:\s*.*$", section):
        return re.sub(r"(?m)^version:\s*.*$", f"version: {SCHEMA_VERSION}", section, count=1)
    return f"version: {SCHEMA_VERSION}\n"


def write_cache(repo: Path, result: dict[str, Any]) -> str:
    path, header, sections = read_metadata(repo)
    tech = technology_section(result)
    had_technology = any(key == TECHNOLOGY_KEY for key, _ in sections)
    output_sections: list[str] = []
    inserted = False

    for key, body in sections:
        if key == "version":
            output_sections.append(rewrite_version(body).rstrip())
            continue
        if key == TECHNOLOGY_KEY:
            output_sections.append(tech.rstrip())
            inserted = True
            continue
        output_sections.append(body.rstrip())
        if key == "profiles" and not inserted:
            output_sections.append(tech.rstrip())
            inserted = True

    if not inserted:
        output_sections.append(tech.rstrip())

    updated = header.rstrip("\r\n")
    if updated:
        updated += "\n"
    updated += "\n\n".join(part for part in output_sections if part.strip()) + "\n"
    original = path.read_text(encoding="utf-8")
    if updated == original:
        return "reused"
    path.write_text(updated, encoding="utf-8")
    return "updated" if had_technology else "created"


def technology_body(sections: list[tuple[str, str]]) -> str | None:
    for key, body in sections:
        if key == TECHNOLOGY_KEY:
            return body
    return None


def cached_values(sections: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    body = technology_body(sections)
    if body is None:
        return None, None
    return scalar(body, "detector_version"), scalar(body, "fingerprint")


def cached_summary(body: str, current: dict[str, Any]) -> dict[str, Any]:
    return {
        **current,
        "stacks": list_value(body, "stacks"),
        "backend_skills": list_value(body, "backend_skills"),
        "frontend_entry": scalar(body, "frontend_entry") or "",
        "frontend_hints": list_value(body, "frontend_hints"),
        "ui_candidate": scalar(body, "ui_candidate") or "",
        "cross_stack_candidate": scalar(body, "cross_stack_candidate") or "",
    }


def resolve(repo: Path, *, force: bool = False, write: bool = True) -> tuple[str, dict[str, Any]]:
    detector = load_detector()
    _, _, sections = read_metadata(repo)
    cached_version, cached_fingerprint = cached_values(sections)
    current = detector.fingerprint(repo)

    if (
        not force
        and cached_version == str(current["detector_version"])
        and cached_fingerprint == str(current["fingerprint"])
    ):
        body = technology_body(sections)
        if body is None:
            raise StackCacheError("technology cache disappeared during cache resolution")
        return "reused", cached_summary(body, current)

    result = detector.detect(repo)
    status = write_cache(repo, result) if write else "stale"
    return status, result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Maintain bootstrap-managed technology stack cache in .hermes/project.yaml"
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check-only", action="store_true", help="Detect stale cache without writing metadata")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}", file=sys.stderr)
        return 2

    try:
        status, result = resolve(repo, force=args.force, write=not args.check_only)
    except StackCacheError as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2

    print(f"STACK_CACHE={status}")
    print(f"DETECTOR_VERSION={result['detector_version']}")
    print(f"STACK_FINGERPRINT={result['fingerprint']}")
    print(f"STACK_INPUTS={','.join(result.get('inputs', []))}")
    print(f"STACKS={','.join(result.get('stacks', []))}")
    print(f"BACKEND_SKILLS={','.join(result.get('backend_skills', []))}")
    print(f"FRONTEND_ENTRY={result.get('frontend_entry', '')}")
    print(f"FRONTEND_HINTS={','.join(result.get('frontend_hints', []))}")
    print(f"UI_SKILL_CANDIDATE={result.get('ui_candidate', '')}")
    print(f"CROSS_STACK_SKILL_CANDIDATE={result.get('cross_stack_candidate', '')}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

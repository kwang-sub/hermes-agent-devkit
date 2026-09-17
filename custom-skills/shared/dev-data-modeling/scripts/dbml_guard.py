#!/usr/bin/env python3
"""Lightweight DBML structural and logical-model guard.

This is intentionally NOT a full DBML parser. It catches cheap AI-edit mistakes
before a real DBML parser or human ERD renderer (for example DBML Canvas) is used.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TABLE_RE = re.compile(r'(?mi)^\s*Table\s+([A-Za-z0-9_."-]+)\s*\{')
REF_RE = re.compile(
    r'(?mi)^\s*Ref(?:\s+[A-Za-z0-9_"-]+)?\s*:\s*'
    r'([A-Za-z0-9_."-]+)\.[A-Za-z0-9_"-]+\s*(?:<>|>|<|-)\s*'
    r'([A-Za-z0-9_."-]+)\.[A-Za-z0-9_"-]+'
)
TABLE_GROUP_START_RE = re.compile(r'(?mi)^\s*TableGroup\s+([A-Za-z0-9_"-]+)\s*\{')
IDENTIFIER_RE = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$')
GROUP_MEMBER_RE = re.compile(r'^[A-Za-z0-9_."-]+$')
VENDOR_TOKENS = {
    "mssql": (r"\bnvarchar\b", r"\bdatetime2\b", r"\bidentity\b", r"\binclude\s*\("),
    "mysql": (r"\bauto_increment\b", r"\bunsigned\b"),
    "postgresql": (r"\bjsonb\b", r"\btimestamptz\b", r"\bserial\b"),
    "oracle": (r"\bnvarchar2\b", r"\bvarchar2\b", r"\bnumber\s*\("),
}


def normalize_table(name: str) -> str:
    return name.replace('"', '').lower()


def _local_identifier(name: str) -> str:
    return normalize_table(name).rsplit(".", 1)[-1]


def extract_table_groups(text: str) -> list[tuple[str, list[str]]]:
    """Extract simple DBML TableGroup membership.

    TableGroup bodies do not contain nested braces in the canonical logical
    convention used by this DevKit. Unknown settings/notes are ignored here;
    a real DBML parser remains the syntax authority.
    """
    groups: list[tuple[str, list[str]]] = []
    for match in TABLE_GROUP_START_RE.finditer(text):
        close = text.find("}", match.end())
        if close < 0:
            groups.append((match.group(1), []))
            continue
        body = text[match.end():close]
        members: list[str] = []
        for raw_line in body.splitlines():
            line = raw_line.split("//", 1)[0].strip().rstrip(",")
            if not line:
                continue
            if line.startswith(("Note:", "note:", "color:", "headercolor:")):
                continue
            candidate = line.split("[", 1)[0].strip()
            if GROUP_MEMBER_RE.fullmatch(candidate):
                members.append(candidate)
        groups.append((match.group(1), members))
    return groups


def analyze(text: str, mode: str = "logical", require_subject_area: bool = False) -> dict[str, Any]:
    raw_tables = TABLE_RE.findall(text)
    tables = [normalize_table(name) for name in raw_tables]
    errors: list[str] = []
    warnings: list[str] = []

    if not tables:
        errors.append("no Table declaration found")

    seen: set[str] = set()
    for original, normalized in zip(raw_tables, tables):
        if normalized in seen:
            errors.append(f"duplicate Table declaration: {original}")
        seen.add(normalized)

    for left, right in REF_RE.findall(text):
        for target in (left, right):
            if normalize_table(target) not in seen:
                errors.append(f"Ref target table is not declared: {target}")

    groups = extract_table_groups(text)
    membership: dict[str, list[str]] = {table: [] for table in tables}
    for raw_group, raw_members in groups:
        group = normalize_table(raw_group)
        if not IDENTIFIER_RE.fullmatch(group):
            errors.append(f"subject area must be lowercase snake_case: {raw_group}")
        if group.startswith("tbl_"):
            errors.append(f"subject area must not use physical table prefix: {raw_group}")
        for raw_member in raw_members:
            member = normalize_table(raw_member)
            if member not in seen:
                errors.append(f"TableGroup member is not declared: {raw_member}")
                continue
            membership.setdefault(member, []).append(group)

    if mode == "logical":
        lowered = text.lower()
        for vendor, patterns in VENDOR_TOKENS.items():
            if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in patterns):
                warnings.append(
                    f"logical mode contains {vendor}-leaning physical token(s); confirm project convention"
                )

        for original in raw_tables:
            local_name = _local_identifier(original)
            if local_name.startswith("tbl_"):
                message = f"logical model contains physical table prefix: {original}"
                if require_subject_area:
                    errors.append(message)
                else:
                    warnings.append(message)

        if require_subject_area:
            if not groups:
                errors.append("logical model requires at least one TableGroup subject area")
            for original, normalized in zip(raw_tables, tables):
                local_name = _local_identifier(original)
                if not IDENTIFIER_RE.fullmatch(local_name):
                    errors.append(f"logical table must be lowercase snake_case: {original}")
                areas = membership.get(normalized, [])
                if not areas:
                    errors.append(f"logical table is not assigned to a subject area: {original}")
                elif len(set(areas)) > 1:
                    errors.append(
                        f"logical table belongs to multiple subject areas: {original} -> {', '.join(sorted(set(areas)))}"
                    )

    return {
        "status": "blocked" if errors else "pass",
        "mode": mode,
        "require_subject_area": require_subject_area,
        "table_count": len(tables),
        "ref_count": len(REF_RE.findall(text)),
        "subject_area_count": len(groups),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lightweight structural guard for DBML edited by agents")
    parser.add_argument("--path", required=True)
    parser.add_argument("--mode", choices=("logical", "physical"), default="logical")
    parser.add_argument("--require-subject-area", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        result = {"status": "blocked", "errors": [f"DBML file not found: {path}"], "warnings": []}
    else:
        result = analyze(
            path.read_text(encoding="utf-8"),
            mode=args.mode,
            require_subject_area=args.require_subject_area,
        )

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"STATUS={result['status']}")
        print(f"MODE={result.get('mode', args.mode)}")
        print(f"TABLE_COUNT={result.get('table_count', 0)}")
        print(f"REF_COUNT={result.get('ref_count', 0)}")
        print(f"SUBJECT_AREA_COUNT={result.get('subject_area_count', 0)}")
        for item in result.get("warnings", []):
            print(f"WARNING={item}")
        for item in result.get("errors", []):
            print(f"ERROR={item}")

    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

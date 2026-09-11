#!/usr/bin/env python3
"""Lightweight DBML structural guard.

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
VENDOR_TOKENS = {
    "mssql": (r"\bnvarchar\b", r"\bdatetime2\b", r"\bidentity\b", r"\binclude\s*\("),
    "mysql": (r"\bauto_increment\b", r"\bunsigned\b"),
    "postgresql": (r"\bjsonb\b", r"\btimestamptz\b", r"\bserial\b"),
    "oracle": (r"\bnvarchar2\b", r"\bvarchar2\b", r"\bnumber\s*\("),
}


def normalize_table(name: str) -> str:
    return name.replace('"', '').lower()


def analyze(text: str, mode: str = "logical") -> dict[str, Any]:
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

    if mode == "logical":
        lowered = text.lower()
        for vendor, patterns in VENDOR_TOKENS.items():
            if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in patterns):
                warnings.append(
                    f"logical mode contains {vendor}-leaning physical token(s); confirm PHYSICAL mode or project convention"
                )

    return {
        "status": "blocked" if errors else "pass",
        "mode": mode,
        "table_count": len(tables),
        "ref_count": len(REF_RE.findall(text)),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lightweight structural guard for DBML edited by agents")
    parser.add_argument("--path", required=True)
    parser.add_argument("--mode", choices=("logical", "physical"), default="logical")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        result = {"status": "blocked", "errors": [f"DBML file not found: {path}"], "warnings": []}
    else:
        result = analyze(path.read_text(encoding="utf-8"), args.mode)

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"STATUS={result['status']}")
        print(f"MODE={result.get('mode', args.mode)}")
        print(f"TABLE_COUNT={result.get('table_count', 0)}")
        print(f"REF_COUNT={result.get('ref_count', 0)}")
        for item in result.get("warnings", []):
            print(f"WARNING={item}")
        for item in result.get("errors", []):
            print(f"ERROR={item}")

    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

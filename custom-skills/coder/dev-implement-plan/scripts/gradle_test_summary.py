#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


class SummaryError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Gradle JUnit XML produced by the Hermes isolated build directory."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument(
        "--results-root",
        help="Explicit test-results search root. Intended for diagnostics/tests; defaults to Hermes managed Gradle build output.",
    )
    parser.add_argument("--json", action="store_true", help="Emit one JSON object instead of key=value lines.")
    return parser.parse_args()


def run_git_hash(value: str) -> str:
    proc = subprocess.run(
        ["git", "hash-object", "--stdin"],
        input=value,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SummaryError((proc.stderr or proc.stdout).strip() or "git hash-object failed")
    return proc.stdout.strip()


def workspace_key(workspace: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", workspace.name or "workspace")
    return f"{name}-{run_git_hash(str(workspace.resolve()))[:12]}"


def default_results_root(workspace: Path) -> Path:
    build_root = Path(os.getenv("HERMES_GRADLE_BUILD_ROOT", "/opt/data/gradle/builds"))
    return build_root / workspace_key(workspace)


def result_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob("TEST-*.xml")
        if path.is_file() and "test-results" in path.parts
    )


def int_attr(element: ET.Element, name: str) -> int:
    raw = element.attrib.get(name, "0")
    try:
        return int(raw)
    except ValueError as exc:
        raise SummaryError(f"invalid JUnit {name}={raw!r}") from exc


def failure_details(suite: ET.Element) -> list[str]:
    details: list[str] = []
    for case in suite.findall(".//testcase"):
        failure = case.find("failure")
        error = case.find("error")
        node = failure if failure is not None else error
        if node is None:
            continue
        classname = case.attrib.get("classname", "").strip()
        name = case.attrib.get("name", "").strip()
        label = ".".join(part for part in (classname, name) if part) or "unknown-test"
        message = (node.attrib.get("message") or (node.text or "")).strip().replace("\n", " | ")
        if len(message) > 240:
            message = message[:237] + "..."
        details.append(f"{label}: {message}" if message else label)
    return details


def summarize(root: Path) -> dict[str, object]:
    files = result_files(root)
    if not files:
        return {
            "status": "MISSING",
            "results_root": str(root),
            "result_file_count": 0,
            "suite_count": 0,
            "tests_total": 0,
            "tests_failures": 0,
            "tests_errors": 0,
            "tests_skipped": 0,
            "tests_passed": 0,
            "failure_details": [],
        }

    suites = 0
    tests = 0
    failures = 0
    errors = 0
    skipped = 0
    details: list[str] = []
    for path in files:
        try:
            document = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            raise SummaryError(f"cannot parse JUnit XML {path}: {exc}") from exc

        elements: list[ET.Element]
        if document.tag.rsplit("}", 1)[-1] == "testsuite":
            elements = [document]
        else:
            elements = [
                element
                for element in document.findall(".//testsuite")
                if element.tag.rsplit("}", 1)[-1] == "testsuite"
            ]
        if not elements:
            raise SummaryError(f"JUnit XML has no testsuite: {path}")

        for suite in elements:
            suites += 1
            tests += int_attr(suite, "tests")
            failures += int_attr(suite, "failures")
            errors += int_attr(suite, "errors")
            skipped += int_attr(suite, "skipped")
            details.extend(failure_details(suite))

    passed = max(tests - failures - errors - skipped, 0)
    return {
        "status": "AVAILABLE",
        "results_root": str(root),
        "result_file_count": len(files),
        "suite_count": suites,
        "tests_total": tests,
        "tests_failures": failures,
        "tests_errors": errors,
        "tests_skipped": skipped,
        "tests_passed": passed,
        "failure_details": details,
    }


def emit(summary: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return
    print(f"TEST_SUMMARY_STATUS={summary['status']}")
    print(f"TEST_RESULTS_ROOT={summary['results_root']}")
    print(f"TEST_RESULT_FILE_COUNT={summary['result_file_count']}")
    print(f"TEST_SUITE_COUNT={summary['suite_count']}")
    print(f"TESTS_TOTAL={summary['tests_total']}")
    print(f"TESTS_FAILURES={summary['tests_failures']}")
    print(f"TESTS_ERRORS={summary['tests_errors']}")
    print(f"TESTS_SKIPPED={summary['tests_skipped']}")
    print(f"TESTS_PASSED={summary['tests_passed']}")
    details = list(summary["failure_details"])
    print(f"TEST_FAILURE_DETAIL_COUNT={len(details)}")
    for index, detail in enumerate(details, 1):
        print(f"TEST_FAILURE_{index}={detail}")


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(f"ERROR: workspace does not exist: {workspace}", file=sys.stderr)
        return 2
    root = Path(args.results_root).resolve() if args.results_root else default_results_root(workspace)
    try:
        summary = summarize(root)
    except SummaryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    emit(summary, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

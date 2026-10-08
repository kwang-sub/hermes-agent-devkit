#!/usr/bin/env python3
"""Canonical multiline Parent Tracking body formatter and validator.

This changes Task body text only. Native task_links and execution ordering
are never created or modified by the formatter.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

PARENT_ID_RE = re.compile(r"t_[A-Za-z0-9_-]{1,96}\Z")
INLINE_PARENT_RE = re.compile(r"Parent Task ID:\s*(t_[A-Za-z0-9_-]{1,96})(?![A-Za-z0-9_-])")
RELATION = "CHILD_WORK_UNIT"
HEADER = "Parent Tracking:"


class ParentTrackingError(ValueError):
    pass


def _nonfenced_lines(body: str) -> list[tuple[int, str]]:
    """Ignore documentation-only examples in Markdown code fences."""
    lines = []
    marker = None
    for index, line in enumerate(body.splitlines()):
        stripped = line.strip()
        if stripped.startswith(chr(96) * 3) or stripped.startswith("~~~"):
            candidate = stripped[:3]
            if marker is None:
                marker = candidate
                continue
            if marker == candidate:
                marker = None
                continue
        if marker is None:
            lines.append((index, line))
    return lines


def _references(body: str) -> set[str]:
    return {
        match.group(1)
        for _index, line in _nonfenced_lines(body)
        for match in INLINE_PARENT_RE.finditer(line)
    }


def _block(body: str) -> tuple[str, str | None] | None:
    """Mirror the dashboard's standalone-header + bullet-field contract."""
    lines = body.splitlines()
    eligible = {index for index, _ in _nonfenced_lines(body)}
    headers = [i for i, line in enumerate(lines) if i in eligible and line.strip() == HEADER]
    if len(headers) > 1:
        raise ParentTrackingError("multiple Parent Tracking blocks are not allowed")
    if not headers:
        return None
    fields = {}
    for index in range(headers[0] + 1, min(len(lines), headers[0] + 9)):
        item = lines[index].strip()
        if not item:
            continue
        if not item.startswith("- "):
            break
        key, colon, value = item[2:].partition(":")
        key = key.strip()
        if colon and key in {"Parent Task ID", "Parent Title", "Relation"}:
            if key in fields:
                raise ParentTrackingError("duplicate Parent Tracking field: " + key)
            fields[key] = value.strip()
    parent_id = fields.get("Parent Task ID", "")
    if not PARENT_ID_RE.fullmatch(parent_id):
        raise ParentTrackingError("Parent Tracking requires its own '- Parent Task ID: t_...' line")
    if fields.get("Relation") != RELATION:
        raise ParentTrackingError("Parent Tracking requires its own '- Relation: CHILD_WORK_UNIT' line")
    return parent_id, fields.get("Parent Title")


def _intent(body: str, title: str, expected_parent: str | None) -> bool:
    if expected_parent is not None:
        return True
    for index, line in _nonfenced_lines(body):
        if line.strip() == HEADER:
            return True
        if not INLINE_PARENT_RE.search(line):
            continue
        if "tracking only" in line.lower() or HEADER in line or RELATION in line:
            return True
        if title.lstrip().startswith("[자식]") and index <= 5:
            return True
        if line.lstrip().startswith("- Parent Task ID:") and index <= 12:
            return True
    return False


def validate_parent_body(body: str | None, *, expected_parent: str | None = None,
                         title: str = "") -> str | None:
    if expected_parent is not None and not PARENT_ID_RE.fullmatch(expected_parent):
        raise ParentTrackingError("Parent Task ID must be an exact t_... identifier")
    text = body or ""
    parsed = _block(text)
    references = _references(text)
    if expected_parent is not None and references - {expected_parent}:
        raise ParentTrackingError("body already references a different Parent Task ID")
    if parsed is None:
        if _intent(text, title, expected_parent):
            raise ParentTrackingError(
                "Parent Tracking must be a newline-delimited block; "
                "format with parent_tracking_body.py --parent-id before saving"
            )
        return None
    parent_id = parsed[0]
    if expected_parent is not None and parent_id != expected_parent:
        raise ParentTrackingError("Parent Tracking ID does not match the approved parent")
    if references - {parent_id}:
        raise ParentTrackingError("more than one Parent Task ID was found")
    return parent_id


def normalize_parent_body(body: str | None, *, title: str = "",
                          expected_parent: str | None = None,
                          parent_title: str | None = None) -> str | None:
    """Prepend a canonical block for clearly intended legacy inline references.

    Existing contents remain byte-for-byte as a suffix. A previous relationship
    cannot silently be switched to a different parent.
    """
    if body is None:
        return None
    if expected_parent is not None and not PARENT_ID_RE.fullmatch(expected_parent):
        raise ParentTrackingError("invalid Parent Task ID")
    parsed = _block(body)
    references = _references(body)
    if len(references) > 1:
        raise ParentTrackingError("multiple Parent Task IDs; cannot infer the parent")
    if parsed is not None:
        validate_parent_body(body, expected_parent=expected_parent, title=title)
        return body
    if not _intent(body, title, expected_parent):
        return body
    inferred = next(iter(references), None)
    if inferred is not None and expected_parent is not None and inferred != expected_parent:
        raise ParentTrackingError("refusing to reparent an existing reference")
    parent_id = expected_parent or inferred
    if not parent_id or not PARENT_ID_RE.fullmatch(parent_id):
        raise ParentTrackingError("Parent Tracking intent is missing a valid parent ID")
    if parent_title is not None and ("\n" in parent_title or "\r" in parent_title):
        raise ParentTrackingError("Parent Title must be a single line")
    sep = "\r\n" if "\r\n" in body else "\n"
    lines = [HEADER, "- Parent Task ID: " + parent_id]
    if parent_title:
        lines.append("- Parent Title: " + parent_title.strip())
    lines.append("- Relation: " + RELATION)
    block = sep.join(lines)
    output = block + (sep * 2 + body if body else sep)
    assert validate_parent_body(output, expected_parent=parent_id, title=title) == parent_id
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", default="-", help="Full existing body text or '-' for stdin")
    parser.add_argument("--output-file", help="Path for normalized body; stdout otherwise")
    parser.add_argument("--parent-id", help="Approved parent ID for explicit linking")
    parser.add_argument("--parent-title", help="Optional single-line parent title")
    parser.add_argument("--title", default="", help="Existing Task title for legacy detection")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.input_file == "-":
            body = sys.stdin.read()
        else:
            with Path(args.input_file).open("r", encoding="utf-8", newline="") as stream:
                body = stream.read()
        if args.check_only:
            parent = validate_parent_body(body, expected_parent=args.parent_id, title=args.title)
            print("PARENT_TRACKING=" + ("PASS" if parent else "NOT_APPLICABLE"))
            if parent:
                print("PARENT_TASK_ID=" + parent)
            return 0
        updated = normalize_parent_body(
            body, title=args.title, expected_parent=args.parent_id,
            parent_title=args.parent_title,
        )
        if args.output_file:
            with Path(args.output_file).open("w", encoding="utf-8", newline="") as stream:
                stream.write(updated or "")
        else:
            sys.stdout.write(updated or "")
        return 0
    except (ParentTrackingError, OSError, UnicodeError) as exc:
        print(f"PARENT_TRACKING=BLOCKED\nREASON={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

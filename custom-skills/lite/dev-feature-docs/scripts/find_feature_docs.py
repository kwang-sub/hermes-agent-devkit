#!/usr/bin/env python3
"""Collect bounded, read-only feature-document candidates; never infer a binding."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import unicodedata
from pathlib import Path
from typing import Any

MAX_ENTRIES = 512
MAX_FILES = 80
MAX_BYTES = 65536
MAX_RESULTS = 12
PREVIEW_CHARS = 1600


def normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def safe_file(root: Path, relative: str) -> Path:
    """Accept only regular Markdown files contained in the selected project."""
    supplied = Path(relative)
    if supplied.is_absolute() or ".." in supplied.parts or "\\" in relative:
        raise ValueError("Use a canonical project-relative path without traversal")
    candidate = root / supplied
    # Do not traverse symlinked files or directories, even within the project.
    current = root
    for part in supplied.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink paths are not scanned")
    resolved = candidate.resolve(strict=True)
    resolved.relative_to(root)
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode) or resolved.suffix.casefold() != ".md":
        raise ValueError("Only regular Markdown files are supported")
    if info.st_size > MAX_BYTES:
        raise ValueError("Document exceeds the bounded read limit")
    return resolved


def read_document(root: Path, relative: str) -> dict[str, Any]:
    path = safe_file(root, relative)
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Document grew beyond the bounded read limit")
    text = data.decode("utf-8-sig")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
    return {
        "path": path.relative_to(root).as_posix(),
        "title": title,
        "sha256": hashlib.sha256(data).hexdigest(),
        "preview": text[:PREVIEW_CHARS],
        "preview_truncated": len(text) > PREVIEW_CHARS,
        "_search": normalized(path.stem + "\n" + text),
    }


def inventory(root: Path, warnings: list[str]) -> list[str]:
    """Never descend outside docs/features or follow a symlink directory."""
    feature_root = root / "docs" / "features"
    if (root / "docs").is_symlink() or feature_root.is_symlink():
        warnings.append("Feature directory is a symlink; automatic scan skipped")
        return []
    if not feature_root.is_dir():
        return []
    pending = [feature_root]
    found: list[str] = []
    entries_seen = 0
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entries_seen += 1
                    if entries_seen > MAX_ENTRIES:
                        warnings.append("Entry limit reached; candidate inventory is incomplete")
                        return sorted(found)
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if not entry.name.startswith("."):
                            pending.append(Path(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    path = Path(entry.path)
                    if path.suffix.casefold() != ".md" or path.name.casefold() == "readme.md":
                        continue
                    if len(found) >= MAX_FILES:
                        warnings.append("File limit reached; candidate inventory is incomplete")
                        return sorted(found)
                    found.append(path.relative_to(root).as_posix())
        except OSError:
            warnings.append("A feature directory could not be read")
    return sorted(found)


def collect(project_root: str, query: str = "", documents: list[str] | None = None,
            approved_documents: list[str] | None = None) -> dict[str, Any]:
    """Explicit paths take precedence. Missing bindings never silently remap."""
    result: dict[str, Any] = {
        "status": "ok", "mode": "discovery", "read_only": True,
        "binding_decided": False, "index": None, "candidates": [], "warnings": [],
    }
    warnings: list[str] = result["warnings"]
    try:
        root = Path(project_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Selected project root is not a directory")
    except (OSError, ValueError, RuntimeError):
        result.update(status="unavailable", warnings=["Selected project root is unavailable"])
        return result

    requested = documents or approved_documents
    if requested:
        result["mode"] = "explicit" if documents else "approved-reuse"
        paths = list(dict.fromkeys(requested))
        if len(paths) > MAX_FILES:
            warnings.append("Explicit path limit reached; remaining paths were not read")
            paths = paths[:MAX_FILES]
    else:
        try:
            index = read_document(root, "docs/features/README.md")
            index.pop("_search")
            result["index"] = index
        except FileNotFoundError:
            pass
        except (OSError, ValueError, RuntimeError):
            warnings.append("Feature index unavailable; individual documents are still considered")
        paths = inventory(root, warnings)

    terms = list(dict.fromkeys(re.findall(r"\w+", normalized(query))))
    candidates = []
    for relative in paths:
        try:
            doc = read_document(root, relative)
        except (OSError, ValueError, RuntimeError):
            warnings.append("Document unavailable or outside read policy: " + relative)
            continue
        search_text = doc.pop("_search")
        doc["matched_terms"] = [term for term in terms if term in search_text]
        if requested or not terms or doc["matched_terms"]:
            candidates.append(doc)
    # Ranking is retrieval assistance only, never semantic relevance or approval.
    if not requested:
        candidates.sort(key=lambda item: (-len(item["matched_terms"]), item["path"]))
    if len(candidates) > MAX_RESULTS:
        warnings.append("Result limit reached; additional candidates were not returned")
    result["candidates"] = candidates[:MAX_RESULTS]
    if warnings:
        result["status"] = "partial"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--document", action="append", default=[])
    parser.add_argument("--approved-document", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(collect(args.project_root, args.query, args.document,
                             args.approved_document), ensure_ascii=False, indent=2))
    # Retrieval failure is advisory; it cannot change a task's lifecycle state.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

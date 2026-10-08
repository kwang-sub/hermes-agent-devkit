"""Shared scoped Git comparison and content fingerprint for Coder/Reviewer.

Runs a single semantic --numstat comparison for an already-approved path set.
Does not perform repository-wide discovery or silently expand review scope.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import subprocess


class ScopeError(RuntimeError):
    pass


def semantic_tracked_paths(root: Path, base: str, paths: list[str]) -> list[str]:
    """Exclude CRLF-only noise without one Git subprocess per changed file."""
    selected = sorted(set(paths))
    if not selected:
        return []
    proc = subprocess.run(
        ["git", "-C", str(root), "diff", "--numstat", "-z", "--no-renames",
         "--ignore-cr-at-eol", base, "--", *selected],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode != 0:
        raise ScopeError(
            proc.stderr.decode("utf-8", "replace").strip()
            or f"scoped semantic Git diff failed: rc={proc.returncode}"
        )
    effective: list[str] = []
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        additions, sep, remainder = entry.partition(b"\t")
        deletions, sep2, encoded_path = remainder.partition(b"\t")
        if not sep or not sep2 or not encoded_path or not additions or not deletions:
            raise ScopeError("malformed Git --numstat -z output")
        effective.append(os.fsdecode(encoded_path))
    return sorted(set(effective))


def scope_sha256(root: Path, paths: list[str]) -> str:
    """Preserve the established EOL-normalized review fingerprint format."""
    digest = sha256()
    for path in sorted(set(paths)):
        file_path = root / path
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        if file_path.is_file():
            digest.update(b"F\0")
            digest.update(file_path.read_bytes().replace(b"\r\n", b"\n"))
        else:
            digest.update(b"MISSING\0")
        digest.update(b"\0")
    return digest.hexdigest()

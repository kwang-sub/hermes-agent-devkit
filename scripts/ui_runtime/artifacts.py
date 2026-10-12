"""Per-attempt immutable evidence; the root report is only a latest snapshot."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import tempfile
import uuid


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def attempt_directory(root: Path) -> Path:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime('attempt-%Y%m%dT%H%M%S-') + uuid.uuid4().hex[:12]
    path = root / name
    path.mkdir(mode=0o700)
    return path


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inside(root: Path, path: Path) -> Path:
    root, path = root.resolve(), path.resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('artifact must be a file within the owned directory')
    return path

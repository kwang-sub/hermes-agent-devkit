#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "screen_spec_guard.py"
SPEC = importlib.util.spec_from_file_location("screen_spec_guard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def image_spec(reference: str = "./reference.png", status: str = "APPROVED") -> str:
    return f"""---
screen: dashboard
status: {status}
source: IMAGE
reference: {reference}
fidelity: VISUAL
viewport: 1440x1024
---
# Dashboard
"""


def test_valid_image_reference() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = root / "docs/ui/screens/dashboard/screen-spec.md"
        write(spec, image_spec())
        (spec.parent / "reference.png").write_bytes(b"png")
        result = MODULE.validate(spec)
        assert result["source"] == "IMAGE"
        assert result["status"] == "APPROVED"


def test_missing_image_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "screen-spec.md"
        write(spec, image_spec())
        try:
            MODULE.validate(spec)
        except MODULE.SpecError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("missing IMAGE reference must be blocked")


def test_valid_figma_reference() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "screen-spec.md"
        write(spec, """---
screen: dashboard
status: REFERENCE
source: FIGMA
reference: https://www.figma.com/design/abc/file?node-id=1-2
fidelity: STRUCTURE
viewport: UNKNOWN
---
# Dashboard
""")
        result = MODULE.validate(spec)
        assert result["source"] == "FIGMA"
        assert result["status"] == "REFERENCE"


def test_invalid_enums_are_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "screen-spec.md"
        write(spec, image_spec(status="FINAL"))
        (spec.parent / "reference.png").write_bytes(b"png")
        try:
            MODULE.validate(spec)
        except MODULE.SpecError as exc:
            assert "invalid status" in str(exc)
        else:
            raise AssertionError("invalid design status must be blocked")


if __name__ == "__main__":
    test_valid_image_reference()
    test_missing_image_is_blocked()
    test_valid_figma_reference()
    test_invalid_enums_are_blocked()
    print("[PASS] Screen specification guard tests")

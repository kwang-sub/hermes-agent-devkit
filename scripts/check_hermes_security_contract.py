#!/usr/bin/env python3
"""Require explicit legacy-Tirith or retired-Tirith upstream security contracts."""
import argparse
import ast
import tempfile
from pathlib import Path

CORE = {
    "tools/approval_detection.py": ("def detect_hardline_command(", "def detect_dangerous_command("),
    "tools/approval_floors.py": ("def _hardline_block_result(",),
}
MARKER = "DEVKIT_TIRITH_PROFILE_GUARD_V1"

def check(root: Path) -> str:
    for name, markers in CORE.items():
        source = (root / name).read_text(encoding="utf-8")
        ast.parse(source, filename=name)
        for marker in markers:
            if marker not in source:
                raise RuntimeError(f"missing core security guard: {name}: {marker}")
    legacy = root / "tools/tirith_security.py"
    if legacy.is_file():
        source = legacy.read_text(encoding="utf-8")
        ast.parse(source, filename=str(legacy))
        if MARKER not in source:
            raise RuntimeError("legacy Tirith exists but DevKit profile guard not applied")
        mode = "legacy-tirith-patched"
    else:
        migration = (root / "hermes_cli/config_migrations.py").read_text(encoding="utf-8")
        if "_RETIRED_TIRITH_KEYS" not in migration or "tirith_fail_open" not in migration:
            raise RuntimeError("Tirith absent without recognized upstream retirement contract")
        mode = "upstream-tirith-retired-core-approval"
    print(f"SECURITY_CONTRACT={mode}")
    return mode

def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, markers in CORE.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(marker + "value):\n    pass" for marker in markers), encoding="utf-8")
        path = root / "hermes_cli/config_migrations.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('_RETIRED_TIRITH_KEYS = ("tirith_fail_open",)\n', encoding="utf-8")
        assert check(root) == "upstream-tirith-retired-core-approval"
        legacy = root / "tools/tirith_security.py"
        legacy.write_text("# " + MARKER + "\n", encoding="utf-8")
        assert check(root) == "legacy-tirith-patched"
        legacy.write_text("# unpatched\n", encoding="utf-8")
        try:
            check(root)
        except RuntimeError:
            pass
        else:
            raise AssertionError("unpatched legacy guard must fail closed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.root:
        check(args.root)
    else:
        parser.error("provide --root or --self-test")

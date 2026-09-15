#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts" / "patch_hermes_tui_file_signature.py"
DOCKERFILE = ROOT / "Dockerfile"
LATEST_COMPAT = ROOT / ".github" / "workflows" / "latest-hermes-compat.yml"


def read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"[FAIL] missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8-sig")


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"[FAIL] {label} missing: {', '.join(missing)}")


def main() -> int:
    patch = read(PATCH)
    dockerfile = read(DOCKERFILE)
    latest = read(LATEST_COMPAT)

    require(
        patch,
        (
            "from utils import file_signature",
            "file_signature(",
            "has_module_import",
            "already-patched",
            "not-needed",
            "--self-test",
            "py_compile.compile",
        ),
        "Hermes TUI file_signature patch",
    )

    require(
        dockerfile,
        (
            "patch_hermes_tui_file_signature.py --self-test",
            "patch_hermes_tui_file_signature.py /opt/hermes/hermes_cli/cli_tui_mixin.py",
            "/opt/hermes/hermes_cli/cli_tui_mixin.py",
            "HERMES_DEFER_AGENT_STARTUP=1",
            "_tui_init_run_state()",
            "devkit-tui-config.yaml",
        ),
        "Dockerfile TUI startup guard",
    )

    require(
        latest,
        (
            "Verify Latest Hermes Compatibility",
            "HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest",
            "bash scripts/verify_latest_hermes_compat.sh",
        ),
        "latest Hermes compatibility CI",
    )

    print("[PASS] latest Hermes TUI file_signature patch + real TUI init smoke contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

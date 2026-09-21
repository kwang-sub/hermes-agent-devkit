#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts" / "patch_hermes_tui_semantic_input.py"
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


def forbid(text: str, terms: tuple[str, ...], label: str) -> None:
    present = [term for term in terms if term in text]
    if present:
        raise SystemExit(f"[FAIL] {label} still contains fixed-layout terms: {', '.join(present)}")


def main() -> int:
    patch = read(PATCH)
    dockerfile = read(DOCKERFILE)
    latest = read(LATEST_COMPAT)

    require(
        patch,
        (
            "def discover_source_paths",
            "def resolve_source_paths",
            "--search-root",
            "_is_tui_candidate",
            "_is_session_candidate",
            "cannot uniquely discover Hermes Clarify sources",
            "--self-test",
            "py_compile.compile",
        ),
        "Hermes TUI semantic-input discovery patch",
    )

    require(
        dockerfile,
        (
            "patch_hermes_tui_semantic_input.py --self-test",
            "patch_hermes_tui_semantic_input.py --search-root /opt/hermes",
            "patch_hermes_tui_semantic_input.py --check-only --search-root /opt/hermes",
            "/opt/hermes/.venv/bin/hermes --help",
        ),
        "Dockerfile TUI layout-independent guard",
    )
    forbid(
        dockerfile,
        (
            "patch_hermes_tui_file_signature.py",
            "/opt/hermes/hermes_cli/cli_tui_mixin.py",
            "/opt/hermes/hermes_cli/cli_session_mixin.py",
        ),
        "Dockerfile TUI layout-independent guard",
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

    print("[PASS] latest Hermes path-independent TUI semantic patch contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

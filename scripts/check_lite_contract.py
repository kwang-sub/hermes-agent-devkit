#!/usr/bin/env python3
"""Assert Lite runs separately from preserved Standard Flow contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check():
    read = lambda p: (ROOT / p).read_text(encoding="utf-8")
    ps, sh = read("updatekit_lite.ps1"), read("updatekit_lite.sh")
    adapter = read("scripts/lite_mode.py")
    standard_root = read("AGENTS.md")
    standard_common = read("shared/AGENTS.common.md").rstrip()
    lite_policy = read("lite/AGENTS.md")
    lite_session = read("custom-skills/lite/dev-lite-session/SKILL.md")
    lite_review = read("custom-skills/lite/dev-lite-review/SKILL.md")
    compose = read("compose.yml")

    # Never replace the Standard authoritative root policy with Lite rules.
    start = standard_root.index("<!-- HERMES-COMMON:START -->")
    end = standard_root.index("<!-- HERMES-COMMON:END -->") + len("<!-- HERMES-COMMON:END -->")
    assert standard_root[start:end].rstrip() == standard_common
    for item in (
        "Orchestrator: 모든 새 mutation request의 실행 진입점",
        "Coder: **Kanban에 할당된 Task만** 구현",
        "Direct Flow",
        "Standard Flow",
    ):
        assert item in standard_root and item in standard_common, item

    required = {
        "PowerShell": (ps, (
            '[string]$Mode = "lite"', 'Adapter "apply"', 'Adapter "restore"',
            "CheckGit", "CheckContainer", "--workdir /workspace/hermes-agent-devkit/lite",
            "/opt/hermes/.venv/bin/hermes -p default", '"status"', '"standard"', '"lite"',
        )),
        "Bash": (sh, ("set -euo pipefail", "powershell.exe", "updatekit_lite.ps1")),
        "Adapter": (adapter, (
            "?mode=ro", "guard(root)", "profile-state.json", "config.yaml",
            "safe_dump", "restore(root)", "dev-lite-session", "auto_load",
            "STANDARD_DIRS", "migrate_legacy_overlay",
        )),
        "Lite workdir rules": (lite_policy, (
            "Kanban", "선택적", "직접 개발", "dev-lite-review",
        )),
        "Lite autoload skill": (lite_session, (
            "name: dev-lite-session", "Orchestrator", "Kanban", "직접 개발",
        )),
        "Lite review skill": (lite_review, (
            "dev-lite-review", "자체 리뷰", "독립 검증",
        )),
        "Compose": (compose, (
            "hermes-data", "/opt/data", "/workspace",
            "/opt/custom-skills", "/opt/data/shared",
        )),
    }
    for label, (value, terms) in required.items():
        for term in terms:
            assert term in value, f"{label} missing {term!r}"

    for term in ('docker compose down', '"down", "-v"', 'git reset',
                 'git clean', 'git stash', 'docker volume rm',
                 'Remove-Item /opt/data'):
        assert term not in ps, f"Unsafe PowerShell action: {term}"

    for term in ("profiles/coder/config.yaml", "profiles/reviewer/config.yaml",
                 "profiles/orchestrator/config.yaml", "DELETE FROM tasks",
                 "UPDATE tasks SET", "shutil.rmtree"):
        assert term not in adapter, f"Unsafe adapter action: {term}"

    print("[PASS] Standard Flow is intact, Lite policy isolated and guarded")


if __name__ == "__main__":
    check()

#!/usr/bin/env python3
"""Static safety assertions for branch-local Hermes Lite scripts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    ps = (ROOT / "updatekit_lite.ps1").read_text(encoding="utf-8")
    sh = (ROOT / "updatekit_lite.sh").read_text(encoding="utf-8")
    adapter = (ROOT / "scripts/lite_mode.py").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    common = (ROOT / "shared/AGENTS.common.md").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
    skill = (ROOT / "custom-skills/lite/dev-lite-review/SKILL.md").read_text(encoding="utf-8")

    required = {
        "PowerShell": (ps, ("[string]$Mode = \"lite\"", 'Adapter "apply"',
                            'Adapter "restore"', 'Assert', "CheckGit", "CheckContainer",
                            '"status"', '"standard"', '"lite"')),
        "Bash": (sh, ("set -euo pipefail", "powershell.exe", "updatekit_lite.ps1")),
        "Adapter": (adapter, ("?mode=ro", "guard(root)", "profile-state.json",
                              "config.yaml", "safe_dump", "restore(root)",
                              "applied", "before", "kanban")),
        "Lite Rules": (common, ("Kanban", "선택적", "직접 개발", "dev-lite-review")),
        "Devkit Rules": (agents, ("Lite", "default 프로필", "Kanban")),
        "Review skill": (skill, ("dev-lite-review", "자체 리뷰", "독립 검증")),
        "Compose": (compose, ("hermes-data", "/opt/data", "/workspace",
                              "/opt/custom-skills", "/opt/data/shared")),
    }
    for label, (text, terms) in required.items():
        for term in terms:
            assert term in text, f"{label} missing {term!r}"

    for forbidden in (
        'docker compose down', '"down", "-v"', 'git reset', 'git clean',
        'git stash', 'docker volume rm', 'Remove-Item /opt/data'
    ):
        assert forbidden not in ps, f"Unsafe operation in Lite PowerShell: {forbidden}"

    # Role profiles, Kanban DB and project files must not be rewritten by Lite.
    for forbidden in ("profiles/coder/config.yaml", "profiles/reviewer/config.yaml",
                      "profiles/orchestrator/config.yaml", "DELETE FROM tasks",
                      "UPDATE tasks SET", "shutil.rmtree"):
        assert forbidden not in adapter, f"Unsafe adapter operation: {forbidden}"

    assert "Orchestrator → Kanban → Coder → Reviewer" in agents
    assert "Standard Flow는 **자동 실행하지 않는다." in common
    print("[PASS] Hermes Lite static contract")


if __name__ == "__main__":
    check()

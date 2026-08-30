#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_skills.py"


def write_profile(root: Path, profile: str, external_dir: Path) -> None:
    profile_home = root / profile
    profile_home.mkdir(parents=True, exist_ok=True)
    (profile_home / "config.yaml").write_text(
        "skills:\n"
        "  external_dirs:\n"
        f"    - {external_dir}\n",
        encoding="utf-8",
    )


def write_skill(root: Path, name: str, platforms: str = "[linux]") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: test skill {name}\n"
        f"platforms: {platforms}\n"
        "---\n\n"
        "# Test\n",
        encoding="utf-8",
    )


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_filters_to_cross_profile_intersection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        profiles = base / "profiles"
        coder = base / "custom" / "coder"
        reviewer = base / "custom" / "reviewer"
        write_profile(profiles, "coder", coder)
        write_profile(profiles, "reviewer", reviewer)
        write_skill(coder, "dev-spring-data")
        write_skill(coder, "dev-spring-test")
        write_skill(reviewer, "dev-spring-data")

        result = run(
            "--profiles-root", str(profiles),
            "--profile", "coder",
            "--profile", "reviewer",
            "--skill", "dev-spring-data",
            "--skill", "dev-spring-test",
            "--skill", "java-project-conventions",
        )

        assert result.returncode == 0, result.stderr
        assert "VALIDATED_SKILLS=dev-spring-data" in result.stdout
        assert "REJECTED_SKILLS=dev-spring-test,java-project-conventions" in result.stdout
        assert "MISSING_CODER=java-project-conventions" in result.stdout
        assert "MISSING_REVIEWER=dev-spring-test,java-project-conventions" in result.stdout


def test_strict_mode_blocks_rejected_skill() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        profiles = base / "profiles"
        coder = base / "custom" / "coder"
        write_profile(profiles, "coder", coder)
        write_skill(coder, "dev-spring-data")

        result = run(
            "--profiles-root", str(profiles),
            "--profile", "coder",
            "--skill", "missing-skill",
            "--strict",
        )

        assert result.returncode == 3
        assert "REJECTED_SKILLS=missing-skill" in result.stdout


def test_profile_local_skill_is_discovered() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        profiles = base / "profiles"
        coder_home = profiles / "coder"
        coder_home.mkdir(parents=True, exist_ok=True)
        (coder_home / "config.yaml").write_text("skills:\n  external_dirs: []\n", encoding="utf-8")
        write_skill(coder_home / "skills", "local-skill")

        result = run(
            "--profiles-root", str(profiles),
            "--profile", "coder",
            "--skill", "local-skill",
        )

        assert result.returncode == 0
        assert "VALIDATED_SKILLS=local-skill" in result.stdout
        assert "REJECTED_SKILLS=" in result.stdout


def test_missing_profile_config_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = run(
            "--profiles-root", str(Path(tmp) / "profiles"),
            "--profile", "coder",
            "--skill", "dev-spring-data",
        )

        assert result.returncode == 2
        assert "ERROR=profile config not found:" in result.stdout


def main() -> int:
    tests = [
        test_filters_to_cross_profile_intersection,
        test_strict_mode_blocks_rejected_skill,
        test_profile_local_skill_is_discovered,
        test_missing_profile_config_fails_closed,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

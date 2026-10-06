#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    failures = []
    launcher = ROOT / "scripts/hermes-maven"
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    if not launcher.is_file():
        failures.append("missing scripts/hermes-maven")
    else:
        text = launcher.read_text(encoding="utf-8")
        required = (
            'HERMES_MAVEN_ROOT:-/opt/data/maven',
            'HERMES_MAVEN_REPO_ROOT:-$root/repository',
            '.mvn/wrapper/maven-wrapper.properties',
            '-Dmaven.repo.local=$repo',
            'workspace-$workspace_key.lock',
            'overriding maven.repo.local is not allowed',
            '.hermes/toolchain.env',
        )
        failures.extend(f"hermes-maven missing: {term}" for term in required if term not in text)
    for term in (
        "ENV HERMES_MAVEN_ROOT=/opt/data/maven",
        "ENV HERMES_MAVEN_REPO_ROOT=/opt/data/maven/repository",
        "COPY --chmod=0755 scripts/hermes-maven /usr/local/bin/hermes-maven",
    ):
        if term not in dockerfile.splitlines():
            failures.append(f"Dockerfile missing: {term}")
    java = (ROOT / "scripts/hermes-java").read_text(encoding="utf-8")
    if 'exec "$maven_launcher" "$@"' not in java:
        failures.append("hermes-java must delegate Maven before raw execution")
    if java.index('exec "$maven_launcher" "$@"') > java.index('gradle_root='):
        failures.append("Maven delegation must precede Gradle state initialization")
    for path in (
        "AGENTS.md", "shared/AGENTS.common.md",
        "custom-skills/coder/dev-implement-plan/SKILL.md",
        "custom-skills/reviewer/dev-code-review/SKILL.md",
        "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md",
    ):
        if "maven-worker-runtime.md" not in (ROOT / path).read_text(encoding="utf-8"):
            failures.append(f"Maven canonical worker contract not linked: {path}")
    for path, term in (
        ("Dockerfile", "COPY scripts/devkit_worker_startup.py /opt/hermes/hermes_cli/devkit_worker_startup.py"),
        ("scripts/patch_hermes_kanban_session_affinity.py", "cmd = with_worker_startup(cmd, profile_arg)"),
        ("scripts/verify-container-runtime.ps1", "hermes-maven"),
    ):
        if term not in (ROOT / path).read_text(encoding="utf-8"):
            failures.append(f"Maven runtime delivery missing: {path}")
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] Maven launcher isolation contract")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

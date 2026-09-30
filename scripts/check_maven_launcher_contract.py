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
        if term not in dockerfile:
            failures.append(f"Dockerfile missing: {term}")
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] Maven launcher isolation contract")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


GIT_ATTRIBUTES_RULES = (
    ("gradlew", "text eol=lf"),
    ("mvnw", "text eol=lf"),
    ("*.sh", "text eol=lf"),
    ("*.bat", "text eol=crlf"),
    ("*.cmd", "text eol=crlf"),
)


class PreflightError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PreflightError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}"
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and prepare a repository for Hermes development work."
    )
    parser.add_argument("--repo", required=True, help="Absolute Git repository root")
    parser.add_argument(
        "--no-gitattributes",
        action="store_true",
        help="Validate the environment without creating/updating .gitattributes",
    )
    return parser.parse_args()


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise PreflightError(f"required development tool is not available on PATH: {name}")


def resolve_repo(value: str) -> Path:
    requested = Path(value)
    if not requested.is_absolute():
        raise PreflightError(f"--repo must be absolute: {requested}")
    if not requested.is_dir():
        raise PreflightError(f"repository path does not exist or is not a directory: {requested}")

    result = run(["git", "-C", str(requested), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise PreflightError(f"not a Git repository: {requested}")

    root = Path(result.stdout.strip()).resolve()
    if root != requested.resolve():
        raise PreflightError(
            f"--repo must point at the Git repository root; requested={requested.resolve()}, root={root}"
        )
    return root


def assert_repository_writable(repo: Path) -> None:
    try:
        fd, name = tempfile.mkstemp(prefix=".hermes-write-test-", dir=repo)
        os.close(fd)
        probe = Path(name)
        probe.write_text("hermes-write-test\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise PreflightError(
            f"repository is not writable by the Hermes runtime user: {repo}: {exc}"
        ) from exc
    print(f"[OK] Workspace writable: {repo}")


def detect_build(repo: Path) -> str:
    if (repo / "gradlew").is_file() or any(
        (repo / name).is_file()
        for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
    ):
        return "gradle"
    if (repo / "mvnw").is_file() or (repo / "pom.xml").is_file():
        return "maven"
    return "other"


def validate_java_toolchain(build_type: str) -> None:
    if build_type not in {"gradle", "maven"}:
        print("[SKIP] Java toolchain: no Gradle/Maven project detected")
        return

    require_tool("java")
    require_tool("javac")
    java = run(["java", "-version"], check=False)
    if java.returncode != 0:
        raise PreflightError("java is present but `java -version` failed")
    javac = run(["javac", "-version"], check=False)
    if javac.returncode != 0:
        raise PreflightError("javac is present but `javac -version` failed")

    java_version = (java.stderr or java.stdout).splitlines()[0].strip()
    javac_version = (javac.stdout or javac.stderr).splitlines()[0].strip()
    print(f"[OK] Java runtime: {java_version}")
    print(f"[OK] Java compiler: {javac_version}")


def _rule_state(lines: list[str], pattern: str, expected_eol: str) -> tuple[bool, list[str]]:
    desired = False
    conflicts: list[str] = []
    expected = expected_eol.split("eol=", 1)[1]

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if not parts or parts[0] != pattern:
            continue

        attrs = parts[1:]
        if "text" in attrs and f"eol={expected}" in attrs:
            desired = True
        for attr in attrs:
            if attr.startswith("eol=") and attr != f"eol={expected}":
                conflicts.append(stripped)

    return desired, conflicts


def ensure_gitattributes(repo: Path) -> str:
    path = repo / ".gitattributes"
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    missing: list[str] = []

    for pattern, attributes in GIT_ATTRIBUTES_RULES:
        desired, conflicts = _rule_state(lines, pattern, attributes)
        if conflicts:
            conflict_text = "; ".join(conflicts)
            raise PreflightError(
                f".gitattributes conflicts with Hermes EOL policy for {pattern}: {conflict_text}. "
                "Resolve the repository policy explicitly; bootstrap will not overwrite it."
            )
        if not desired:
            missing.append(f"{pattern} {attributes}")

    if not missing:
        print(f"[OK] .gitattributes EOL policy: {path}")
        return "unchanged"

    block = ["# Hermes development defaults", *missing]
    if original:
        updated = original.rstrip("\r\n") + "\n\n" + "\n".join(block) + "\n"
        action = "updated"
    else:
        updated = "\n".join(block) + "\n"
        action = "created"

    path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"[{action.upper()}] .gitattributes EOL policy: {path}")
    return action


def inspect_wrapper_eol(repo: Path, build_type: str) -> list[str]:
    warnings: list[str] = []
    wrapper_name = "gradlew" if build_type == "gradle" else "mvnw" if build_type == "maven" else ""
    if not wrapper_name:
        return warnings

    wrapper = repo / wrapper_name
    if not wrapper.is_file():
        warnings.append(f"{build_type} project detected but {wrapper_name} is missing")
        return warnings

    data = wrapper.read_bytes()
    if b"\r\n" in data:
        warnings.append(
            f"{wrapper_name} currently contains CRLF. .gitattributes now requires LF, but bootstrap "
            "does not renormalize tracked files automatically. Re-checkout/renormalize this wrapper explicitly."
        )
    else:
        print(f"[OK] Wrapper EOL: {wrapper_name}=LF")
    return warnings


def main() -> int:
    args = parse_args()
    require_tool("git")
    require_tool("python3")

    repo = resolve_repo(args.repo)
    print("== Hermes Development Environment Preflight ==")
    print(f"Repository : {repo}")

    assert_repository_writable(repo)
    build_type = detect_build(repo)
    print(f"Build      : {build_type}")
    validate_java_toolchain(build_type)

    gitattributes = "skipped"
    if not args.no_gitattributes:
        gitattributes = ensure_gitattributes(repo)

    warnings = inspect_wrapper_eol(repo, build_type)
    for warning in warnings:
        print(f"[WARN] {warning}")

    print("")
    print(f"BUILD_TYPE={build_type}")
    print(f"GITATTRIBUTES={gitattributes}")
    print(f"WARNINGS={len(warnings)}")
    print("PREFLIGHT_STATUS=ready" if not warnings else "PREFLIGHT_STATUS=ready-with-warnings")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreflightError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
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
SUPPORTED_JAVA_VERSIONS = (8, 17, 21)
JAVA_HOMES = {
    8: Path(os.getenv("JAVA_HOME_8", "/opt/jdks/temurin-8")),
    17: Path(os.getenv("JAVA_HOME_17", "/opt/jdks/temurin-17")),
    21: Path(os.getenv("JAVA_HOME_21", "/opt/jdks/temurin-21")),
}
DEFAULT_JAVA_VERSION = 17
TOOLCHAIN_MARKER = "# managed-by: dev-project-bootstrap"


class PreflightError(RuntimeError):
    pass


def run(
    cmd: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True, env=env)
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


def _normalize_java_version(raw: str) -> int | None:
    value = raw.strip().strip("'\"")
    if value in {"1.8", "8"}:
        return 8
    match = re.search(r"(?:VERSION_)?(?:1_)?(8|17|21)\b", value)
    return int(match.group(1)) if match else None


def _collect_gradle_java_versions(repo: Path) -> set[int]:
    versions: set[int] = set()
    candidates = [
        repo / "build.gradle",
        repo / "build.gradle.kts",
        repo / "gradle.properties",
    ]
    patterns = (
        r"JavaLanguageVersion\.of\(\s*(8|17|21)\s*\)",
        r"jvmToolchain\(\s*(8|17|21)\s*\)",
        r"(?:sourceCompatibility|targetCompatibility)\s*=\s*([^\r\n]+)",
        r"(?:sourceCompatibility|targetCompatibility)\s+([^\r\n]+)",
    )
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                raw = match.group(1)
                version = _normalize_java_version(raw)
                if version is not None:
                    versions.add(version)
    return versions


def _collect_maven_java_versions(repo: Path) -> set[int]:
    pom = repo / "pom.xml"
    if not pom.is_file():
        return set()
    text = pom.read_text(encoding="utf-8", errors="replace")
    versions: set[int] = set()
    for tag in (
        "java.version",
        "maven.compiler.release",
        "maven.compiler.source",
        "maven.compiler.target",
    ):
        for match in re.finditer(rf"<{re.escape(tag)}>\s*([^<]+?)\s*</{re.escape(tag)}>", text):
            version = _normalize_java_version(match.group(1))
            if version is not None:
                versions.add(version)
    return versions


def detect_java_target(repo: Path, build_type: str) -> tuple[int, list[str]]:
    warnings: list[str] = []
    if build_type == "gradle":
        versions = _collect_gradle_java_versions(repo)
    elif build_type == "maven":
        versions = _collect_maven_java_versions(repo)
    else:
        return DEFAULT_JAVA_VERSION, warnings

    if len(versions) > 1:
        raise PreflightError(
            "conflicting Java target versions were detected in the repository: "
            + ", ".join(str(v) for v in sorted(versions))
            + ". Resolve the project build configuration explicitly."
        )
    if not versions:
        warnings.append(
            f"Java target version was not detected; using DevKit default Java {DEFAULT_JAVA_VERSION}."
        )
        return DEFAULT_JAVA_VERSION, warnings

    version = next(iter(versions))
    if version not in SUPPORTED_JAVA_VERSIONS:
        raise PreflightError(
            f"detected Java target {version}, but this DevKit provides only "
            + ", ".join(str(v) for v in SUPPORTED_JAVA_VERSIONS)
        )
    return version, warnings


def gradle_wrapper_version(repo: Path) -> tuple[int, int] | None:
    properties = repo / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not properties.is_file():
        return None
    text = properties.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"gradle-(\d+)\.(\d+)(?:\.\d+)?-", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def select_runtime_java(repo: Path, build_type: str, target_java: int) -> tuple[int, list[str]]:
    warnings: list[str] = []
    runtime_java = target_java

    # Gradle 9 requires a Java 17+ runtime even when the project still compiles
    # Java 8 bytecode. Keep target and build-runtime Java separate in that case.
    wrapper_version = gradle_wrapper_version(repo) if build_type == "gradle" else None
    if wrapper_version and wrapper_version[0] >= 9 and runtime_java < 17:
        runtime_java = 17
        warnings.append(
            f"Gradle {wrapper_version[0]}.{wrapper_version[1]} requires a newer build runtime; "
            f"using Java 17 to build Java {target_java} target sources."
        )

    return runtime_java, warnings


def validate_java_home(version: int) -> Path:
    home = JAVA_HOMES[version]
    java = home / "bin" / "java"
    javac = home / "bin" / "javac"
    if not java.is_file() or not os.access(java, os.X_OK):
        raise PreflightError(f"Java {version} runtime is missing from DevKit image: {java}")
    if not javac.is_file() or not os.access(javac, os.X_OK):
        raise PreflightError(f"Java {version} compiler is missing from DevKit image: {javac}")

    java_result = run([str(java), "-version"], check=False)
    javac_result = run([str(javac), "-version"], check=False)
    if java_result.returncode != 0 or javac_result.returncode != 0:
        raise PreflightError(f"Java {version} toolchain exists but failed self-check: {home}")
    return home


def write_toolchain_env(repo: Path, target_java: int, runtime_java: int, java_home: Path) -> Path:
    hermes_dir = repo / ".hermes"
    hermes_dir.mkdir(parents=True, exist_ok=True)
    path = hermes_dir / "toolchain.env"
    if path.exists():
        original = path.read_text(encoding="utf-8")
        if TOOLCHAIN_MARKER not in original.splitlines()[:3]:
            raise PreflightError(
                f"existing toolchain file is not managed by dev-project-bootstrap; refusing overwrite: {path}"
            )

    content = "\n".join([
        TOOLCHAIN_MARKER,
        f"HERMES_PROJECT_JAVA_TARGET={target_java}",
        f"HERMES_PROJECT_JAVA_RUNTIME={runtime_java}",
        f"JAVA_HOME={java_home}",
        "",
    ])
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"[UPDATE] Java toolchain: target={target_java}, runtime={runtime_java}, home={java_home}")
    return path


def configure_java_toolchain(repo: Path, build_type: str) -> tuple[str, list[str]]:
    if build_type not in {"gradle", "maven"}:
        print("[SKIP] Java toolchain: no Gradle/Maven project detected")
        return "none", []

    target_java, warnings = detect_java_target(repo, build_type)
    runtime_java, runtime_warnings = select_runtime_java(repo, build_type, target_java)
    warnings.extend(runtime_warnings)
    java_home = validate_java_home(runtime_java)
    toolchain_file = write_toolchain_env(repo, target_java, runtime_java, java_home)
    return str(toolchain_file), warnings


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
    toolchain_file, warnings = configure_java_toolchain(repo, build_type)

    gitattributes = "skipped"
    if not args.no_gitattributes:
        gitattributes = ensure_gitattributes(repo)

    warnings.extend(inspect_wrapper_eol(repo, build_type))
    for warning in warnings:
        print(f"[WARN] {warning}")

    print("")
    print(f"BUILD_TYPE={build_type}")
    print(f"TOOLCHAIN_FILE={toolchain_file}")
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

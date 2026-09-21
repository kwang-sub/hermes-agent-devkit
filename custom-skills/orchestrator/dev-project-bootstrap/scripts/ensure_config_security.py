#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable


MAX_DISCOVERY_DEPTH = 3
PRUNED_DIRS = {
    ".git",
    ".hermes",
    ".worktrees",
    "node_modules",
    ".next",
    "build",
    "dist",
    "out",
    "target",
}
ENV_EXAMPLE = ".env.example"
LOCAL_ENV_NAMES = (
    ".env",
    ".env.local",
    ".env.development.local",
    ".env.production.local",
    ".env.test.local",
)
SPRING_PUBLIC_CONFIG_NAMES = (
    "application.yml",
    "application.yaml",
    "application.properties",
)
SPRING_PRIVATE_PREFIXES = (
    "application-local.",
    "application-secret.",
    "application-private.",
)
PRIVATE_KEY_SUFFIXES = (".p12", ".pfx", ".jks")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::[^}]*)?}")
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "service-role-key",
    "service_role_key",
    "client-secret",
    "client_secret",
    "private-key",
    "private_key",
    "api-key",
    "api_key",
)
RUNTIME_PUBLIC_KEY_PARTS = (
    "publishable-key",
    "publishable_key",
)


class ConfigSecurityError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ConfigSecurityError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}"
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Protect application runtime configuration, create conventional .env.example files, "
            "and report existing tracked/hardcoded configuration without rewriting it."
        )
    )
    parser.add_argument("--repo", required=True, help="Absolute path to a project root")
    parser.add_argument(
        "--allow-non-git",
        action="store_true",
        help="Allow security inspection without Git tracked-file evidence after explicit acknowledgement.",
    )
    return parser.parse_args()


def resolve_project_root(path_text: str, *, allow_non_git: bool) -> tuple[Path, str]:
    requested = Path(path_text)
    if not requested.is_absolute():
        raise ConfigSecurityError(f"--repo must be absolute: {requested}")
    if not requested.is_dir():
        raise ConfigSecurityError(f"project path does not exist or is not a directory: {requested}")

    requested = requested.resolve()
    result = run(["git", "-C", str(requested), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        if not allow_non_git:
            raise ConfigSecurityError(
                "project is not a Git repository; explicit Non-Git acknowledgement is required"
            )
        return requested, "none"

    root = Path(result.stdout.strip()).resolve()
    if root != requested:
        raise ConfigSecurityError(
            f"--repo must point at the Git repository root; requested={requested}, root={root}"
        )
    return root, "git"


def tracked_paths(repo: Path) -> set[str]:
    result = run(["git", "-C", str(repo), "ls-files", "-z"])
    return {item for item in result.stdout.split("\0") if item}


def is_protected_runtime_file(path_text: str) -> bool:
    path = Path(path_text)
    name = path.name
    lowered = name.lower()

    if lowered == ".env":
        return True
    if lowered.startswith(".env.") and lowered != ENV_EXAMPLE:
        return True
    if lowered.startswith(SPRING_PRIVATE_PREFIXES):
        return True
    if lowered == "private.pem" or lowered.endswith("-private.pem") or lowered.endswith(".private.pem"):
        return True
    if lowered.endswith(PRIVATE_KEY_SUFFIXES):
        return True
    return False


def protected_tracked_paths(repo: Path) -> list[str]:
    return sorted(path for path in tracked_paths(repo) if is_protected_runtime_file(path))


def relative_depth(root: Path, path: Path) -> int:
    return len(path.relative_to(root).parts)


def discover_manifest_roots(repo: Path) -> tuple[set[Path], set[Path]]:
    frontend_roots: set[Path] = set()
    backend_roots: set[Path] = set()

    for current_text, dirs, files in os.walk(repo):
        current = Path(current_text)
        depth = relative_depth(repo, current)
        dirs[:] = [
            name
            for name in dirs
            if name not in PRUNED_DIRS and depth < MAX_DISCOVERY_DEPTH
        ]
        if depth > MAX_DISCOVERY_DEPTH:
            continue

        if "package.json" in files and is_frontend_package(current / "package.json"):
            frontend_roots.add(current)
        if any(name in files for name in ("build.gradle", "build.gradle.kts", "pom.xml")):
            if is_spring_root(current):
                backend_roots.add(current)

    return frontend_roots, backend_roots


def is_frontend_package(package_json: Path) -> bool:
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False

    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        values = payload.get(key)
        if isinstance(values, dict):
            names.update(str(name) for name in values)
    return bool(names & {"next", "react", "react-dom", "@supabase/ssr", "@supabase/supabase-js"})


def is_spring_root(root: Path) -> bool:
    resources = root / "src" / "main" / "resources"
    if any((resources / name).is_file() for name in SPRING_PUBLIC_CONFIG_NAMES):
        return True

    manifests = [root / "build.gradle", root / "build.gradle.kts", root / "pom.xml"]
    for manifest in manifests:
        if not manifest.is_file():
            continue
        try:
            text = manifest.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "spring-boot" in text or "org.springframework.boot" in text:
            return True
    return False


def env_keys_from_file(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    keys: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return set()

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if ENV_KEY_RE.fullmatch(key):
            keys.add(key)
    return keys


def spring_placeholder_keys(root: Path) -> set[str]:
    resources = root / "src" / "main" / "resources"
    keys: set[str] = set()
    for name in SPRING_PUBLIC_CONFIG_NAMES:
        path = resources / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        keys.update(PLACEHOLDER_RE.findall(text))
    return keys


def collect_env_keys(root: Path, *, spring: bool) -> set[str]:
    keys: set[str] = set()
    for name in LOCAL_ENV_NAMES:
        keys.update(env_keys_from_file(root / name))
    if spring:
        keys.update(spring_placeholder_keys(root))
    return keys


def render_example(kind: str, keys: Iterable[str]) -> str:
    if kind == "frontend":
        header = [
            "# Runtime environment contract for local frontend development.",
            "# Copy to .env.local and fill real values locally.",
            "# NEXT_PUBLIC_* values are browser-visible, but real environment-specific values stay out of Git.",
        ]
    elif kind == "spring":
        header = [
            "# Runtime environment contract for Spring Boot.",
            "# Spring Boot does not load .env by itself; provide these through IntelliJ/OS/container environment.",
            "# Keep real credentials and environment-specific endpoints out of Git.",
        ]
    else:
        header = [
            "# Runtime environment contract.",
            "# Keep real values in local/runtime environment configuration, not in Git.",
        ]

    body = [f"{key}=" for key in sorted(set(keys))]
    return "\n".join([*header, "", *body]).rstrip() + "\n"


def ensure_example(root: Path, *, kind: str, keys: set[str]) -> str:
    path = root / ENV_EXAMPLE
    if path.exists():
        return "reused"
    path.write_text(render_example(kind, keys), encoding="utf-8")
    return "created"


def normalized_key(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def value_is_externalized(value: str) -> bool:
    stripped = value.strip().strip("'\"")
    if not stripped or stripped.lower() in {"null", "~"}:
        return True
    if re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*:?}", stripped):
        return True
    upper = stripped.upper()
    if upper.startswith(("YOUR_", "REPLACE_", "CHANGE_ME", "<")):
        return True
    if stripped.lower() in {"placeholder", "example", "changeme"}:
        return True
    return False


def yaml_scalar_entries(text: str) -> Iterable[tuple[str, str]]:
    stack: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = re.match(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.-]+):(?:\s*(?P<value>.*))?$", raw)
        if not match:
            continue
        indent = len(match.group("indent").replace("\t", "    "))
        key = match.group("key")
        value = (match.group("value") or "").strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        full = ".".join([*(item[1] for item in stack), key])
        if value:
            yield full, value
        else:
            stack.append((indent, key))


def property_scalar_entries(text: str) -> Iterable[tuple[str, str]]:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*[:=]\s*(.*)$", line)
        if match:
            yield match.group(1), match.group(2)


def key_requires_externalization(key: str) -> bool:
    normalized = normalized_key(key)
    if any(part.replace("_", "-") in normalized for part in SENSITIVE_KEY_PARTS):
        return True
    if any(part.replace("_", "-") in normalized for part in RUNTIME_PUBLIC_KEY_PARTS):
        return True
    if normalized in {
        "spring.datasource.password",
        "spring.datasource.username",
        "spring.datasource.url",
        "supabase.url",
    }:
        return True
    return False


def hardcoded_spring_config(repo: Path, *, tracked: set[str] | None = None) -> list[str]:
    tracked = tracked_paths(repo) if tracked is None else tracked
    findings: list[str] = []
    for relative in sorted(tracked):
        name = Path(relative).name
        if name not in SPRING_PUBLIC_CONFIG_NAMES:
            continue
        path = repo / relative
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        entries = (
            property_scalar_entries(text)
            if name.endswith(".properties")
            else yaml_scalar_entries(text)
        )
        for key, value in entries:
            if key_requires_externalization(key) and not value_is_externalized(value):
                findings.append(f"{relative}:{key}")
    return findings


def ensure_configuration_security(
    repo: Path,
    *,
    version_control: str = "git",
) -> dict[str, object]:
    # Existing projects are preserve-first. Security findings are reported, but
    # bootstrap does not rewrite, untrack, or block legacy configuration solely
    # because it is already committed.
    if version_control == "git":
        tracked = tracked_paths(repo)
        tracked_protected = sorted(
            path for path in tracked if is_protected_runtime_file(path)
        )
        hardcoded = hardcoded_spring_config(repo, tracked=tracked)
    else:
        tracked_protected = []
        hardcoded = []

    frontend_roots, backend_roots = discover_manifest_roots(repo)
    created: list[str] = []
    reused: list[str] = []

    for root in sorted(frontend_roots):
        status = ensure_example(root, kind="frontend", keys=collect_env_keys(root, spring=False))
        relative = str((root / ENV_EXAMPLE).relative_to(repo))
        (created if status == "created" else reused).append(relative)

    for root in sorted(backend_roots):
        status = ensure_example(root, kind="spring", keys=collect_env_keys(root, spring=True))
        relative = str((root / ENV_EXAMPLE).relative_to(repo))
        (created if status == "created" else reused).append(relative)

    if not frontend_roots and not backend_roots:
        root_keys = collect_env_keys(repo, spring=False)
        if root_keys:
            status = ensure_example(repo, kind="generic", keys=root_keys)
            relative = ENV_EXAMPLE
            (created if status == "created" else reused).append(relative)

    warnings = [
        *(f"tracked-protected:{path}" for path in tracked_protected),
        *(f"hardcoded-spring:{item}" for item in hardcoded),
    ]
    if version_control == "none":
        warnings.append("version-control:none-tracked-file-audit-unavailable")

    return {
        "frontend_roots": sorted(str(path.relative_to(repo) or Path(".")) for path in frontend_roots),
        "backend_roots": sorted(str(path.relative_to(repo) or Path(".")) for path in backend_roots),
        "created": created,
        "reused": reused,
        "tracked_protected": tracked_protected,
        "hardcoded_spring": hardcoded,
        "warnings": warnings,
        "version_control": version_control,
    }


def main() -> int:
    args = parse_args()
    repo, version_control = resolve_project_root(
        args.repo,
        allow_non_git=args.allow_non_git,
    )
    result = ensure_configuration_security(
        repo,
        version_control=version_control,
    )

    for path in result["tracked_protected"]:
        print(
            f"[WARN] Git already tracks protected local/runtime configuration: {path}; preserving existing project state.",
            file=sys.stderr,
        )
    for finding in result["hardcoded_spring"]:
        print(
            f"[WARN] Spring tracked configuration contains a hardcoded runtime/security setting: {finding}; preserving existing value.",
            file=sys.stderr,
        )

    if version_control == "none":
        print(
            "[WARN] Non-Git project: tracked secret/config audit is unavailable; "
            "runtime configuration discovery continues without Git evidence.",
            file=sys.stderr,
        )

    warning_count = len(result["warnings"])
    print(f"VERSION_CONTROL={version_control}")
    print(f"CONFIG_SECURITY={'warn' if warning_count else 'pass'}")
    print(f"CONFIG_SECURITY_WARNING_COUNT={warning_count}")
    print(f"CONFIG_FRONTEND_ROOTS={len(result['frontend_roots'])}")
    print(f"CONFIG_BACKEND_ROOTS={len(result['backend_roots'])}")
    print(f"ENV_EXAMPLES_CREATED={len(result['created'])}")
    print(f"ENV_EXAMPLES_REUSED={len(result['reused'])}")
    print(f"TRACKED_SECRET_FILES={len(result['tracked_protected'])}")
    print(f"HARDCODED_SPRING_RUNTIME_VALUES={len(result['hardcoded_spring'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigSecurityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

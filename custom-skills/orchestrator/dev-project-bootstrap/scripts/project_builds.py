#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, NamedTuple

import dev_environment_preflight as shared


GRADLE_ROOT_MARKERS = {
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
}
_STACK_DETECTOR: Any | None = None


class BuildProject(NamedTuple):
    root: Path
    build_type: str


def load_stack_detector() -> Any:
    """Load dev-tech-dispatch so bootstrap shares its bounded manifest policy."""
    global _STACK_DETECTOR
    if _STACK_DETECTOR is not None:
        return _STACK_DETECTOR

    script = (
        Path(__file__).resolve().parents[2]
        / "dev-tech-dispatch"
        / "scripts"
        / "detect_capabilities.py"
    )
    if not script.is_file():
        raise shared.PreflightError(f"stack detector is missing: {script}")
    spec = importlib.util.spec_from_file_location(
        "devkit_detect_capabilities_bootstrap_preflight",
        script,
    )
    if spec is None or spec.loader is None:
        raise shared.PreflightError(f"cannot load stack detector: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _STACK_DETECTOR = module
    return module


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def project_label(repo: Path, project_root: Path) -> str:
    relative = project_root.resolve().relative_to(repo.resolve())
    return "." if not relative.parts else relative.as_posix()


def discover_build_projects(repo: Path) -> list[BuildProject]:
    """Discover Gradle/Maven build roots without unbounded repository scanning.

    The canonical stack detector owns max depth and skipped directories. Nested
    candidates of the same build system collapse under the closest selected
    ancestor, so a Gradle/Maven multi-module build is treated as one build while
    sibling applications in a monorepo remain independent build projects.
    """
    repo = repo.resolve()
    detector = load_stack_detector()
    manifests = [Path(path).resolve() for path in detector.discover_inputs(repo)]

    candidate_types: dict[Path, set[str]] = {}
    for path in manifests:
        if path.name in GRADLE_ROOT_MARKERS:
            candidate_types.setdefault(path.parent, set()).add("gradle")
        elif path.name == "pom.xml":
            candidate_types.setdefault(path.parent, set()).add("maven")

    candidates: list[BuildProject] = []
    for root, build_types in candidate_types.items():
        if len(build_types) > 1:
            raise shared.PreflightError(
                "multiple JVM build systems were detected at the same project root "
                f"{project_label(repo, root)}: " + ", ".join(sorted(build_types))
            )
        candidates.append(BuildProject(root, next(iter(build_types))))

    candidates.sort(
        key=lambda item: (
            len(item.root.relative_to(repo).parts),
            item.root.relative_to(repo).as_posix(),
            item.build_type,
        )
    )

    selected: list[BuildProject] = []
    for candidate in candidates:
        if any(
            ancestor.build_type == candidate.build_type
            and ancestor.root != candidate.root
            and _is_under(candidate.root, ancestor.root)
            for ancestor in selected
        ):
            continue
        selected.append(candidate)
    return selected


def summarize_build_type(projects: list[BuildProject]) -> str:
    build_types = {project.build_type for project in projects}
    if not build_types:
        return "other"
    if len(build_types) == 1:
        return next(iter(build_types))
    return "mixed"


def configure_java_toolchain(
    repo: Path,
    projects: list[BuildProject],
) -> tuple[str, list[str]]:
    if not projects:
        print("[SKIP] Java toolchain: no Gradle/Maven project detected")
        return "none", []

    resolved: list[tuple[BuildProject, int, int, Path]] = []
    warnings: list[str] = []
    for project in projects:
        target_java, project_warnings = shared.detect_java_target(
            project.root,
            project.build_type,
        )
        runtime_java, runtime_warnings = shared.select_runtime_java(
            project.root,
            project.build_type,
            target_java,
        )
        project_warnings.extend(runtime_warnings)
        java_home = shared.validate_java_home(runtime_java)
        resolved.append((project, target_java, runtime_java, java_home))
        label = project_label(repo, project.root)
        warnings.extend(f"{label}: {warning}" for warning in project_warnings)

    targets = {target for _, target, _, _ in resolved}
    runtimes = {runtime for _, _, runtime, _ in resolved}
    homes = {home for _, _, _, home in resolved}
    if len(targets) > 1 or len(runtimes) > 1 or len(homes) > 1:
        detail = ", ".join(
            f"{project_label(repo, project.root)}:{project.build_type}:"
            f"target={target}:runtime={runtime}"
            for project, target, runtime, _ in resolved
        )
        raise shared.PreflightError(
            "multiple JVM build projects require different Java toolchains, but "
            "the current Hermes repository contract uses one .hermes/toolchain.env. "
            f"Align the project Java versions or split the runtime contract: {detail}"
        )

    first_project, target_java, runtime_java, java_home = resolved[0]
    toolchain_file = shared.write_toolchain_env(
        repo,
        target_java,
        runtime_java,
        java_home,
    )
    if len(resolved) == 1:
        label = project_label(repo, first_project.root)
        if label != ".":
            print(
                "[INFO] Java toolchain source project: "
                f"{label} ({first_project.build_type})"
            )
    else:
        labels = ", ".join(
            f"{project_label(repo, project.root)} ({project.build_type})"
            for project, _, _, _ in resolved
        )
        print(f"[INFO] Shared Java toolchain applies to build projects: {labels}")
    return str(toolchain_file), warnings


def inspect_wrapper_eol(repo: Path, projects: list[BuildProject]) -> list[str]:
    warnings: list[str] = []
    for project in projects:
        label = project_label(repo, project.root)
        project_warnings = shared.inspect_wrapper_eol(
            project.root,
            project.build_type,
        )
        warnings.extend(f"{label}: {warning}" for warning in project_warnings)
    return warnings

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, asdict
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_WORKSPACE_ROOT = Path("/workspace")
DEFAULT_OUTPUT_DIR = Path("/opt/data/work-items/resolutions")


class ResolveError(RuntimeError):
    pass


@dataclass
class Evidence:
    kind: str
    term: str
    weight: int
    detail: str
    strong: bool = False


@dataclass
class Candidate:
    project_id: str
    project_name: str
    repository: str
    metadata_file: str
    score: int = 0
    evidence: list[Evidence] = field(default_factory=list)
    strong_terms: list[str] = field(default_factory=list)

    def add(self, kind: str, term: str, weight: int, detail: str, strong: bool = False) -> None:
        key = (kind.casefold(), term.casefold(), detail.casefold())
        for item in self.evidence:
            if (item.kind.casefold(), item.term.casefold(), item.detail.casefold()) == key:
                return
        self.evidence.append(Evidence(kind, term, weight, detail, strong))
        self.score += weight
        if strong and term.casefold() not in {x.casefold() for x in self.strong_terms}:
            self.strong_terms.append(term)


def scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return None
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    low = value.casefold()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "~"}:
        return None
    return value


def fallback_yaml_paths(text: str) -> dict[tuple[str, ...], list[Any]]:
    result: dict[tuple[str, ...], list[Any]] = {}
    stack: list[tuple[int, str]] = []

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()

        if line.startswith("- "):
            path = tuple(key for _, key in stack)
            result.setdefault(path, []).append(scalar(line[2:]))
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        parent = tuple(k for _, k in stack)
        full = parent + (key,)

        if value:
            result.setdefault(full, []).append(scalar(value))
        else:
            stack.append((indent, key))

    return result


def load_project_metadata(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")

    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        paths = fallback_yaml_paths(text)

        def vals(*parts: str) -> list[Any]:
            return paths.get(tuple(parts), [])

        def one(*parts: str) -> Any:
            values = vals(*parts)
            return values[0] if values else None

        return {
            "project": {
                "id": one("project", "id"),
                "name": one("project", "name"),
                "repository": one("project", "repository"),
            },
            "resolver": {
                "aliases": vals("resolver", "aliases"),
                "modules": vals("resolver", "modules"),
                "files": vals("resolver", "files"),
                "paths": vals("resolver", "paths"),
            },
            "work_sources": {
                "jira": {
                    "project_keys": vals("work_sources", "jira", "project_keys"),
                    "components": vals("work_sources", "jira", "components"),
                    "labels": vals("work_sources", "jira", "labels"),
                },
                "notion": {
                    "databases": vals("work_sources", "notion", "databases"),
                },
                "slack": {
                    "channels": vals("work_sources", "slack", "channels"),
                },
                "text": {
                    "aliases": vals("work_sources", "text", "aliases"),
                },
            },
            "jira": {
                "project_keys": vals("jira", "project_keys"),
                "components": vals("jira", "components"),
            },
        }


def dig(data: Any, *keys: str, default: Any = None) -> Any:
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None]
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]
    return []


def collect_work_text(item: dict[str, Any]) -> str:
    work = item.get("work") if isinstance(item.get("work"), dict) else {}
    hints = item.get("project_hints") if isinstance(item.get("project_hints"), dict) else {}

    parts: list[str] = []

    for key in ("title", "description"):
        if work.get(key):
            parts.append(str(work[key]))

    for value in work.get("acceptance_criteria") or []:
        parts.append(str(value))

    for comment in work.get("comments") or []:
        if isinstance(comment, dict) and comment.get("body"):
            parts.append(str(comment["body"]))

    for value in work.get("labels") or []:
        parts.append(str(value))

    for value in work.get("components") or []:
        parts.append(str(value))

    custom = work.get("custom_fields")
    if isinstance(custom, dict):
        for key, value in custom.items():
            parts.append(str(key))
            parts.append(str(value))

    # Project key is intentionally not appended to the text used for strong matching.
    for key, value in hints.items():
        if key in {"jira_project_key", "project_key"}:
            continue
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif value:
            parts.append(str(value))

    return "\n".join(parts)


def source_info(item: dict[str, Any]) -> tuple[str, str]:
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    return str(source.get("type") or "unknown"), str(source.get("ref") or "")


def phrase_present(text: str, phrase: str) -> bool:
    phrase = re.sub(r"\s+", " ", phrase or "").strip()
    return bool(phrase) and phrase.casefold() in text.casefold()


def discover_metadata_files(workspace: Path, project_depth: int) -> list[Path]:
    workspace = workspace.resolve()

    if not workspace.is_dir():
        raise ResolveError(f"workspace root does not exist: {workspace}")

    if project_depth < 1:
        raise ResolveError("--project-depth must be >= 1")

    results: list[Path] = []

    # Bounded directory-level discovery only. We never recurse inside a discovered
    # project repository. At each level we only test <dir>/.hermes/project.yaml.
    current_dirs = [workspace]

    for depth in range(1, project_depth + 1):
        next_dirs: list[Path] = []

        for parent in current_dirs:
            try:
                children = sorted(
                    (p for p in parent.iterdir() if p.is_dir()),
                    key=lambda p: p.name.casefold()
                )
            except PermissionError:
                continue

            for child in children:
                if child.name in {".worktrees", ".git", "node_modules", "target", "build", "dist", ".gradle", ".idea"}:
                    continue

                metadata = child / ".hermes" / "project.yaml"
                if metadata.is_file():
                    results.append(metadata.resolve())
                    # Project found: do not descend into repository.
                    continue

                # Only descend to the configured directory depth.
                if depth < project_depth:
                    next_dirs.append(child)

        current_dirs = next_dirs

    # Deduplicate.
    unique: list[Path] = []
    seen: set[str] = set()
    for path in results:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def get_source_project_key(item: dict[str, Any]) -> str:
    hints = item.get("project_hints") if isinstance(item.get("project_hints"), dict) else {}
    return str(hints.get("jira_project_key") or hints.get("project_key") or "")


def candidate_from_metadata(
    metadata_file: Path,
    work_text: str,
    item: dict[str, Any],
    source_type: str,
    source_project_key: str,
    explicit_repository: str | None,
) -> Candidate:
    meta = load_project_metadata(metadata_file)

    inferred_repo = metadata_file.parent.parent
    repository = str(dig(meta, "project", "repository", default="") or inferred_repo)
    project_id = str(dig(meta, "project", "id", default="") or inferred_repo.name)
    project_name = str(dig(meta, "project", "name", default="") or project_id)

    candidate = Candidate(
        project_id=project_id,
        project_name=project_name,
        repository=repository,
        metadata_file=str(metadata_file),
    )

    # Explicit repository selection must still be a managed project.
    if explicit_repository:
        explicit = explicit_repository.casefold()
        repo_path = Path(repository)
        if (
            repository.casefold() == explicit
            or repo_path.name.casefold() == explicit
            or project_id.casefold() == explicit
            or project_name.casefold() == explicit
        ):
            candidate.add(
                "explicit_repository",
                explicit_repository,
                200,
                "Explicit repository matches this managed project.",
                strong=True,
            )

    aliases = str_list(dig(meta, "resolver", "aliases", default=[]))
    modules = str_list(dig(meta, "resolver", "modules", default=[]))
    files = str_list(dig(meta, "resolver", "files", default=[]))
    paths = str_list(dig(meta, "resolver", "paths", default=[]))

    for alias in aliases:
        if phrase_present(work_text, alias):
            candidate.add(
                "resolver.alias", alias, 80,
                f"Work Item mentions managed-project alias '{alias}'.",
                strong=True,
            )

    for module in modules:
        if phrase_present(work_text, module):
            candidate.add(
                "resolver.module", module, 90,
                f"Work Item mentions managed-project module '{module}'.",
                strong=True,
            )

    for name in files:
        if phrase_present(work_text, name):
            candidate.add(
                "resolver.file", name, 55,
                f"Work Item mentions managed-project file '{name}'.",
                strong=True,
            )

    for path in paths:
        if phrase_present(work_text, path):
            candidate.add(
                "resolver.path", path, 70,
                f"Work Item mentions managed-project path '{path}'.",
                strong=True,
            )

    # Stable managed project identifiers.
    for kind, value, weight in (
        ("project.id", project_id, 65),
        ("project.name", project_name, 60),
        ("repository.name", Path(repository).name, 55),
    ):
        if len(value) >= 3 and phrase_present(work_text, value):
            candidate.add(
                kind, value, weight,
                f"Work Item explicitly mentions managed-project identifier '{value}'.",
                strong=True,
            )

    work = item.get("work") if isinstance(item.get("work"), dict) else {}
    components = str_list(work.get("components"))
    labels = str_list(work.get("labels"))

    source_cfg = dig(meta, "work_sources", source_type, default={})
    if isinstance(source_cfg, dict):
        configured_components = str_list(source_cfg.get("components"))
        for component in components:
            if component.casefold() in {x.casefold() for x in configured_components}:
                candidate.add(
                    "source.component", component, 30,
                    f"Source component '{component}' matches project metadata.",
                    strong=False,
                )

        configured_labels = str_list(source_cfg.get("labels"))
        for label in labels:
            if label.casefold() in {x.casefold() for x in configured_labels}:
                candidate.add(
                    "source.label", label, 20,
                    f"Source label '{label}' matches project metadata.",
                    strong=False,
                )

        configured_keys = str_list(source_cfg.get("project_keys"))
        if (
            source_project_key
            and source_project_key.casefold() in {x.casefold() for x in configured_keys}
        ):
            candidate.add(
                "source.project_key", source_project_key, 5,
                f"Source project key '{source_project_key}' matches metadata; weak context only.",
                strong=False,
            )

    # Backward compatibility with earlier bootstrap metadata.
    if source_type == "jira":
        legacy_keys = str_list(dig(meta, "jira", "project_keys", default=[]))
        if (
            source_project_key
            and source_project_key.casefold() in {x.casefold() for x in legacy_keys}
        ):
            candidate.add(
                "legacy.jira.project_key", source_project_key, 3,
                "Legacy Jira project-key metadata matched; weak context only.",
                strong=False,
            )

        legacy_components = str_list(dig(meta, "jira", "components", default=[]))
        for component in components:
            if component.casefold() in {x.casefold() for x in legacy_components}:
                candidate.add(
                    "legacy.jira.component", component, 20,
                    f"Legacy Jira component '{component}' matches project metadata.",
                    strong=False,
                )

    return candidate


def determine_resolution(candidates: list[Candidate]) -> tuple[str, list[Candidate], str]:
    ranked = sorted(candidates, key=lambda c: (-c.score, c.repository.casefold()))

    explicit = [
        c for c in ranked
        if any(e.kind == "explicit_repository" for e in c.evidence)
    ]
    if len(explicit) == 1:
        return "RESOLVED_SINGLE", explicit, "explicit_managed_project"

    viable = [
        c for c in ranked
        if c.score >= 55 and any(e.strong for e in c.evidence)
    ]

    if not viable:
        return "BLOCKED", [], "no_managed_project_match"

    if len(viable) == 1:
        return "RESOLVED_SINGLE", viable, "single_strong_managed_project"

    # Multi-project only when each candidate has at least one strong term
    # not shared by the other viable candidates.
    counts: dict[str, int] = {}
    for c in viable:
        for term in {x.casefold() for x in c.strong_terms}:
            counts[term] = counts.get(term, 0) + 1

    all_have_distinct = True
    for c in viable:
        if not any(counts.get(term.casefold(), 0) == 1 for term in c.strong_terms):
            all_have_distinct = False
            break

    if all_have_distinct:
        return "RESOLVED_MULTI", viable, "multiple_distinct_managed_projects"

    top, second = viable[0], viable[1]
    if top.score >= second.score + 40:
        return "RESOLVED_SINGLE", [top], "top_managed_project_materially_stronger"

    return "BLOCKED", [], "ambiguous_managed_project_metadata"


def candidate_dict(candidate: Candidate) -> dict[str, Any]:
    return {
        "project_id": candidate.project_id,
        "project_name": candidate.project_name,
        "repository": candidate.repository,
        "metadata_file": candidate.metadata_file,
        "score": candidate.score,
        "strong_terms": candidate.strong_terms,
        "evidence": [asdict(e) for e in candidate.evidence],
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        f"# Project Resolution: {result['work_id']}",
        "",
        f"- Status: **{result['status']}**",
        f"- Reason: `{result['reason']}`",
        f"- Workspace: `{result['workspace_root']}`",
        f"- Managed projects scanned: `{result['managed_projects_scanned']}`",
        "",
    ]

    if result["resolved_projects"]:
        lines += ["## Resolved Projects", ""]
        for idx, project in enumerate(result["resolved_projects"], start=1):
            lines += [
                f"### {idx}. {project['project_id']}",
                f"- Repository: `{project['repository']}`",
                f"- Metadata: `{project['metadata_file']}`",
                f"- Score: `{project['score']}`",
                f"- Strong terms: {', '.join(project['strong_terms']) if project['strong_terms'] else '-'}",
                "- Evidence:",
            ]
            for e in project["evidence"]:
                marker = "strong" if e["strong"] else "supporting"
                lines.append(
                    f"  - [{marker}] {e['kind']} `{e['term']}` "
                    f"(+{e['weight']}): {e['detail']}"
                )
            lines.append("")
    else:
        lines += [
            "## Resolution",
            "",
            "No managed project was automatically selected.",
            "",
        ]

    lines += ["## Ranked Managed Projects", ""]
    for idx, project in enumerate(result["candidates"], start=1):
        lines += [
            f"### {idx}. {project['project_id']}",
            f"- Repository: `{project['repository']}`",
            f"- Metadata: `{project['metadata_file']}`",
            f"- Score: `{project['score']}`",
        ]
        if project["evidence"]:
            lines.append("- Evidence:")
            for e in project["evidence"]:
                marker = "strong" if e["strong"] else "supporting"
                lines.append(
                    f"  - [{marker}] {e['kind']} `{e['term']}` "
                    f"(+{e['weight']}): {e['detail']}"
                )
        else:
            lines.append("- Evidence: none")
        lines.append("")

    if result["status"] == "BLOCKED":
        lines += [
            "## Required Action",
            "",
            "Do not scan unmanaged repositories. Either identify an already managed project, "
            "bootstrap the intended repository, or add stable resolver metadata to its "
            "`.hermes/project.yaml`.",
            "",
        ]

    lines += [
        "> Only `.hermes/project.yaml` metadata was used. Repository source code was not scanned.",
        "",
    ]
    return "\n".join(lines)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve Work Item only against Hermes-managed .hermes/project.yaml projects."
    )
    parser.add_argument("--work-item", required=True)
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--explicit-repository")
    parser.add_argument(
        "--project-depth",
        type=int,
        default=1,
        help="Directory depth used only to locate .hermes/project.yaml. Default: 1",
    )
    args = parser.parse_args()

    work_item_path = Path(args.work_item)
    if not work_item_path.is_file():
        raise ResolveError(f"Work Item JSON does not exist: {work_item_path}")

    try:
        item = json.loads(work_item_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResolveError(f"invalid Work Item JSON: {exc}") from exc

    if not isinstance(item, dict):
        raise ResolveError("Work Item root must be an object")

    work = item.get("work") if isinstance(item.get("work"), dict) else {}
    source_type, source_ref = source_info(item)
    work_id = str(work.get("id") or source_ref or "work-item")

    workspace = Path(args.workspace_root).resolve()
    metadata_files = discover_metadata_files(workspace, args.project_depth)

    if not metadata_files:
        raise ResolveError(
            f"no managed projects found: expected .hermes/project.yaml under {workspace}"
        )

    work_text = collect_work_text(item)
    source_project_key = get_source_project_key(item)

    candidates = [
        candidate_from_metadata(
            metadata_file=path,
            work_text=work_text,
            item=item,
            source_type=source_type,
            source_project_key=source_project_key,
            explicit_repository=args.explicit_repository,
        )
        for path in metadata_files
    ]

    status, resolved, reason = determine_resolution(candidates)
    ranked = sorted(candidates, key=lambda c: (-c.score, c.repository.casefold()))

    result = {
        "version": 2,
        "work_id": work_id,
        "work_item": str(work_item_path),
        "source_type": source_type,
        "source_ref": source_ref,
        "source_project_key": source_project_key,
        "workspace_root": str(workspace),
        "project_depth": args.project_depth,
        "managed_projects_scanned": len(candidates),
        "status": status,
        "reason": reason,
        "resolved_projects": [candidate_dict(c) for c in resolved],
        "candidates": [candidate_dict(c) for c in ranked],
        "search_policy": {
            "managed_projects_only": True,
            "metadata_file": ".hermes/project.yaml",
            "repository_content_scanned": False,
            "unmanaged_repositories_scanned": False,
            "worktrees_excluded": True,
            "source_project_key_is_non_resolving": True,
        },
    }

    output_dir = Path(args.output_dir)
    json_path = output_dir / f"{work_id}.json"
    md_path = output_dir / f"{work_id}.md"

    atomic_write(json_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    atomic_write(md_path, markdown_report(result))

    print(f"WORK_ID={work_id}")
    print(f"STATUS={status}")
    print(f"REASON={reason}")
    print(f"MANAGED_PROJECTS_SCANNED={len(candidates)}")
    print(f"RESOLVED_COUNT={len(resolved)}")

    for idx, c in enumerate(resolved, start=1):
        print(f"PROJECT_{idx}={c.repository}")
        print(f"PROJECT_{idx}_ID={c.project_id}")
        print(f"PROJECT_{idx}_SCORE={c.score}")

    if status == "BLOCKED":
        for idx, c in enumerate(ranked[:5], start=1):
            print(f"CANDIDATE_{idx}={c.repository}")
            print(f"CANDIDATE_{idx}_SCORE={c.score}")

    print(f"JSON_FILE={json_path}")
    print(f"MARKDOWN_FILE={md_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ResolveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

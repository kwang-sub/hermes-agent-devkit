#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Iterable


COMMON_START = "<!-- HERMES-COMMON:START -->"
COMMON_END = "<!-- HERMES-COMMON:END -->"
PROJECT_START = "<!-- HERMES-PROJECT:START -->"
PROJECT_END = "<!-- HERMES-PROJECT:END -->"
MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
SCHEMA_VERSION = "2"

BOOTSTRAP_MANAGED_KEYS = {
    "version",
    "project",
    "kanban",
    "git",
    "profiles",
}


class BootstrapError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise BootstrapError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}"
        )
    return result


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if not value:
        raise BootstrapError("project/board slug cannot be empty after normalization")
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Ensure an existing Git repository is bootstrapped for Hermes development."
    )
    p.add_argument("--repo", required=True, help="Absolute path to an existing Git repository root")
    p.add_argument("--project-id", help="Canonical project id; default: existing metadata or repo directory")
    p.add_argument("--name", help="Human-readable project name; default: existing metadata or project id")
    p.add_argument("--board", help="Kanban board slug; default: existing metadata or project id")
    p.add_argument("--base", help="Default worktree base branch/ref")
    p.add_argument(
        "--profiles",
        help="Comma-separated profiles to register; default: resolved orchestrator,coder,reviewer role profiles",
    )
    p.add_argument("--orchestrator-profile", help="Default: existing metadata or orchestrator")
    p.add_argument("--coder-profile", help="Default: existing metadata or coder")
    p.add_argument("--reviewer-profile", help="Default: existing metadata or reviewer")
    p.add_argument("--description", help="Project/board description")
    p.add_argument("--common-context", default="/opt/data/shared/AGENTS.common.md")
    return p.parse_args()


def require_tool(name: str) -> None:
    # Do not use a login shell here. Hermes containers may expose executables
    # through a PATH that `sh -lc` replaces.
    if shutil.which(name) is None:
        raise BootstrapError(f"required tool is not available on PATH: {name}")


def resolve_repo(path_text: str) -> Path:
    requested = Path(path_text)
    if not requested.is_absolute():
        raise BootstrapError(f"--repo must be absolute: {requested}")
    if not requested.exists():
        raise BootstrapError(f"repository path does not exist: {requested}")
    if not requested.is_dir():
        raise BootstrapError(f"repository path is not a directory: {requested}")

    result = run(["git", "-C", str(requested), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise BootstrapError(f"not a Git repository: {requested}")

    root = Path(result.stdout.strip()).resolve()
    requested_resolved = requested.resolve()
    if root != requested_resolved:
        raise BootstrapError(
            f"--repo must point at the Git repository root; "
            f"requested={requested_resolved}, root={root}"
        )
    return root


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def split_top_level_sections(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Split YAML text into header lines and top-level key sections.

    This is intentionally a text-preserving splitter, not a YAML serializer.
    It allows user-managed/legacy sections to survive bootstrap byte-for-byte
    except for surrounding blank-line normalization.
    """
    lines = text.splitlines(keepends=True)
    starts: list[tuple[int, str]] = []

    for idx, line in enumerate(lines):
        if line.startswith((" ", "\t")):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):(?:\s.*)?(?:\r?\n)?$", line)
        if m:
            starts.append((idx, m.group(1)))

    if not starts:
        return lines, []

    header = lines[:starts[0][0]]
    sections: list[tuple[str, str]] = []

    for pos, (start_idx, key) in enumerate(starts):
        end_idx = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        sections.append((key, "".join(lines[start_idx:end_idx])))

    return header, sections


def section_map(text: str) -> dict[str, str]:
    _, sections = split_top_level_sections(text)
    return {key: body for key, body in sections}


def parse_quoted_or_plain(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        decoded = json.loads(value)
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return value.strip("'\"")


def section_scalar(section: str, child_key: str) -> str | None:
    pattern = rf"(?m)^\s{{2}}{re.escape(child_key)}:\s*(.+?)\s*$"
    m = re.search(pattern, section)
    if not m:
        return None
    return parse_quoted_or_plain(m.group(1))


def read_managed_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "exists": False,
            "text": "",
            "sections": {},
            "section_order": [],
        }

    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise BootstrapError(
            f"existing metadata is not managed by dev-project-bootstrap; refusing overwrite: {path}"
        )

    _, ordered_sections = split_top_level_sections(text)
    sections = {key: body for key, body in ordered_sections}

    data: dict[str, object] = {
        "exists": True,
        "text": text,
        "sections": sections,
        "section_order": [key for key, _ in ordered_sections],
    }

    project = sections.get("project", "")
    kanban = sections.get("kanban", "")
    git = sections.get("git", "")
    profiles = sections.get("profiles", "")

    data["project_id"] = section_scalar(project, "id")
    data["project_name"] = section_scalar(project, "name")
    data["repository"] = section_scalar(project, "repository")
    data["board"] = section_scalar(kanban, "board")
    data["base"] = section_scalar(git, "default_base_branch")
    data["worktree_root"] = section_scalar(git, "worktree_root")
    data["orchestrator"] = section_scalar(profiles, "orchestrator")
    data["coder"] = section_scalar(profiles, "coder")
    data["reviewer"] = section_scalar(profiles, "reviewer")

    return data


def core_metadata_text(
    *,
    project_id: str,
    name: str,
    repository: str,
    board: str,
    base: str,
    worktree_root: str,
    orchestrator: str,
    coder: str,
    reviewer: str,
) -> str:
    lines = [
        MANAGED_MARKER,
        f"version: {SCHEMA_VERSION}",
        "",
        "project:",
        f"  id: {yaml_scalar(project_id)}",
        f"  name: {yaml_scalar(name)}",
        f"  repository: {yaml_scalar(repository)}",
        "",
        "kanban:",
        f"  board: {yaml_scalar(board)}",
        "",
        "git:",
        f"  default_base_branch: {yaml_scalar(base)}",
        f"  worktree_root: {yaml_scalar(worktree_root)}",
        "",
        "profiles:",
        f"  orchestrator: {yaml_scalar(orchestrator)}",
        f"  coder: {yaml_scalar(coder)}",
        f"  reviewer: {yaml_scalar(reviewer)}",
        "",
    ]
    return "\n".join(lines)


def resolver_skeleton() -> str:
    return "\n".join([
        "resolver:",
        "  aliases: []",
        "  modules: []",
        "  files: []",
        "  paths: []",
        "",
    ])


def normalize_preserved_section(section: str) -> str:
    # Keep section contents unchanged. Ensure one trailing newline so sections
    # can be concatenated safely.
    return section.rstrip("\r\n") + "\n"


def write_metadata(
    path: Path,
    *,
    existing: dict[str, object],
    project_id: str,
    name: str,
    repository: str,
    board: str,
    base: str,
    worktree_root: str,
    orchestrator: str,
    coder: str,
    reviewer: str,
) -> tuple[bool, list[str]]:
    """Write bootstrap-managed core and preserve user/legacy top-level sections.

    Returns:
      resolver_created
      preserved_extra_keys
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_sections = existing.get("sections")
    if not isinstance(existing_sections, dict):
        existing_sections = {}

    section_order = existing.get("section_order")
    if not isinstance(section_order, list):
        section_order = []

    resolver_created = "resolver" not in existing_sections

    parts: list[str] = [
        core_metadata_text(
            project_id=project_id,
            name=name,
            repository=repository,
            board=board,
            base=base,
            worktree_root=worktree_root,
            orchestrator=orchestrator,
            coder=coder,
            reviewer=reviewer,
        ).rstrip()
    ]

    if resolver_created:
        parts.append(resolver_skeleton().rstrip())
    else:
        parts.append(normalize_preserved_section(str(existing_sections["resolver"])).rstrip())

    preserved_extra_keys: list[str] = []
    for key in section_order:
        if key in BOOTSTRAP_MANAGED_KEYS or key == "resolver":
            continue
        section = existing_sections.get(key)
        if not isinstance(section, str):
            continue
        parts.append(normalize_preserved_section(section).rstrip())
        preserved_extra_keys.append(str(key))

    output = "\n\n".join(part for part in parts if part.strip()) + "\n"
    path.write_text(output, encoding="utf-8")

    return resolver_created, preserved_extra_keys


def board_exists(board: str) -> bool:
    result = run(["hermes", "kanban", "boards", "list", "--json"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BootstrapError(
            f"cannot parse `hermes kanban boards list --json`: {exc}"
        ) from exc

    if isinstance(payload, dict):
        candidates = payload.get("boards", payload.get("items", []))
    else:
        candidates = payload

    if not isinstance(candidates, list):
        raise BootstrapError("unexpected board list JSON structure")

    for item in candidates:
        if isinstance(item, str) and item == board:
            return True
        if isinstance(item, dict) and item.get("slug") == board:
            return True
    return False


def ensure_board(board: str, name: str, description: str) -> None:
    if board_exists(board):
        print(f"[OK] Kanban board: {board}")
        return

    cmd = ["hermes", "kanban", "boards", "create", board, "--name", name]
    if description:
        cmd += ["--description", description]
    run(cmd)

    if not board_exists(board):
        raise BootstrapError(
            f"board creation returned success but board is still missing: {board}"
        )
    print(f"[CREATE] Kanban board: {board}")


def ensure_profile(profile: str) -> None:
    result = run(["hermes", "profile", "show", profile], check=False)
    if result.returncode != 0:
        raise BootstrapError(
            f"required Hermes profile does not exist or cannot be read: {profile}"
        )


def project_show(profile: str, project_id: str) -> subprocess.CompletedProcess[str]:
    return run(
        ["hermes", "-p", profile, "project", "show", project_id],
        check=False,
    )


def extract_primary(show_text: str) -> str | None:
    m = re.search(r"(?mi)^\s*primary:\s*(.+?)\s*$", show_text)
    return m.group(1).strip() if m else None


def extract_board(show_text: str) -> str | None:
    m = re.search(r"(?mi)^\s*board:\s*(.+?)\s*$", show_text)
    return m.group(1).strip() if m else None


def ensure_project(
    profile: str,
    project_id: str,
    repo: Path,
    board: str,
    description: str,
) -> None:
    ensure_profile(profile)
    shown = project_show(profile, project_id)

    if shown.returncode != 0:
        cmd = [
            "hermes", "-p", profile,
            "project", "create", project_id, str(repo),
        ]
        if description:
            cmd += ["--description", description]
        run(cmd)
        print(f"[CREATE] Project {project_id} in profile {profile}")

        shown = project_show(profile, project_id)
        if shown.returncode != 0:
            raise BootstrapError(
                f"project was created but cannot be shown: "
                f"profile={profile}, project={project_id}"
            )
    else:
        print(f"[OK] Project {project_id} in profile {profile}")

    primary = extract_primary(shown.stdout)
    if not primary:
        raise BootstrapError(
            f"cannot verify project primary folder from `project show`: "
            f"profile={profile}, project={project_id}"
        )

    primary_path = Path(os.path.expanduser(primary)).resolve()
    if primary_path != repo.resolve():
        raise BootstrapError(
            f"project id conflict in profile {profile}: "
            f"{project_id} points to {primary_path}, expected {repo}"
        )

    current_board = extract_board(shown.stdout)
    if current_board != board:
        run([
            "hermes", "-p", profile,
            "project", "bind-board", project_id, board,
        ])
        print(f"[BIND] {profile}:{project_id} -> board {board}")
    else:
        print(f"[OK] Board binding {profile}:{project_id} -> {board}")

    verify = project_show(profile, project_id)
    if verify.returncode != 0:
        raise BootstrapError(
            f"cannot verify project after binding: {profile}:{project_id}"
        )
    if extract_board(verify.stdout) != board:
        raise BootstrapError(
            f"board binding verification failed: "
            f"{profile}:{project_id} -> {board}"
        )


def select_context_file(repo: Path) -> Path:
    candidates = [
        ".hermes.md",
        "HERMES.md",
        "AGENTS.md",
        "CLAUDE.md",
        ".cursorrules",
    ]
    for name in candidates:
        path = repo / name
        if path.is_file():
            return path
    return repo / "AGENTS.md"


def extract_block(text: str, start: str, end: str) -> str:
    start_pos = text.find(start)
    end_pos = text.find(end)
    if start_pos == -1 or end_pos == -1 or end_pos < start_pos:
        raise BootstrapError(
            f"managed block markers are missing or malformed: {start} ... {end}"
        )
    end_pos += len(end)
    return text[start_pos:end_pos].strip()


def replace_or_append_block(
    original: str,
    block: str,
    start: str,
    end: str,
) -> str:
    start_pos = original.find(start)
    end_pos = original.find(end)

    if start_pos == -1 and end_pos == -1:
        if original and not original.endswith("\n"):
            original += "\n"
        prefix = original.rstrip()
        if prefix:
            return prefix + "\n\n" + block.strip() + "\n"
        return block.strip() + "\n"

    if start_pos == -1 or end_pos == -1 or end_pos < start_pos:
        raise BootstrapError(
            f"existing context contains malformed managed block: {start} ... {end}"
        )

    end_pos += len(end)
    return original[:start_pos] + block.strip() + original[end_pos:]


def project_context_block(
    *,
    project_id: str,
    name: str,
    repository: str,
    board: str,
    base: str,
    worktree_root: str,
    orchestrator: str,
    coder: str,
    reviewer: str,
) -> str:
    return "\n".join([
        PROJECT_START,
        "",
        "## Hermes Project Configuration",
        "",
        "> 이 블록은 `dev-project-bootstrap`이 관리한다. "
        "프로젝트 자동화의 canonical 값은 `.hermes/project.yaml`이다.",
        "",
        f"- Project ID: `{project_id}`",
        f"- Project Name: `{name}`",
        f"- Repository: `{repository}`",
        f"- Kanban Board: `{board}`",
        f"- Default Base Branch: `{base}`",
        f"- Worktree Root: `{worktree_root}`",
        f"- Orchestrator Profile: `{orchestrator}`",
        f"- Coder Profile: `{coder}`",
        f"- Reviewer Profile: `{reviewer}`",
        "",
        "`resolver:` 값은 사용자가 직접 관리한다. "
        "Agent는 Bootstrap 중 resolver alias/module/file/path를 추측해서 기록하지 않는다.",
        "",
        "개발 작업은 프로젝트 metadata를 먼저 확인하고, "
        "구현용 Worktree는 원본 checkout 외부에 생성한다.",
        "",
        PROJECT_END,
    ])


def apply_context(
    context_path: Path,
    common_path: Path,
    *,
    project_id: str,
    name: str,
    repository: str,
    board: str,
    base: str,
    worktree_root: str,
    orchestrator: str,
    coder: str,
    reviewer: str,
) -> None:
    common_text = common_path.read_text(encoding="utf-8")
    common_block = extract_block(common_text, COMMON_START, COMMON_END)

    original = (
        context_path.read_text(encoding="utf-8")
        if context_path.exists()
        else ""
    )

    updated = replace_or_append_block(
        original,
        common_block,
        COMMON_START,
        COMMON_END,
    )

    pblock = project_context_block(
        project_id=project_id,
        name=name,
        repository=repository,
        board=board,
        base=base,
        worktree_root=worktree_root,
        orchestrator=orchestrator,
        coder=coder,
        reviewer=reviewer,
    )
    updated = replace_or_append_block(
        updated,
        pblock,
        PROJECT_START,
        PROJECT_END,
    )

    if updated != original:
        context_path.write_text(updated, encoding="utf-8")
        print(f"[UPDATE] Context: {context_path}")
    else:
        print(f"[OK] Context: {context_path}")


def main() -> int:
    args = parse_args()

    for tool in ("git", "hermes", "python3"):
        require_tool(tool)

    repo = resolve_repo(args.repo)

    common_path = Path(args.common_context)
    if not common_path.is_file():
        raise BootstrapError(
            f"common context file does not exist: {common_path}"
        )

    metadata_path = repo / ".hermes" / "project.yaml"
    existing = read_managed_metadata(metadata_path)

    requested_project_id = (
        args.project_id
        or str(existing.get("project_id") or "")
        or repo.name
    )
    project_id = slugify(requested_project_id)

    name = (
        args.name
        or str(existing.get("project_name") or "")
        or project_id
    )

    board = slugify(
        args.board
        or str(existing.get("board") or "")
        or project_id
    )

    orchestrator = (
        args.orchestrator_profile
        or str(existing.get("orchestrator") or "")
        or "orchestrator"
    )
    coder = (
        args.coder_profile
        or str(existing.get("coder") or "")
        or "coder"
    )
    reviewer = (
        args.reviewer_profile
        or str(existing.get("reviewer") or "")
        or "reviewer"
    )

    if args.profiles:
        profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    else:
        profiles = list(dict.fromkeys([orchestrator, coder, reviewer]))

    if not profiles:
        raise BootstrapError("at least one profile is required")

    if existing.get("project_id") and existing["project_id"] != project_id:
        raise BootstrapError(
            f"managed metadata project id conflict: "
            f"existing={existing['project_id']}, requested={project_id}"
        )

    if existing.get("repository"):
        existing_repo = Path(str(existing["repository"])).resolve()
        if existing_repo != repo.resolve():
            raise BootstrapError(
                f"managed metadata repository conflict: "
                f"existing={existing_repo}, requested={repo}"
            )

    if args.board and existing.get("board") and existing["board"] != board:
        raise BootstrapError(
            f"managed metadata board conflict: "
            f"existing={existing['board']}, requested={board}"
        )

    if args.base:
        base = args.base
    elif existing.get("base"):
        base = str(existing["base"])
    else:
        branch = run([
            "git", "-C", str(repo),
            "branch", "--show-current",
        ]).stdout.strip()
        if not branch:
            raise BootstrapError(
                "repository is detached; specify --base"
            )
        base = branch

    base_check = run([
        "git", "-C", str(repo),
        "rev-parse", "--verify", f"{base}^{{commit}}",
    ], check=False)
    if base_check.returncode != 0:
        raise BootstrapError(
            f"base branch/ref does not resolve to a commit: {base}"
        )

    worktree_root = str(
        existing.get("worktree_root")
        or (Path("/workspace/.worktrees") / repo.name)
    )

    description = args.description or f"{name} application development"

    print("== dev-project-bootstrap v0.2.0 ==")
    print(f"Repository : {repo}")
    print(f"Project    : {project_id}")
    print(f"Board      : {board}")
    print(f"Base       : {base}")
    print(f"Profiles   : {','.join(profiles)}")
    print("Resolver   : user-managed")

    # Board first so bind-board never writes a dangling board binding.
    ensure_board(board, name, description)

    for profile in profiles:
        ensure_project(profile, project_id, repo, board, description)

    resolver_created, preserved_extra_keys = write_metadata(
        metadata_path,
        existing=existing,
        project_id=project_id,
        name=name,
        repository=str(repo),
        board=board,
        base=base,
        worktree_root=worktree_root,
        orchestrator=orchestrator,
        coder=coder,
        reviewer=reviewer,
    )

    if resolver_created:
        print(f"[CREATE] Resolver skeleton: {metadata_path}")
    else:
        print(f"[PRESERVE] Resolver metadata (user-managed): {metadata_path}")

    if preserved_extra_keys:
        print(
            "[PRESERVE] Additional metadata sections: "
            + ",".join(preserved_extra_keys)
        )

    print(f"[UPDATE] Metadata core: {metadata_path}")

    context_path = select_context_file(repo)
    apply_context(
        context_path,
        common_path,
        project_id=project_id,
        name=name,
        repository=str(repo),
        board=board,
        base=base,
        worktree_root=worktree_root,
        orchestrator=orchestrator,
        coder=coder,
        reviewer=reviewer,
    )

    # Final checks.
    if not board_exists(board):
        raise BootstrapError(
            f"final board verification failed: {board}"
        )

    for profile in profiles:
        shown = project_show(profile, project_id)
        if shown.returncode != 0:
            raise BootstrapError(
                f"final project verification failed: "
                f"{profile}:{project_id}"
            )

        primary = extract_primary(shown.stdout)
        if (
            not primary
            or Path(os.path.expanduser(primary)).resolve() != repo.resolve()
        ):
            raise BootstrapError(
                f"final project path verification failed: "
                f"{profile}:{project_id}"
            )

        if extract_board(shown.stdout) != board:
            raise BootstrapError(
                f"final board binding verification failed: "
                f"{profile}:{project_id}"
            )

    text = context_path.read_text(encoding="utf-8")
    for marker in (
        COMMON_START, COMMON_END,
        PROJECT_START, PROJECT_END,
    ):
        if marker not in text:
            raise BootstrapError(
                f"final context verification failed; marker missing: {marker}"
            )

    final_metadata = read_managed_metadata(metadata_path)
    final_sections = final_metadata.get("sections")
    if not isinstance(final_sections, dict) or "resolver" not in final_sections:
        raise BootstrapError(
            "final metadata verification failed: resolver section missing"
        )

    print("")
    print(f"PROJECT_ID={project_id}")
    print(f"REPOSITORY={repo}")
    print(f"BOARD={board}")
    print(f"BASE_BRANCH={base}")
    print(f"WORKTREE_ROOT={worktree_root}")
    print(f"CONTEXT_FILE={context_path}")
    print(f"METADATA_FILE={metadata_path}")
    print(f"PROFILES={','.join(profiles)}")
    print("RESOLVER_MODE=user-managed")
    print("STATUS=ready")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys

MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
HERMES_CLI = "/opt/hermes/.venv/bin/hermes"


class FastFlowError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectMetadata:
    project_id: str
    repository: str
    board: str
    coder: str
    reviewer: str


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise FastFlowError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")
    return result


def ensure_safe_directory(path: Path) -> None:
    resolved = str(path.resolve())
    current = run(["git", "config", "--global", "--get-all", "safe.directory"], check=False)
    configured = {line.strip() for line in current.stdout.splitlines() if line.strip()}
    if resolved not in configured:
        added = run(["git", "config", "--global", "--add", "safe.directory", resolved], check=False)
        if added.returncode != 0:
            detail = (added.stderr or added.stdout).strip()
            raise FastFlowError(f"cannot register Git safe.directory for {resolved}: {detail}")


def resolve_git_root(path: Path) -> Path:
    ensure_safe_directory(path)
    result = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise FastFlowError(f"workspace is not a Git repository: {path}: {detail}")
    return Path(result.stdout.strip()).resolve()


def parse_managed_metadata(path: Path) -> ProjectMetadata:
    if not path.is_file():
        raise FastFlowError(f"project metadata is missing: {path}; use Standard Flow to bootstrap the project first")
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise FastFlowError(f"project metadata is not managed by dev-project-bootstrap: {path}")

    def field(pattern: str, name: str) -> str:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if not match:
            raise FastFlowError(f"required metadata field is missing: {name}")
        return match.group(1).strip().strip("'\"")

    return ProjectMetadata(
        project_id=field(r"^\s{2}id:\s*(.+?)\s*$", "project.id"),
        repository=field(r"^\s{2}repository:\s*(.+?)\s*$", "project.repository"),
        board=field(r"^kanban:\s*\n\s{2}board:\s*(.+?)\s*$", "kanban.board"),
        coder=field(r"^profiles:\s*\n(?:.*\n)*?\s{2}coder:\s*(.+?)\s*$", "profiles.coder"),
        reviewer=field(r"^profiles:\s*\n(?:.*\n)*?\s{2}reviewer:\s*(.+?)\s*$", "profiles.reviewer"),
    )


def current_branch(repo: Path) -> str:
    branch = run(["git", "-C", str(repo), "branch", "--show-current"]).stdout.strip()
    if not branch:
        raise FastFlowError("workspace is in detached HEAD; use Standard Flow")
    return branch


def current_head(repo: Path) -> str:
    sha = run(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise FastFlowError(f"HEAD did not resolve to a full commit SHA: {sha}")
    return sha


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def workspace_status(repo: Path) -> tuple[list[str], list[str]]:
    """Return effective pre-existing changes and tracked EOL-only noise.

    Raw `git status` is unreliable for Windows bind mounts when the host checkout
    uses CRLF and Linux Git sees the LF-normalized index. Unstaged tracked files
    only count as real changes when their diff survives --ignore-cr-at-eol.
    Staged and untracked paths always count as real changes.
    """
    normal_unstaged = set(_lines(run([
        "git", "-C", str(repo), "diff", "--name-only",
    ]).stdout))
    effective_unstaged = set(_lines(run([
        "git", "-C", str(repo), "diff", "--name-only", "--ignore-cr-at-eol",
    ]).stdout))
    staged = set(_lines(run([
        "git", "-C", str(repo), "diff", "--cached", "--name-only",
    ]).stdout))
    untracked = set(_lines(run([
        "git", "-C", str(repo), "ls-files", "--others", "--exclude-standard",
    ]).stdout))

    changes = [f"M {path}" for path in sorted(effective_unstaged - staged)]
    changes.extend(f"STAGED {path}" for path in sorted(staged))
    changes.extend(f"?? {path}" for path in sorted(untracked))
    eol_only = sorted(normal_unstaged - effective_unstaged - staged)
    return changes, eol_only


def _normalize_task_spec_value(value: str) -> str:
    return " ".join(value.split())


def request_fingerprint(*, title: str, goal: str, acceptance: list[str], implementation: list[str], tests: list[str], risks: list[str]) -> str:
    """Return a stable fingerprint for the requested Fast Flow work.

    Exact retries keep the same fingerprint, while follow-up work on the same
    Base SHA gets a different fingerprint when its requested spec changes.
    """
    parts = [
        f"title={_normalize_task_spec_value(title)}",
        f"goal={_normalize_task_spec_value(goal)}",
        *(f"acceptance={_normalize_task_spec_value(value)}" for value in acceptance),
        *(f"implementation={_normalize_task_spec_value(value)}" for value in implementation),
        *(f"test={_normalize_task_spec_value(value)}" for value in tests),
        *(f"risk={_normalize_task_spec_value(value)}" for value in risks),
    ]
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()[:8].upper()


def logical_task_key(title: str, base_sha: str, fingerprint: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").upper() or "TASK"
    return f"FAST-{base_sha[:8].upper()}-{slug[:32].rstrip('-')}-{fingerprint}"


def bullet_lines(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def build_body(*, task_key: str, goal: str, acceptance: list[str], implementation: list[str], tests: list[str], risks: list[str], reviewer: str, workspace: Path, branch: str, base_sha: str, pre_existing: list[str], eol_only_count: int) -> str:
    dirty = bool(pre_existing)
    baseline = bullet_lines(pre_existing) if pre_existing else "- none"
    return f"""Flow: FAST
Task Key: {task_key}
Review Policy: RISK_BASED

Goal:
{goal}

Acceptance Criteria:
{bullet_lines(acceptance)}

Implementation Tasks:
{bullet_lines(implementation)}

Test Plan:
{bullet_lines(tests)}

Dependencies:
- none known at dispatch

Known Risks:
{bullet_lines(risks)}

Fast Flow Escalation:
- If source evidence reveals ambiguous product intent, architecture decisions, public API/schema changes, cross-repository work, dependency changes, or materially broader scope, do not expand implementation.
- Call kanban_block with reason FAST_FLOW_ESCALATION_REQUIRED and include evidence required to restart through Standard Flow.

Review Policy Contract:
- After implementation and targeted verification, coder evaluates Review Risk using dev-implement-plan.
- LOW -> coder records risk reasons and verification, then kanban_complete.
- REVIEW_REQUIRED -> coder calls kanban_request_review for {reviewer}.
- Any CHANGES_REQUESTED retry must return to reviewer after the fix.

Reviewer Profile:
{reviewer}

Implementation Skill: dev-implement-plan
Review Skill: dev-code-review

Workspace Contract:
- Workspace: {workspace}
- Branch mode: current
- Expected branch: {branch}
- Base branch: {branch}
- Base SHA: {base_sha}
- Workspace dirty at dispatch: {str(dirty).lower()}
- Ignored tracked EOL-only changes at dispatch: {eol_only_count}
- Pre-existing effective changes at dispatch:
{baseline}
- Raw `git status` may contain Windows bind-mount EOL noise; do not use raw modified-file counts as the dirty baseline.
- Coder must preserve pre-existing user changes and must not reset, restore, clean, or stash them.
- Coder must not switch branches or create another worktree.
- Coder must not commit, push, create a PR, or merge during implementation.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Fast Flow Kanban task for the configured coder/reviewer profiles.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--acceptance", action="append", required=True)
    parser.add_argument("--implementation", action="append", required=True)
    parser.add_argument("--test", action="append", required=True)
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested = Path(args.workspace).resolve()
    repo = resolve_git_root(requested)
    if repo != requested:
        raise FastFlowError(f"Fast Flow workspace must be the Git repository root: requested={requested}, root={repo}")

    meta = parse_managed_metadata(repo / ".hermes" / "project.yaml")
    configured_repo = Path(meta.repository).resolve()
    if configured_repo != repo:
        raise FastFlowError(f"project metadata repository mismatch: metadata={configured_repo}, actual={repo}")

    pre_existing, eol_only = workspace_status(repo)
    branch = current_branch(repo)
    base_sha = current_head(repo)
    risks = args.risk or ["Fast Flow remains valid only while the task is local, unambiguous, and small."]
    fingerprint = request_fingerprint(
        title=args.title,
        goal=args.goal,
        acceptance=args.acceptance,
        implementation=args.implementation,
        tests=args.test,
        risks=risks,
    )
    task_key = logical_task_key(args.title, base_sha, fingerprint)
    body = build_body(task_key=task_key, goal=args.goal, acceptance=args.acceptance, implementation=args.implementation, tests=args.test, risks=risks, reviewer=meta.reviewer, workspace=repo, branch=branch, base_sha=base_sha, pre_existing=pre_existing, eol_only_count=len(eol_only))

    print("=== Fast Flow Dispatch ===")
    print(f"PROJECT={meta.project_id}")
    print(f"BOARD={meta.board}")
    print(f"TASK_KEY={task_key}")
    print(f"REQUEST_FINGERPRINT={fingerprint}")
    print(f"WORKSPACE={repo}")
    print(f"BRANCH={branch}")
    print(f"BASE_SHA={base_sha}")
    print(f"WORKSPACE_DIRTY={str(bool(pre_existing)).lower()}")
    print(f"EFFECTIVE_CHANGE_COUNT={len(pre_existing)}")
    print(f"EOL_ONLY_CHANGE_COUNT={len(eol_only)}")
    print(f"CODER={meta.coder}")
    print(f"REVIEWER={meta.reviewer}")

    if args.dry_run:
        print("\n--- KANBAN BODY ---")
        print(body.rstrip())
        print("\nSTATUS=dry-run")
        return 0

    command = [HERMES_CLI, "kanban", "--board", meta.board, "create", args.title, "--body", body, "--assignee", meta.coder, "--workspace", f"dir:{repo}", "--created-by", "coder-fast-flow", "--idempotency-key", f"fast:{meta.project_id}:{task_key}", "--skill", "dev-implement-plan", "--json"]
    result = run(command)
    print(result.stdout.rstrip())
    print("STATUS=created")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FastFlowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

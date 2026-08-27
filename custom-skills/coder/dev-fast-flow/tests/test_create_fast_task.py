#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_fast_task.py"


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def write_metadata(repo: Path) -> None:
    (repo / ".hermes").mkdir(parents=True)
    (repo / ".hermes" / "project.yaml").write_text(
        f"""# managed-by: dev-project-bootstrap
version: 2
project:
  id: demo
  name: Demo
  repository: {repo}
kanban:
  board: demo

git:
  default_base_branch: dev
  worktree_root: {repo.parent / '.worktrees' / 'demo'}

profiles:
  orchestrator: orchestrator
  coder: coder
  reviewer: reviewer
""",
        encoding="utf-8",
    )


def make_repo(root: Path) -> Path:
    repo = root / "demo"
    repo.mkdir()
    run(["git", "init", "-b", "dev"], repo)
    run(["git", "config", "user.email", "test@example.invalid"], repo)
    run(["git", "config", "user.name", "Fast Flow Test"], repo)
    run(["git", "config", "core.autocrlf", "false"], repo)
    write_metadata(repo)
    (repo / "app.txt").write_text("baseline\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    commit = run(["git", "commit", "-m", "baseline"], repo)
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr or commit.stdout)
    return repo


def invoke(
    repo: Path,
    title: str = "small fix",
    goal: str = "Small fix.",
) -> subprocess.CompletedProcess[str]:
    return run([
        "python3", str(SCRIPT), "--workspace", str(repo), "--title", title,
        "--goal", goal, "--acceptance", "Requested behavior works.",
        "--implementation", "Apply minimum fix.", "--test", "Run focused test.", "--dry-run",
    ])


def task_key(stdout: str) -> str:
    match = re.search(r"^TASK_KEY=(.+)$", stdout, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"TASK_KEY missing:\n{stdout}")
    return match.group(1).strip()


def fingerprint(stdout: str) -> str:
    match = re.search(r"^REQUEST_FINGERPRINT=([0-9A-F]{8})$", stdout, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"REQUEST_FINGERPRINT missing:\n{stdout}")
    return match.group(1)


def test_clean_repo_dry_run() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        result = invoke(repo, "fix null handling")
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        required = (
            "PROJECT=demo", "BOARD=demo", "BRANCH=dev", "WORKSPACE_DIRTY=false",
            "EFFECTIVE_CHANGE_COUNT=0", "EOL_ONLY_CHANGE_COUNT=0", "REQUEST_FINGERPRINT=",
            "CODER=coder", "REVIEWER=reviewer", "Flow: FAST", "Review Policy: RISK_BASED",
            "Workspace dirty at dispatch: false", "Pre-existing effective changes at dispatch:", "- none",
            "LOW -> coder", "REVIEW_REQUIRED -> coder", "FAST_FLOW_ESCALATION_REQUIRED", "STATUS=dry-run",
        )
        for term in required:
            if term not in result.stdout:
                raise AssertionError(f"missing dry-run contract term: {term}\n{result.stdout}")


def test_dirty_repo_is_accepted_and_recorded() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-dirty-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        (repo / "app.txt").write_text("dirty\n", encoding="utf-8")
        result = invoke(repo)
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        required = (
            "WORKSPACE_DIRTY=true",
            "EFFECTIVE_CHANGE_COUNT=1",
            "Workspace dirty at dispatch: true",
            "Pre-existing effective changes at dispatch:",
            "M app.txt",
            "must preserve pre-existing user changes",
        )
        for term in required:
            if term not in result.stdout:
                raise AssertionError(f"missing dirty-workspace contract term: {term}\n{result.stdout}")


def test_crlf_only_tracked_change_is_not_dirty() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-eol-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        (repo / "app.txt").write_bytes(b"baseline\r\n")

        normal = run(["git", "diff", "--name-only"], repo)
        ignored = run(["git", "diff", "--name-only", "--ignore-cr-at-eol"], repo)
        if "app.txt" not in normal.stdout or ignored.stdout.strip():
            raise AssertionError("test fixture did not create an EOL-only tracked change")

        result = invoke(repo, "ignore eol noise")
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        required = (
            "WORKSPACE_DIRTY=false",
            "EFFECTIVE_CHANGE_COUNT=0",
            "EOL_ONLY_CHANGE_COUNT=1",
            "Workspace dirty at dispatch: false",
            "Ignored tracked EOL-only changes at dispatch: 1",
            "Pre-existing effective changes at dispatch:\n- none",
        )
        for term in required:
            if term not in result.stdout:
                raise AssertionError(f"missing EOL-noise contract term: {term}\n{result.stdout}")


def test_same_request_is_stable_and_follow_up_is_distinct() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-key-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        first = invoke(repo, "NodeSpecificConfigService 문서 및 주석 보강", "Analyze and comment helpers.")
        retry = invoke(repo, "NodeSpecificConfigService 문서 및 주석 보강", "Analyze and comment helpers.")
        follow_up = invoke(repo, "NodeSpecificConfigService 문서 및 주석 보강", "Add a separate single-node behavior analysis.")
        for result in (first, retry, follow_up):
            if result.returncode != 0:
                raise AssertionError(result.stderr or result.stdout)

        first_key = task_key(first.stdout)
        retry_key = task_key(retry.stdout)
        follow_up_key = task_key(follow_up.stdout)
        if first_key != retry_key:
            raise AssertionError(f"exact retry changed task key: {first_key} != {retry_key}")
        if first_key == follow_up_key:
            raise AssertionError("follow-up request reused the same task key")
        if not first_key.endswith(fingerprint(first.stdout)):
            raise AssertionError(f"task key does not contain request fingerprint: {first_key}")


def main() -> int:
    test_clean_repo_dry_run()
    test_dirty_repo_is_accepted_and_recorded()
    test_crlf_only_tracked_change_is_not_dirty()
    test_same_request_is_stable_and_follow_up_is_distinct()
    print("[PASS] dev-fast-flow task creation tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

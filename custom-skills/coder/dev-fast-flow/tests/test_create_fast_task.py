#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
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
    write_metadata(repo)
    (repo / "app.txt").write_text("baseline\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    commit = run(["git", "commit", "-m", "baseline"], repo)
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr or commit.stdout)
    return repo


def test_clean_repo_dry_run() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        result = run([
            "python3", str(SCRIPT), "--workspace", str(repo),
            "--title", "fix null handling",
            "--goal", "Prevent the known null-input failure.",
            "--acceptance", "Null input no longer triggers the reported exception.",
            "--implementation", "Inspect the existing null-handling pattern and apply the minimum fix.",
            "--test", "Run the relevant focused test.",
            "--dry-run",
        ])
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        required = (
            "PROJECT=demo", "BOARD=demo", "BRANCH=dev", "CODER=coder", "REVIEWER=reviewer",
            "Flow: FAST", "Review Policy: RISK_BASED", "LOW -> coder", "REVIEW_REQUIRED -> coder",
            "FAST_FLOW_ESCALATION_REQUIRED", "STATUS=dry-run",
        )
        for term in required:
            if term not in result.stdout:
                raise AssertionError(f"missing dry-run contract term: {term}\n{result.stdout}")


def test_dirty_repo_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-dirty-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        (repo / "app.txt").write_text("dirty\n", encoding="utf-8")
        result = run([
            "python3", str(SCRIPT), "--workspace", str(repo), "--title", "small fix",
            "--goal", "Small fix.", "--acceptance", "Requested behavior works.",
            "--implementation", "Apply minimum fix.", "--test", "Run focused test.", "--dry-run",
        ])
        if result.returncode == 0:
            raise AssertionError("dirty workspace was accepted")
        if "Fast Flow requires a clean workspace" not in result.stderr:
            raise AssertionError(result.stderr or result.stdout)


def main() -> int:
    test_clean_repo_dry_run()
    test_dirty_repo_rejected()
    print("[PASS] dev-fast-flow task creation tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

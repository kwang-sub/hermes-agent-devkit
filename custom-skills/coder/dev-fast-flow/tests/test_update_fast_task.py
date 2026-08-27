#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_fast_task.py"


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def make_repo(root: Path) -> Path:
    repo = root / "demo"
    repo.mkdir()
    run(["git", "init", "-b", "dev"], repo)
    run(["git", "config", "user.email", "test@example.invalid"], repo)
    run(["git", "config", "user.name", "Fast Follow-up Test"], repo)
    (repo / ".hermes").mkdir()
    (repo / ".hermes" / "project.yaml").write_text(
        f"""# managed-by: dev-project-bootstrap
version: 2
project:
  id: demo
  name: Demo
  repository: {repo}
kanban:
  board: demo
profiles:
  orchestrator: orchestrator
  coder: coder
  reviewer: reviewer
""",
        encoding="utf-8",
    )
    (repo / "app.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)
    return repo


def make_fake_hermes(root: Path, repo: Path, status: str) -> tuple[Path, Path]:
    log = root / "calls.log"
    cli = root / "hermes"
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "log = os.environ['FAKE_HERMES_LOG']\n"
        "with open(log, 'a', encoding='utf-8') as f: f.write(json.dumps(args, ensure_ascii=False) + '\\n')\n"
        "if 'show' in args:\n"
        "    print(json.dumps({'id': 't_active', 'status': os.environ['FAKE_TASK_STATUS'], 'workspace_path': os.environ['FAKE_TASK_WORKSPACE']}))\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)
    return cli, log


def invoke(repo: Path, cli: Path, log: Path, status: str, instruction: str = "UI only로 변경") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "HERMES_CLI": str(cli),
        "FAKE_HERMES_LOG": str(log),
        "FAKE_TASK_STATUS": status,
        "FAKE_TASK_WORKSPACE": str(repo),
    })
    return run([
        "python3", str(SCRIPT), "--workspace", str(repo), "--task", "t_active",
        "--instruction", instruction,
    ], env=env)


def calls(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_running_task_adds_direction_comment_only() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-followup-running-") as temp_dir:
        root = Path(temp_dir)
        repo = make_repo(root)
        cli, log = make_fake_hermes(root, repo, "running")
        result = invoke(repo, cli, log, "running")
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        history = calls(log)
        if len(history) != 2 or "show" not in history[0] or "comment" not in history[1]:
            raise AssertionError(history)
        if any("reopen-review" in call for call in history):
            raise AssertionError(history)
        if "USER_DIRECTION_CHANGE" not in " ".join(history[1]):
            raise AssertionError(history[1])
        if "STATUS=updated" not in result.stdout:
            raise AssertionError(result.stdout)


def test_review_task_reopens_before_comment() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-followup-review-") as temp_dir:
        root = Path(temp_dir)
        repo = make_repo(root)
        cli, log = make_fake_hermes(root, repo, "review")
        result = invoke(repo, cli, log, "review")
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        history = calls(log)
        if len(history) != 3:
            raise AssertionError(history)
        if "show" not in history[0] or "reopen-review" not in history[1] or "comment" not in history[2]:
            raise AssertionError(history)
        if "REVIEW_REOPENED=true" not in result.stdout:
            raise AssertionError(result.stdout)


def test_terminal_task_is_rejected_without_comment() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-followup-done-") as temp_dir:
        root = Path(temp_dir)
        repo = make_repo(root)
        cli, log = make_fake_hermes(root, repo, "done")
        result = invoke(repo, cli, log, "done")
        if result.returncode == 0:
            raise AssertionError(result.stdout)
        history = calls(log)
        if len(history) != 1 or "show" not in history[0]:
            raise AssertionError(history)
        if "terminal (done)" not in result.stderr:
            raise AssertionError(result.stderr)


def main() -> int:
    test_running_task_adds_direction_comment_only()
    test_review_task_reopens_before_comment()
    test_terminal_task_is_rejected_without_comment()
    print("[PASS] dev-fast-flow active task follow-up tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

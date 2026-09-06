#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_fast_task.py"

MODEL_ENV = {
    "HERMES_FLOW_MODEL_DEFAULT_PROVIDER": "openai-codex",
    "HERMES_FLOW_MODEL_DEFAULT": "gpt-5.6-terra",
    "HERMES_FLOW_MODEL_PREMIUM_PROVIDER": "openai-codex",
    "HERMES_FLOW_MODEL_PREMIUM": "gpt-6-astra",
}


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)


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


def invoke(repo: Path, title: str = "small fix", goal: str = "Small fix.", verification_mode: str = "TARGETED_TEST", model_tier: str = "DEFAULT", model_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(MODEL_ENV if model_env is None else model_env)
    return run([
        "python3", str(SCRIPT), "--workspace", str(repo), "--title", title,
        "--goal", goal, "--acceptance", "Requested behavior works.",
        "--implementation", "Apply minimum fix.", "--test", "Run focused test.",
        "--verification-mode", verification_mode, "--model-tier", model_tier, "--dry-run",
    ], env=env)


def extract(stdout: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}=(.+)$", stdout, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"{key} missing:\n{stdout}")
    return match.group(1).strip()


def test_clean_repo_dry_run() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        result = invoke(repo, "fix null handling")
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        required = (
            "PROJECT=demo", "BOARD=demo", "BRANCH=dev", "WORKSPACE_DIRTY=false",
            "EFFECTIVE_CHANGE_COUNT=0", "EOL_ONLY_CHANGE_COUNT=0", "REQUEST_FINGERPRINT=",
            "VERIFICATION_MODE=TARGETED_TEST", "Verification Mode: TARGETED_TEST",
            "CODER=coder", "REVIEWER=reviewer", "Flow: FAST", "Review Policy: RISK_BASED",
            "MODEL_TIER=DEFAULT", "MODEL=gpt-5.6-terra", "PROVIDER=openai-codex",
            "Coder Model Tier: DEFAULT", "Coder Model: gpt-5.6-terra", "Reviewer Model: DEFAULT",
            "Model Escalation: REQUIRE_REAPPROVAL", "Workspace dirty at dispatch: false",
            "Pre-existing effective changes at dispatch:", "- none", "LOW -> coder",
            "REVIEW_REQUIRED -> coder", "FAST_FLOW_ESCALATION_REQUIRED", "STATUS=dry-run",
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
        for term in ("WORKSPACE_DIRTY=true", "EFFECTIVE_CHANGE_COUNT=1", "M app.txt", "must preserve pre-existing user changes"):
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
        for term in ("WORKSPACE_DIRTY=false", "EFFECTIVE_CHANGE_COUNT=0", "EOL_ONLY_CHANGE_COUNT=1"):
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
        if extract(first.stdout, "TASK_KEY") != extract(retry.stdout, "TASK_KEY"):
            raise AssertionError("exact retry changed task key")
        if extract(first.stdout, "TASK_KEY") == extract(follow_up.stdout, "TASK_KEY"):
            raise AssertionError("follow-up request reused the same task key")


def test_verification_mode_changes_contract_and_fingerprint() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-verification-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        compile_result = invoke(repo, verification_mode="COMPILE")
        test_result = invoke(repo, verification_mode="TARGETED_TEST")
        if compile_result.returncode != 0 or test_result.returncode != 0:
            raise AssertionError(compile_result.stderr or test_result.stderr)
        if "Verification Mode: COMPILE" not in compile_result.stdout:
            raise AssertionError(compile_result.stdout)
        if extract(compile_result.stdout, "TASK_KEY") == extract(test_result.stdout, "TASK_KEY"):
            raise AssertionError("verification mode must participate in request identity")


def test_model_tier_changes_contract_and_fingerprint() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-model-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        default_result = invoke(repo, model_tier="DEFAULT")
        premium_result = invoke(repo, model_tier="PREMIUM")
        if default_result.returncode != 0 or premium_result.returncode != 0:
            raise AssertionError(default_result.stderr or premium_result.stderr)
        for term in ("MODEL_TIER=PREMIUM", "MODEL=gpt-6-astra", "Coder Model Tier: PREMIUM"):
            if term not in premium_result.stdout:
                raise AssertionError(premium_result.stdout)
        if extract(default_result.stdout, "TASK_KEY") == extract(premium_result.stdout, "TASK_KEY"):
            raise AssertionError("model tier must participate in request identity")


def test_missing_model_env_fails_before_dispatch() -> None:
    with tempfile.TemporaryDirectory(prefix="fast-flow-model-env-test-") as temp_dir:
        repo = make_repo(Path(temp_dir))
        env = dict(MODEL_ENV)
        env["HERMES_FLOW_MODEL_PREMIUM"] = ""
        result = invoke(repo, model_tier="PREMIUM", model_env=env)
        if result.returncode == 0:
            raise AssertionError("missing model env must fail")
        if "HERMES_FLOW_MODEL_PREMIUM" not in result.stderr:
            raise AssertionError(result.stderr)


def main() -> int:
    test_clean_repo_dry_run()
    test_dirty_repo_is_accepted_and_recorded()
    test_crlf_only_tracked_change_is_not_dirty()
    test_same_request_is_stable_and_follow_up_is_distinct()
    test_verification_mode_changes_contract_and_fingerprint()
    test_model_tier_changes_contract_and_fingerprint()
    test_missing_model_env_fails_before_dispatch()
    print("[PASS] dev-fast-flow task creation tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

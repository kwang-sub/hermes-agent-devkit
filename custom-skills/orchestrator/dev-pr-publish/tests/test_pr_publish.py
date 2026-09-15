#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
SCRIPTS = SKILL_ROOT / "scripts"
PREPARE = SCRIPTS / "prepare_publish.py"
PUBLISH = SCRIPTS / "publish_commit.py"
PREPARE_PR = SCRIPTS / "prepare_pr.py"
CREATE_PR = SCRIPTS / "create_pr.py"
LIB = SCRIPTS / "pr_publish_lib.py"
DOCKERFILE = REPO_ROOT / "Dockerfile"


def run(args, *, cwd: Path, env=None, check=True):
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {args}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def parse_kv(output: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for line in output.splitlines():
        if "=" not in line or line in {"DIFF_STAT_BEGIN", "DIFF_STAT_END"}:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key, []).append(value)
    return values


class PrPublishTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="dev-pr-publish-"))
        self.remote = self.temp / "remote.git"
        self.work = self.temp / "work"
        self.fake_bin = self.temp / "bin"
        self.fake_bin.mkdir()
        self.gh_state = self.temp / "gh-state.json"

        run(["git", "init", "--bare", str(self.remote)], cwd=self.temp)
        run(["git", "init", "-b", "main", str(self.work)], cwd=self.temp)
        run(["git", "config", "user.name", "DevKit Test"], cwd=self.work)
        run(["git", "config", "user.email", "devkit@example.invalid"], cwd=self.work)
        (self.work / "README.md").write_text("base\n", encoding="utf-8")
        run(["git", "add", "README.md"], cwd=self.work)
        run(["git", "commit", "-m", "chore: 기본 커밋"], cwd=self.work)
        run(["git", "remote", "add", "origin", str(self.remote)], cwd=self.work)
        run(["git", "push", "-u", "origin", "main"], cwd=self.work)
        run(["git", "remote", "set-head", "origin", "main"], cwd=self.work)
        run(["git", "switch", "-c", "feature/pr-skill-test"], cwd=self.work)

        gh = self.fake_bin / "gh"
        gh.write_text(
            """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state_path = Path(os.environ['GH_FAKE_STATE'])
args = sys.argv[1:]
if args[:2] == ['auth', 'status']:
    print('logged in')
    raise SystemExit(0)
if args[:2] == ['pr', 'list']:
    if state_path.exists():
        print(state_path.read_text(encoding='utf-8'))
    else:
        print('[]')
    raise SystemExit(0)
if args[:2] == ['pr', 'create']:
    title = args[args.index('--title') + 1]
    base = args[args.index('--base') + 1]
    head = args[args.index('--head') + 1]
    item = {'number': 1, 'url': 'https://github.example.invalid/org/repo/pull/1', 'title': title, 'baseRefName': base, 'headRefName': head}
    state_path.write_text(json.dumps([item]), encoding='utf-8')
    print(item['url'])
    raise SystemExit(0)
print('unexpected gh args: ' + repr(args), file=sys.stderr)
raise SystemExit(9)
""",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        self.env = os.environ.copy()
        self.env["PATH"] = str(self.fake_bin) + os.pathsep + self.env.get("PATH", "")
        self.env["GH_FAKE_STATE"] = str(self.gh_state)
        self.env.pop("GH_CONFIG_DIR", None)
        self.env.pop("HERMES_GH_CONFIG_DIR", None)

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def modify(self):
        (self.work / "README.md").write_text("base\nfeature\n", encoding="utf-8")
        (self.work / "new.txt").write_text("new\n", encoding="utf-8")

    def prepare(self):
        result = run(
            [sys.executable, str(PREPARE), "--workspace", str(self.work), "--base-branch", "main"],
            cwd=self.work,
            env=self.env,
        )
        values = parse_kv(result.stdout)
        self.assertEqual(values["STATUS"], ["ready"])
        self.assertEqual(values["BRANCH"], ["feature/pr-skill-test"])
        self.assertEqual(values["BASE_BRANCH"], ["main"])
        self.assertEqual(values["CHANGED_COUNT"], ["2"])
        return values

    def test_fingerprint_change_requires_reapproval(self):
        self.modify()
        values = self.prepare()
        (self.work / "README.md").write_text("base\nchanged-after-approval\n", encoding="utf-8")
        result = run(
            [
                sys.executable,
                str(PUBLISH),
                "--workspace",
                str(self.work),
                "--branch",
                "feature/pr-skill-test",
                "--fingerprint",
                values["PUBLISH_FINGERPRINT"][0],
                "--message",
                "feat: PR 게시 테스트",
            ],
            cwd=self.work,
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("fingerprint changed after approval", result.stderr)
        self.assertEqual(run(["git", "rev-list", "--count", "main..HEAD"], cwd=self.work).stdout.strip(), "0")

    def test_commit_push_then_preview_and_create_pr(self):
        self.modify()
        values = self.prepare()
        published = run(
            [
                sys.executable,
                str(PUBLISH),
                "--workspace",
                str(self.work),
                "--branch",
                "feature/pr-skill-test",
                "--fingerprint",
                values["PUBLISH_FINGERPRINT"][0],
                "--message",
                "feat: PR 게시 테스트",
            ],
            cwd=self.work,
            env=self.env,
        )
        published_values = parse_kv(published.stdout)
        self.assertEqual(published_values["STATUS"], ["pushed"])
        local = run(["git", "rev-parse", "HEAD"], cwd=self.work).stdout.strip()
        remote = run(
            ["git", "ls-remote", "--heads", "origin", "refs/heads/feature/pr-skill-test"],
            cwd=self.work,
        ).stdout.split()[0]
        self.assertEqual(local, remote)

        preview = run(
            [
                sys.executable,
                str(PREPARE_PR),
                "--workspace",
                str(self.work),
                "--base",
                "main",
                "--head",
                "feature/pr-skill-test",
            ],
            cwd=self.work,
            env=self.env,
        )
        self.assertEqual(parse_kv(preview.stdout)["STATUS"], ["ready"])

        created = run(
            [
                sys.executable,
                str(CREATE_PR),
                "--workspace",
                str(self.work),
                "--base",
                "main",
                "--head",
                "feature/pr-skill-test",
                "--title",
                "feat: PR 게시 테스트",
                "--body",
                "## 변경 내용\n- 테스트",
            ],
            cwd=self.work,
            env=self.env,
        )
        created_values = parse_kv(created.stdout)
        self.assertEqual(created_values["STATUS"], ["created"])
        self.assertEqual(
            created_values["PR_URL"],
            ["https://github.example.invalid/org/repo/pull/1"],
        )

        duplicate = run(
            [
                sys.executable,
                str(PREPARE_PR),
                "--workspace",
                str(self.work),
                "--base",
                "main",
                "--head",
                "feature/pr-skill-test",
            ],
            cwd=self.work,
            env=self.env,
        )
        duplicate_values = parse_kv(duplicate.stdout)
        self.assertEqual(duplicate_values["STATUS"], ["existing-pr"])
        self.assertEqual(duplicate_values["PR_NUMBER"], ["1"])

    def test_conventional_commit_message_is_required(self):
        self.modify()
        values = self.prepare()
        result = run(
            [
                sys.executable,
                str(PUBLISH),
                "--workspace",
                str(self.work),
                "--branch",
                "feature/pr-skill-test",
                "--fingerprint",
                values["PUBLISH_FINGERPRINT"][0],
                "--message",
                "plain message",
            ],
            cwd=self.work,
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Conventional Commits", result.stderr)

    def test_github_cli_runtime_and_auth_contract(self):
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        library = LIB.read_text(encoding="utf-8")
        publisher = PUBLISH.read_text(encoding="utf-8")
        self.assertIn("        gh \\", dockerfile)
        self.assertIn("&& gh --version \\", dockerfile)
        self.assertIn('"/opt/data/gh"', library)
        self.assertIn("HERMES_GH_CONFIG_DIR", library)
        self.assertIn("credential.helper=!gh auth git-credential", publisher)

    def test_forbidden_publish_mutations_are_not_in_scripts(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (PUBLISH, CREATE_PR, PREPARE, PREPARE_PR)
        )
        for term in ("--force-with-lease", "push --force", "git reset", "git restore", "git stash", "gh pr merge"):
            self.assertNotIn(term, combined)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Actual gitignore matching and static safety assertions for dev-git-init."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "templates" / ".gitignore"
SKILL = SKILL_ROOT / "SKILL.md"
REPO_ROOT = Path(__file__).resolve().parents[4]


class GitInitSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")

    def test_skill_identity_and_scoped_lite_flow(self):
        for term in ("name: dev-git-init", "dev-lite-session", "초기화만 승인", "GitHub 인증",
                     "상위 디렉터리", "Git 루트"):
            with self.subTest(term=term):
                self.assertIn(term, self.skill)

    def test_branch_first_commit_and_scope(self):
        for term in ("git init -b dev", "chore(init): initialize workspace", "git add --",
                     "git add -A", "일괄 추가는 하지 않는다", "git diff --cached",
                     "global config", "다른 Worktree"):
            with self.subTest(term=term):
                self.assertIn(term, self.skill)

    def test_ignored_file_extensions_are_not_mandatory(self):
        rules = [line.strip() for line in self.template.splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        for forbidden in ("*.jar", "*.xlsx", "*.zip", "build/", "target/", "dist/",
                          "gradle/", "package-lock.json", "pnpm-lock.yaml"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, rules)

    def test_branch_policy_excludes_main(self):
        self.assertIn('새 로컬 브랜치: dev', self.skill)
        self.assertIn('git -C "$WORKSPACE" init -b dev', self.skill)
        self.assertNotIn('git init -b main', self.skill)
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("기본 브랜치는 `dev`", readme)

    def test_language_and_ide_sections(self):
        for term in ("Java / Kotlin", "Node.js", "Python", "IntelliJ IDEA",
                     "PyCharm", "VS Code", "Eclipse"):
            self.assertIn(term, self.template)

    @unittest.skipUnless(shutil.which("git"), "Git not installed")
    def test_real_git_ignore_matches(self):
        with tempfile.TemporaryDirectory(prefix="dev-git-init-") as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text(self.template, encoding="utf-8")
            subprocess.run(["git", "init", "-q", "-b", "dev"], cwd=root, check=True,
                           capture_output=True)

            head = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=root,
                                  check=True, capture_output=True, text=True)
            self.assertEqual(head.stdout.strip(), "dev")

            def ignored(path):
                result = subprocess.run(["git", "check-ignore", "-q", "--no-index", path],
                                        cwd=root, capture_output=True)
                return result.returncode == 0

            examples = {
                ".idea/workspace.xml": True,
                ".vscode/settings.json": True,
                ".settings/org.eclipse.jdt.core.prefs": True,
                ".gradle/caches/data": True,
                "src/Test.class": True,
                "node_modules/pkg/index.js": True,
                ".pnpm-store/cache/a": True,
                ".next/cache/part": True,
                "__pycache__/module.pyc": True,
                ".venv/pyvenv.cfg": True,
                ".pytest_cache/readme": True,
                ".env": True,
                ".env.local": True,
                "keystore.p12": True,
                "application-local.yml": True,
                "~$report.xlsx": True,
                "build/app.jar": False,
                "target/app.jar": False,
                "dist/report.xlsx": False,
                "reports/report.xlsx": False,
                "archives/results.zip": False,
                "gradle/wrapper/gradle-wrapper.jar": False,
                "package-lock.json": False,
                "pnpm-lock.yaml": False,
                ".env.example": False,
                ".env.sample": False,
                "README.md": False,
            }
            for path, expected in examples.items():
                with self.subTest(path=path):
                    self.assertEqual(ignored(path), expected)
            remote = subprocess.run(["git", "remote"], cwd=root, check=True,
                                    capture_output=True, text=True)
            self.assertEqual(remote.stdout.strip(), "")

    def test_unchanged_root_single_powershell_entrypoint(self):
        self.assertFalse(list(SKILL_ROOT.rglob("*.ps1")))
        self.assertEqual(sorted(p.name for p in REPO_ROOT.glob("*.ps1")), ["update-devkit.ps1"])


if __name__ == "__main__":
    unittest.main()

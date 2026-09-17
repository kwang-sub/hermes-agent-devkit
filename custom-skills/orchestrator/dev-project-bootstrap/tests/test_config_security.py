from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ensure_config_security.py"
SPEC = importlib.util.spec_from_file_location("ensure_config_security", SCRIPT)
assert SPEC and SPEC.loader
security = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(security)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


class ConfigSecurityTest(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "dev")
        git(repo, "config", "user.name", "DevKit Test")
        git(repo, "config", "user.email", "devkit@example.invalid")
        return repo

    def commit_all(self, repo: Path, message: str = "chore: fixture") -> None:
        git(repo, "add", ".")
        git(repo, "commit", "-m", message)

    def test_frontend_example_uses_conventional_name_and_never_copies_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            frontend = repo / "frontend"
            frontend.mkdir()
            (frontend / "package.json").write_text(
                '{"dependencies":{"next":"16.0.0","@supabase/ssr":"1.0.0"}}',
                encoding="utf-8",
            )
            (frontend / ".env.local").write_text(
                "NEXT_PUBLIC_SUPABASE_URL=https://real-project.supabase.co\n"
                "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_real\n"
                "SUPABASE_SECRET_KEY=sb_secret_real\n",
                encoding="utf-8",
            )

            result = security.ensure_configuration_security(repo)
            example = (frontend / ".env.example").read_text(encoding="utf-8")

            self.assertIn("frontend/.env.example", result["created"])
            self.assertIn("NEXT_PUBLIC_SUPABASE_URL=", example)
            self.assertIn("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=", example)
            self.assertIn("SUPABASE_SECRET_KEY=", example)
            self.assertNotIn("real-project", example)
            self.assertNotIn("sb_publishable_real", example)
            self.assertNotIn("sb_secret_real", example)

    def test_spring_example_is_derived_from_application_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            backend = repo / "backend"
            resources = backend / "src" / "main" / "resources"
            resources.mkdir(parents=True)
            (backend / "build.gradle.kts").write_text(
                'plugins { id("org.springframework.boot") version "3.5.0" }\n',
                encoding="utf-8",
            )
            (resources / "application.yml").write_text(
                "spring:\n"
                "  datasource:\n"
                "    url: ${DB_URL}\n"
                "    username: ${DB_USERNAME}\n"
                "    password: ${DB_PASSWORD}\n"
                "supabase:\n"
                "  url: ${SUPABASE_URL}\n"
                "  secret-key: ${SUPABASE_SECRET_KEY}\n",
                encoding="utf-8",
            )

            result = security.ensure_configuration_security(repo)
            example = (backend / ".env.example").read_text(encoding="utf-8")

            self.assertIn("backend/.env.example", result["created"])
            for key in (
                "DB_URL=",
                "DB_USERNAME=",
                "DB_PASSWORD=",
                "SUPABASE_URL=",
                "SUPABASE_SECRET_KEY=",
            ):
                self.assertIn(key, example)
            self.assertIn("Spring Boot does not load .env by itself", example)

    def test_existing_example_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            frontend = repo / "frontend"
            frontend.mkdir()
            (frontend / "package.json").write_text(
                '{"dependencies":{"next":"16.0.0"}}', encoding="utf-8"
            )
            example = frontend / ".env.example"
            example.write_text("CUSTOM_CONTRACT=\n", encoding="utf-8")

            result = security.ensure_configuration_security(repo)

            self.assertIn("frontend/.env.example", result["reused"])
            self.assertEqual("CUSTOM_CONTRACT=\n", example.read_text(encoding="utf-8"))

    def test_tracked_local_env_is_blocked_without_untracking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / ".env.local").write_text("DB_PASSWORD=real-secret\n", encoding="utf-8")
            self.commit_all(repo)

            with self.assertRaises(security.ConfigSecurityError) as ctx:
                security.ensure_configuration_security(repo)

            self.assertIn(".env.local", str(ctx.exception))
            self.assertIn(".env.local", security.tracked_paths(repo))

    def test_tracked_spring_local_and_private_key_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            resources = repo / "backend" / "src" / "main" / "resources"
            keys = resources / "keys"
            keys.mkdir(parents=True)
            (resources / "application-local.yml").write_text("password: real\n", encoding="utf-8")
            (keys / "jwt-private.pem").write_text("PRIVATE FIXTURE\n", encoding="utf-8")
            self.commit_all(repo)

            with self.assertRaises(security.ConfigSecurityError) as ctx:
                security.ensure_configuration_security(repo)

            message = str(ctx.exception)
            self.assertIn("application-local.yml", message)
            self.assertIn("jwt-private.pem", message)

    def test_public_key_is_not_treated_as_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            keys = repo / "backend" / "src" / "main" / "resources" / "keys"
            keys.mkdir(parents=True)
            (keys / "jwt-public.pem").write_text("PUBLIC FIXTURE\n", encoding="utf-8")
            self.commit_all(repo)

            self.assertEqual([], security.protected_tracked_paths(repo))

    def test_hardcoded_spring_password_is_blocked_but_placeholder_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            resources = repo / "backend" / "src" / "main" / "resources"
            resources.mkdir(parents=True)
            app = resources / "application.yml"
            app.write_text(
                "spring:\n  datasource:\n    username: ${DB_USERNAME}\n    password: actual-secret\n",
                encoding="utf-8",
            )
            self.commit_all(repo)

            findings = security.hardcoded_spring_config(repo)
            self.assertEqual(
                ["backend/src/main/resources/application.yml:spring.datasource.password"],
                findings,
            )

            app.write_text(
                "spring:\n  datasource:\n    username: ${DB_USERNAME}\n    password: ${DB_PASSWORD}\n",
                encoding="utf-8",
            )
            git(repo, "add", str(app.relative_to(repo)))
            git(repo, "commit", "-m", "fix: externalize password")
            self.assertEqual([], security.hardcoded_spring_config(repo))


if __name__ == "__main__":
    unittest.main()

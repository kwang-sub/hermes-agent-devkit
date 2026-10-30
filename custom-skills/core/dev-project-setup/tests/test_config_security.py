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

    def spring_backend(self, repo: Path) -> tuple[Path, Path]:
        backend = repo / "backend"
        resources = backend / "src" / "main" / "resources"
        resources.mkdir(parents=True)
        (backend / "build.gradle.kts").write_text(
            'plugins { id("org.springframework.boot") version "3.5.0" }\n',
            encoding="utf-8",
        )
        return backend, resources

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

    def test_spring_yaml_example_is_derived_from_application_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            backend, resources = self.spring_backend(repo)
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

    def test_spring_properties_example_is_derived_from_application_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            backend, resources = self.spring_backend(repo)
            (resources / "application.properties").write_text(
                "spring.datasource.url=${DB_URL}\n"
                "spring.datasource.username=${DB_USERNAME}\n"
                "spring.datasource.password=${DB_PASSWORD}\n"
                "supabase.url=${SUPABASE_URL}\n"
                "supabase.secret-key=${SUPABASE_SECRET_KEY}\n",
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
            self.assertEqual([], result["hardcoded_spring"])

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

    def test_tracked_local_env_warns_and_does_not_untrack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / ".env.local").write_text("DB_PASSWORD=real-secret\n", encoding="utf-8")
            self.commit_all(repo)

            result = security.ensure_configuration_security(repo)

            self.assertIn(".env.local", result["tracked_protected"])
            self.assertIn("tracked-protected:.env.local", result["warnings"])
            self.assertIn(".env.local", security.tracked_paths(repo))

    def test_tracked_spring_local_and_private_key_warn_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            resources = repo / "backend" / "src" / "main" / "resources"
            keys = resources / "keys"
            keys.mkdir(parents=True)
            local = resources / "application-local.yml"
            private = keys / "jwt-private.pem"
            local.write_text("password: real\n", encoding="utf-8")
            private.write_text("PRIVATE FIXTURE\n", encoding="utf-8")
            self.commit_all(repo)

            result = security.ensure_configuration_security(repo)

            self.assertIn(
                "backend/src/main/resources/application-local.yml",
                result["tracked_protected"],
            )
            self.assertIn(
                "backend/src/main/resources/keys/jwt-private.pem",
                result["tracked_protected"],
            )
            self.assertEqual("password: real\n", local.read_text(encoding="utf-8"))
            self.assertEqual("PRIVATE FIXTURE\n", private.read_text(encoding="utf-8"))

    def test_public_key_is_not_treated_as_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            keys = repo / "backend" / "src" / "main" / "resources" / "keys"
            keys.mkdir(parents=True)
            (keys / "jwt-public.pem").write_text("PUBLIC FIXTURE\n", encoding="utf-8")
            self.commit_all(repo)

            self.assertEqual([], security.protected_tracked_paths(repo))

    def test_hardcoded_spring_yaml_warns_but_placeholder_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            _, resources = self.spring_backend(repo)
            app = resources / "application.yml"
            app.write_text(
                "spring:\n  datasource:\n    username: ${DB_USERNAME}\n    password: actual-secret\n",
                encoding="utf-8",
            )
            self.commit_all(repo)

            result = security.ensure_configuration_security(repo)
            expected = "backend/src/main/resources/application.yml:spring.datasource.password"
            self.assertEqual([expected], result["hardcoded_spring"])
            self.assertIn(f"hardcoded-spring:{expected}", result["warnings"])
            self.assertIn("actual-secret", app.read_text(encoding="utf-8"))

            app.write_text(
                "spring:\n  datasource:\n    username: ${DB_USERNAME}\n    password: ${DB_PASSWORD}\n",
                encoding="utf-8",
            )
            git(repo, "add", str(app.relative_to(repo)))
            git(repo, "commit", "-m", "fix: externalize password")
            self.assertEqual([], security.hardcoded_spring_config(repo))

    def test_hardcoded_spring_properties_warns_and_preserves_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            _, resources = self.spring_backend(repo)
            app = resources / "application.properties"
            app.write_text(
                "spring.datasource.url=jdbc:postgresql://localhost:5432/app\n"
                "spring.datasource.username=app_user\n"
                "spring.datasource.password=actual-secret\n"
                "supabase.url=https://example.supabase.co\n",
                encoding="utf-8",
            )
            self.commit_all(repo)

            result = security.ensure_configuration_security(repo)

            self.assertEqual(
                [
                    "backend/src/main/resources/application.properties:spring.datasource.url",
                    "backend/src/main/resources/application.properties:spring.datasource.username",
                    "backend/src/main/resources/application.properties:spring.datasource.password",
                    "backend/src/main/resources/application.properties:supabase.url",
                ],
                result["hardcoded_spring"],
            )
            self.assertTrue(result["warnings"])
            self.assertIn("actual-secret", app.read_text(encoding="utf-8"))
            self.assertIn("jdbc:postgresql://localhost:5432/app", app.read_text(encoding="utf-8"))


    def test_non_git_project_keeps_env_contract_without_tracked_file_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "legacy"
            frontend = project / "frontend"
            frontend.mkdir(parents=True)
            (frontend / "package.json").write_text(
                '{"dependencies":{"next":"16.0.0"}}',
                encoding="utf-8",
            )
            (frontend / ".env.local").write_text(
                "NEXT_PUBLIC_API_URL=https://example.invalid\n",
                encoding="utf-8",
            )

            result = security.ensure_configuration_security(
                project,
                version_control="none",
            )
            example = frontend / ".env.example"

            self.assertTrue(example.is_file())
            self.assertIn("NEXT_PUBLIC_API_URL=", example.read_text(encoding="utf-8"))
            self.assertEqual([], result["tracked_protected"])
            self.assertEqual([], result["hardcoded_spring"])
            self.assertIn(
                "version-control:none-tracked-file-audit-unavailable",
                result["warnings"],
            )


    def test_non_git_composite_does_not_mutate_nested_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "aggregate"
            child = project / "new" / "frontend"
            child.mkdir(parents=True)
            subprocess.run(
                ["git", "init", "-q", str(child)],
                text=True,
                capture_output=True,
                check=True,
            )
            (child / "package.json").write_text(
                '{"dependencies":{"next":"16.0.0"}}',
                encoding="utf-8",
            )
            (child / ".env.local").write_text(
                "NEXT_PUBLIC_API_URL=https://example.invalid\n",
                encoding="utf-8",
            )

            result = security.ensure_configuration_security(
                project,
                version_control="none",
            )

            self.assertFalse((child / ".env.example").exists())
            self.assertEqual([], result["frontend_roots"])
            self.assertEqual([], result["backend_roots"])


if __name__ == "__main__":
    unittest.main()

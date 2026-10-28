from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import project_builds  # noqa: E402


class BuildProjectDiscoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        project_builds._STACK_DETECTOR = None

    def test_single_root_gradle_project_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")

            projects = project_builds.discover_build_projects(repo)

            self.assertEqual(
                [project_builds.BuildProject(repo.resolve(), "gradle")],
                projects,
            )

    def test_nested_backend_is_detected_without_frontend_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            backend = repo / "chagok-backend"
            frontend = repo / "chagok-frontend"
            backend.mkdir()
            frontend.mkdir()
            (backend / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
            (frontend / "package.json").write_text('{"dependencies": {}}\n', encoding="utf-8")

            projects = project_builds.discover_build_projects(repo)

            self.assertEqual(
                [project_builds.BuildProject(backend.resolve(), "gradle")],
                projects,
            )

    def test_gradle_multimodule_candidates_collapse_to_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            module = repo / "domain"
            module.mkdir()
            (repo / "settings.gradle.kts").write_text(
                'include(":domain")\n', encoding="utf-8"
            )
            (repo / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
            (module / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")

            projects = project_builds.discover_build_projects(repo)

            self.assertEqual(
                [project_builds.BuildProject(repo.resolve(), "gradle")],
                projects,
            )

    def test_sibling_gradle_and_maven_projects_remain_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            gradle = repo / "service-a"
            maven = repo / "service-b"
            gradle.mkdir()
            maven.mkdir()
            (gradle / "build.gradle").write_text("plugins {}\n", encoding="utf-8")
            (maven / "pom.xml").write_text("<project/>\n", encoding="utf-8")

            projects = project_builds.discover_build_projects(repo)

            self.assertEqual(2, len(projects))
            self.assertEqual("mixed", project_builds.summarize_build_type(projects))
            self.assertEqual(
                {gradle.resolve(), maven.resolve()},
                {project.root for project in projects},
            )


class MultiProjectJavaToolchainTest(unittest.TestCase):
    def _write_gradle_java(self, root: Path, version: int) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "build.gradle.kts").write_text(
            "java { toolchain { languageVersion.set(JavaLanguageVersion.of("
            f"{version})) }} }}\n",
            encoding="utf-8",
        )

    def test_nested_backend_drives_repository_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            backend = repo / "chagok-backend"
            self._write_gradle_java(backend, 17)
            projects = [project_builds.BuildProject(backend.resolve(), "gradle")]

            with patch.object(
                project_builds.shared,
                "validate_java_home",
                return_value=Path("/opt/jdks/temurin-17"),
            ):
                toolchain, warnings = project_builds.configure_java_toolchain(
                    repo,
                    projects,
                )

            self.assertEqual(str(repo / ".hermes" / "toolchain.env"), toolchain)
            self.assertEqual([], warnings)
            text = (repo / ".hermes" / "toolchain.env").read_text(encoding="utf-8")
            self.assertIn("HERMES_PROJECT_JAVA_TARGET=17", text)
            self.assertIn("JAVA_HOME=/opt/jdks/temurin-17", text)

    def test_same_java_version_across_sibling_projects_shares_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            service_a = repo / "service-a"
            service_b = repo / "service-b"
            self._write_gradle_java(service_a, 17)
            self._write_gradle_java(service_b, 17)
            projects = [
                project_builds.BuildProject(service_a.resolve(), "gradle"),
                project_builds.BuildProject(service_b.resolve(), "gradle"),
            ]

            with patch.object(
                project_builds.shared,
                "validate_java_home",
                return_value=Path("/opt/jdks/temurin-17"),
            ):
                toolchain, warnings = project_builds.configure_java_toolchain(
                    repo,
                    projects,
                )

            self.assertEqual(str(repo / ".hermes" / "toolchain.env"), toolchain)
            self.assertEqual([], warnings)

    def test_different_java_versions_across_projects_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            service_a = repo / "service-a"
            service_b = repo / "service-b"
            self._write_gradle_java(service_a, 17)
            self._write_gradle_java(service_b, 21)
            projects = [
                project_builds.BuildProject(service_a.resolve(), "gradle"),
                project_builds.BuildProject(service_b.resolve(), "gradle"),
            ]

            def java_home(version: int) -> Path:
                return Path(f"/opt/jdks/temurin-{version}")

            with patch.object(
                project_builds.shared,
                "validate_java_home",
                side_effect=java_home,
            ):
                with self.assertRaisesRegex(
                    project_builds.shared.PreflightError,
                    "different Java toolchains",
                ):
                    project_builds.configure_java_toolchain(repo, projects)


if __name__ == "__main__":
    unittest.main()

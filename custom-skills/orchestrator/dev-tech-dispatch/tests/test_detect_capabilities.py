#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_capabilities.py"
SPEC = importlib.util.spec_from_file_location("detect_capabilities", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_spring_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "build.gradle", 'plugins { id "org.springframework.boot" version "3.5.0" }')
        result = MODULE.detect(repo)
        assert result["stacks"] == ["java", "spring"]
        assert result["backend_skills"] == ["dev-java-guidelines", "dev-spring-guidelines"]
        assert result["frontend_entry"] == ""
        assert result["frontend_hints"] == []
        assert result["detector_version"] == "4"
        assert result["inputs"] == ["build.gradle"]
        assert result["database_vendors"] == []
        assert result["data_entry_candidate"] == ""
        assert str(result["fingerprint"]).startswith("sha256:")


def test_kotlin_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "build.gradle.kts", 'plugins { kotlin("jvm") version "2.4.20" }')
        result = MODULE.detect(repo)
        assert result["stacks"] == ["kotlin"]
        assert result["backend_skills"] == ["dev-kotlin-guidelines"]


def test_kotlin_spring() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "build.gradle.kts", '''
plugins {
    kotlin("jvm") version "2.4.20"
    kotlin("plugin.spring") version "2.4.20"
    id("org.springframework.boot") version "4.0.0"
}
''')
        result = MODULE.detect(repo)
        assert result["stacks"] == ["kotlin", "spring"]
        assert result["backend_skills"] == ["dev-kotlin-guidelines", "dev-spring-guidelines"]


def test_kotlin_spring_jpa() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "build.gradle.kts", '''
plugins {
    kotlin("jvm") version "2.4.20"
    id("org.jetbrains.kotlin.plugin.spring") version "2.4.20"
    id("org.jetbrains.kotlin.plugin.jpa") version "2.4.20"
    id("org.springframework.boot") version "4.0.0"
}
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
}
''')
        result = MODULE.detect(repo)
        assert result["stacks"] == ["kotlin", "spring"]
        assert result["backend_skills"] == ["dev-kotlin-guidelines", "dev-spring-guidelines"]
        assert result["data_entry_candidate"] == "dev-data-feature"


def test_java_kotlin_mixed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "build.gradle.kts", '''
plugins {
    java
    kotlin("jvm") version "2.4.20"
    id("org.springframework.boot") version "4.0.0"
}
''')
        result = MODULE.detect(repo)
        assert result["stacks"] == ["java", "kotlin", "spring"]
        assert result["backend_skills"] == [
            "dev-java-guidelines", "dev-kotlin-guidelines", "dev-spring-guidelines"
        ]


def test_maven_kotlin() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "pom.xml", '''
<project>
  <dependencies><dependency><artifactId>spring-boot-starter-web</artifactId></dependency></dependencies>
  <build><plugins><plugin><artifactId>kotlin-maven-plugin</artifactId></plugin></plugins></build>
</project>
''')
        result = MODULE.detect(repo)
        assert result["stacks"] == ["kotlin", "spring"]
        assert result["backend_skills"] == ["dev-kotlin-guidelines", "dev-spring-guidelines"]


def test_next_typescript_with_tests() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "tsconfig.json", "{}")
        write(repo / "package.json", json.dumps({
            "dependencies": {"next": "15.0.0", "react": "19.0.0", "react-dom": "19.0.0"},
            "devDependencies": {"typescript": "5.9.0", "vitest": "3.0.0"},
        }))
        result = MODULE.detect(repo)
        assert result["stacks"] == ["typescript", "react", "nextjs"]
        assert result["frontend_entry"] == "dev-frontend-feature"
        assert result["frontend_hints"] == [
            "dev-typescript-guidelines", "dev-frontend-guidelines", "dev-nextjs-feature", "dev-frontend-test"
        ]
        assert result["ui_candidate"] == "dev-ui-ux"
        assert result["backend_skills"] == []


def test_fullstack_contract_candidate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "pom.xml", "<artifactId>spring-boot-starter-web</artifactId>")
        write(repo / "tsconfig.json", "{}")
        write(repo / "package.json", json.dumps({
            "dependencies": {"next": "15.0.0", "react": "19.0.0"},
            "devDependencies": {"typescript": "5.9.0"},
        }))
        result = MODULE.detect(repo)
        assert result["frontend_entry"] == "dev-frontend-feature"
        assert result["cross_stack_candidate"] == "dev-api-contract"
        assert result["backend_skills"] == ["dev-java-guidelines", "dev-spring-guidelines"]


def test_kotlin_frontend_monorepo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "backend" / "build.gradle.kts", '''
plugins {
    kotlin("jvm") version "2.4.20"
    id("org.springframework.boot") version "4.0.0"
}
''')
        write(repo / "frontend" / "package.json", json.dumps({
            "dependencies": {"next": "16.0.0", "react": "19.0.0"},
            "devDependencies": {"typescript": "5.9.0"},
        }))
        write(repo / "frontend" / "tsconfig.json", "{}")
        result = MODULE.detect(repo)
        assert result["stacks"] == ["kotlin", "spring", "typescript", "react", "nextjs"]
        assert result["backend_skills"] == ["dev-kotlin-guidelines", "dev-spring-guidelines"]
        assert result["cross_stack_candidate"] == "dev-api-contract"


def test_mssql_driver_detects_data_entry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "build.gradle", '''
plugins { id "org.springframework.boot" version "3.5.0" }
dependencies {
    implementation "org.springframework.boot:spring-boot-starter-data-jpa"
    runtimeOnly "com.microsoft.sqlserver:mssql-jdbc:12.8.1.jre11"
}
''')
        result = MODULE.detect(repo)
        assert result["database_vendors"] == ["mssql"]
        assert result["data_entry_candidate"] == "dev-data-feature"
        assert "mssql" not in result["stacks"]


def test_node_postgresql_driver_detects_data_entry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "package.json", json.dumps({
            "dependencies": {"pg": "8.13.0", "kysely": "0.28.0"}
        }))
        result = MODULE.detect(repo)
        assert result["database_vendors"] == ["postgresql"]
        assert result["data_entry_candidate"] == "dev-data-feature"


def test_prisma_schema_is_manifest_and_vendor_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "package.json", json.dumps({"devDependencies": {"prisma": "6.0.0"}}))
        write(repo / "prisma" / "schema.prisma", '''
datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}
''')
        result = MODULE.detect(repo)
        assert result["database_vendors"] == ["mssql"]
        assert result["data_entry_candidate"] == "dev-data-feature"
        assert "prisma/schema.prisma" in result["inputs"]


def test_multiple_database_vendors_remain_candidates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "backend" / "pom.xml", '''
<project>
  <dependencies>
    <dependency><groupId>org.postgresql</groupId><artifactId>postgresql</artifactId></dependency>
    <dependency><groupId>org.mariadb.jdbc</groupId><artifactId>mariadb-java-client</artifactId></dependency>
  </dependencies>
</project>
''')
        result = MODULE.detect(repo)
        assert result["database_vendors"] == ["mariadb", "postgresql"]
        assert result["data_entry_candidate"] == "dev-data-feature"


def test_monorepo_detection_is_manifest_bounded() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "backend" / "build.gradle.kts", 'plugins { id("org.springframework.boot") }')
        write(repo / "frontend" / "package.json", json.dumps({
            "dependencies": {"next": "16.0.0", "react": "19.0.0"},
            "devDependencies": {"typescript": "5.9.0", "@playwright/test": "1.55.0"},
        }))
        write(repo / "frontend" / "tsconfig.app.json", "{}")
        write(repo / "frontend" / "node_modules" / "ignored" / "package.json", '{"dependencies":{"vue":"1"}}')
        write(repo / "deep" / "one" / "two" / "three" / "package.json", '{"dependencies":{"vue":"1"}}')

        result = MODULE.detect(repo)
        assert result["stacks"] == ["java", "spring", "typescript", "react", "nextjs"]
        assert result["cross_stack_candidate"] == "dev-api-contract"
        assert "frontend/package.json" in result["inputs"]
        assert "frontend/tsconfig.app.json" in result["inputs"]
        assert not any("node_modules" in path for path in result["inputs"])
        assert not any("deep/one/two/three" in path for path in result["inputs"])


def test_fingerprint_changes_only_when_manifest_evidence_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / "package.json", '{"dependencies":{"react":"19"}}')
        first = MODULE.fingerprint(repo)
        write(repo / "src" / "page.tsx", "export default function Page() { return null }")
        second = MODULE.fingerprint(repo)
        assert first["fingerprint"] == second["fingerprint"]

        write(repo / "package.json", '{"dependencies":{"react":"19","next":"16"}}')
        third = MODULE.fingerprint(repo)
        assert third["fingerprint"] != second["fingerprint"]

        write(repo / "schema.prisma", 'datasource db { provider = "postgresql" url = env("DATABASE_URL") }')
        fourth = MODULE.fingerprint(repo)
        assert fourth["fingerprint"] != third["fingerprint"]


if __name__ == "__main__":
    test_spring_only()
    test_kotlin_only()
    test_kotlin_spring()
    test_kotlin_spring_jpa()
    test_java_kotlin_mixed()
    test_maven_kotlin()
    test_next_typescript_with_tests()
    test_fullstack_contract_candidate()
    test_kotlin_frontend_monorepo()
    test_mssql_driver_detects_data_entry()
    test_node_postgresql_driver_detects_data_entry()
    test_prisma_schema_is_manifest_and_vendor_evidence()
    test_multiple_database_vendors_remain_candidates()
    test_monorepo_detection_is_manifest_bounded()
    test_fingerprint_changes_only_when_manifest_evidence_changes()
    print("[PASS] Stack capability detector tests")

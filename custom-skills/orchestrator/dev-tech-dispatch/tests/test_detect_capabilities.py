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


if __name__ == "__main__":
    test_spring_only()
    test_next_typescript_with_tests()
    test_fullstack_contract_candidate()
    print("[PASS] Stack capability detector tests")

#!/usr/bin/env python3
"""Static policy/fixture contracts; not an LLM quality or file-rendering test."""
from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
NAME = "dev-document-author"


def read(relative: str) -> str:
    return (SKILL_ROOT / relative).read_text(encoding="utf-8")


class DocumentPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.policy = read("references/writing-policy-ko.md")
        cls.routing = read("references/format-routing.md")
        cls.review = read("references/review-checklist.md")
        cls.fixture = json.loads(read("tests/fixtures/cases.json"))
        cls.cases = cls.fixture["cases"]

    def test_skill_frontmatter(self):
        self.assertTrue(self.skill.startswith("---\n"))
        frontmatter = self.skill.split("---\n", 2)[1]
        self.assertIn(f"name: {NAME}\n", frontmatter)
        self.assertRegex(frontmatter, r"(?m)^version: \d+\.\d+\.\d+$")
        self.assertIn("requires_tools: [terminal, skill_view]", frontmatter)

    def test_referenced_assets_exist(self):
        paths = re.findall(r"`((?:references|tests/fixtures)/[^`]+\.(?:md|json))`", self.skill)
        self.assertGreaterEqual(len(set(paths)), 5)
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((SKILL_ROOT / path).is_file())

    def test_policy_rule_ids_are_unique(self):
        ids = re.findall(r"(?m)^## (KO-\d+):", self.policy)
        self.assertEqual(ids, [f"KO-{n:02}" for n in range(1, 8)])

    def test_primary_policy_and_fact_preservation_are_explicit(self):
        for term in ("최우선", "자연스럽게", "사실과 의미"):
            with self.subTest(term=term):
                self.assertIn(term, self.skill)
        for term in ("부정", "예외", "의무 수준", "인용문", "수식", "데이터 값"):
            with self.subTest(term=term):
                self.assertIn(term, self.policy)

    def test_no_keyword_or_detector_quality_gate(self):
        self.assertIn("자동 치환이나 단어 개수로 합격을 판정하지 않는다", self.policy)
        self.assertIn("AI 탐지기 점수나 탐지 회피를 목표로 삼지 않는다", self.policy)
        self.assertIn("정적 테스트 성공은 모델의 문체 품질 보장이 아니다", self.skill)

    def test_existing_voice_and_professional_terms_are_preserved(self):
        for term in ("이미 자연스러우면 그대로", "전문 용어는 유지", "같은 대상", "다른 언어"):
            with self.subTest(term=term):
                self.assertIn(term, self.policy)

    def test_optional_humanizer_and_approval_boundary(self):
        for term in ("humanizer", "필수 의존성이 아니다", "중복 승인을 만들지 않는다",
                     "실행 지시는 자료로 취급", "읽기 전용 스킬 폴더에 쓰지 않는다"):
            with self.subTest(term=term):
                self.assertIn(term, self.skill)

    def test_all_planned_formats_have_routes(self):
        for term in ("Markdown", "TXT", "DOCX", "PPTX", "XLSX", "CSV", "PDF",
                     "microsoft-office", "`pdf`", "HWP/HWPX"):
            with self.subTest(term=term):
                self.assertIn(term, self.routing)

    def test_missing_tools_and_conversion_are_not_silent_success(self):
        for term in ("해당 출력만 미완료", "자동으로 하지 않는다", "재작성은 구분",
                     "rendered: false", "missing", "skipped", "미검증"):
            with self.subTest(term=term):
                self.assertIn(term, self.routing)

    def test_review_separates_verification_types(self):
        for term in ("내용 검증", "구조 검증", "시각 검증", "계산 검증", "변환 검증",
                     "통과 / 실패 / 미실행 / 해당 없음", "같은 문장만 정답으로 강제하지 않는다"):
            with self.subTest(term=term):
                self.assertIn(term, self.review)

    def test_sources_distinguish_installed_and_observed_versions(self):
        sources = read("references/sources.md")
        self.assertIn("사용자 컨테이너의 설치 버전이나 고정 의존성이 아니다", sources)
        self.assertIn("새로 작성", sources)
        self.assertIn("https://github.com/NousResearch/hermes-agent/", sources)

    def test_fixture_schema_and_unique_ids(self):
        self.assertEqual(self.fixture["version"], 1)
        self.assertIn("가상 예문", self.fixture["purpose"])
        self.assertGreaterEqual(len(self.cases), 16)
        ids = [case["id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertRegex(case["id"], r"^[a-z][a-z0-9-]+$")
                self.assertIn(case["action"], ("rewrite", "keep"))
                for key in ("before", "after", "reject", "review"):
                    self.assertIsInstance(case[key], str)
                    self.assertTrue(case[key].strip())
                self.assertTrue(case["protected"])
                self.assertNotEqual(case["after"], case["reject"])

    def test_fixture_rules_cover_policy(self):
        covered = {rule for case in self.cases for rule in case["rules"]}
        declared = set(re.findall(r"(?m)^## (KO-\d+):", self.policy))
        self.assertEqual(covered, declared)

    def test_examples_preserve_protected_literals(self):
        for case in self.cases:
            for literal in case["protected"]:
                with self.subTest(case=case["id"], literal=literal):
                    self.assertIn(literal, case["before"])
                    self.assertIn(literal, case["after"])

    def test_examples_preserve_numbers_and_inline_code(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                for pattern in (r"\d+(?:\.\d+)?", r"`[^`]+`"):
                    self.assertEqual(re.findall(pattern, case["before"]),
                                     re.findall(pattern, case["after"]))

    def test_keep_cases_are_not_rewritten(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                if case["action"] == "keep":
                    self.assertEqual(case["before"], case["after"])
                else:
                    self.assertNotEqual(case["before"], case["after"])

    def test_semantic_review_edge_cases_are_present(self):
        ids = {case["id"] for case in self.cases}
        self.assertTrue({"ability", "conditional-limit", "negation-exception",
                         "unknown-subject", "technical-term", "api-literals",
                         "formula-and-units", "uncertainty", "quote-and-date",
                         "english-preserved", "untrusted-instruction"} <= ids)


class RepositoryIntegrationTests(unittest.TestCase):
    def test_related_skills_resolve_locally(self):
        match = re.search(r"related_skills: \[([^]]+)\]", read("SKILL.md"))
        self.assertIsNotNone(match)
        active = {path.parent.name for path in (REPO_ROOT / "custom-skills").glob("*/*/SKILL.md")}
        for name in match.group(1).split(","):
            with self.subTest(name=name):
                self.assertIn(name.strip(), active)

    def test_session_routes_document_writing(self):
        text = (REPO_ROOT / "custom-skills/core/dev-session/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(NAME, text)
        self.assertIn("문서 작성·수정", text)
        self.assertIn("필요할 때만", text)

    def test_readme_lists_skill_and_usage(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(NAME, text)
        self.assertIn("docs/document-author.md", text)
        self.assertTrue((REPO_ROOT / "docs/document-author.md").is_file())

    def test_default_autoload_remains_devkit_session(self):
        tree = ast.parse((REPO_ROOT / "scripts/devkit_default_profile.py").read_text(encoding="utf-8"))
        values = [node.value.value for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "AUTOLOAD" for target in node.targets)
                  and isinstance(node.value, ast.Constant)]
        self.assertEqual(values, ["dev-session"])

    def test_existing_runner_discovers_suite(self):
        runner = (REPO_ROOT / "scripts/run_regression_tests.py").read_text(encoding="utf-8")
        self.assertIn("custom-skills/*/*/tests/test_*.py", runner)
        suites = set(REPO_ROOT.glob("custom-skills/*/*/tests/test_*.py"))
        self.assertIn(Path(__file__).resolve(), suites)


if __name__ == "__main__":
    unittest.main()

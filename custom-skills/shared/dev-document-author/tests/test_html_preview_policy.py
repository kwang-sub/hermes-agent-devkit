#!/usr/bin/env python3
"""Static workflow, native JSON template and manual-case contracts; not agent E2E."""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shlex
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
LABEL = "PPT 제작용 HTML 시안"


def read(relative: str) -> str:
    return (SKILL_ROOT / relative).read_text(encoding="utf-8")


class MockMarkup(HTMLParser):
    """Inspect only markup; do not execute scripts or resolve any assets."""
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.attributes: list[tuple[str, str | None]] = []
        self.text: list[str] = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


class HtmlPreviewPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.preview = read("references/html-preview.md")
        cls.routing = read("references/format-routing.md")
        cls.review = read("references/review-checklist.md")

    def test_version_and_public_entry_stay_compatible(self):
        self.assertIn("name: dev-document-author\n", self.skill)
        self.assertIn("version: 0.2.0\n", self.skill)
        self.assertIn("requires_tools: [terminal, skill_view]", self.skill)
        self.assertIn("사람이 실제 업무에서 사용하는 말", self.skill)
        self.assertIn("사실과 의미는 바꾸지 않는다", self.skill)

    def test_preview_reference_is_loaded_before_file_creation(self):
        self.assertIn("전체 파일을 생성하기 전에 `references/html-preview.md`", self.skill)
        a = self.skill.index("6. **PPTX 신규 작성")
        b = self.skill.index("7. 시안 대상이면")
        c = self.skill.index("8. 현재 시안에 대한 명시적인 선택")
        self.assertLess(a, b)
        self.assertLess(b, c)

    def test_preview_handoff_stops_before_full_ppt(self):
        for value in ("사용자 선택을 기다리고 이번 응답을 종료", "전체 PPT 생성은 하지 않는다",
                      "작업 진행 승인은 디자인 A/B 선택이 아니다"):
            with self.subTest(value=value):
                self.assertIn(value, self.skill)

    def test_writing_review_does_not_cancel_design_selection(self):
        writing = read("references/writing-policy-ko.md")
        self.assertIn("디자인 선택을 생략하는 근거가 아니다", writing)
        self.assertIn("시안 선택은 `dev-session` 변경 승인과 구분", writing)

    def test_minor_edit_template_and_user_skip_are_exempt(self):
        for value in ("단순 문구", "같은 범위에 이미 승인된 양식", "명시적인 시안 생략"):
            self.assertIn(value, self.skill)
        self.assertIn("다른 생략 조건이 있어도 비교 요청을 우선", self.preview)
        self.assertIn("DOCX/XLSX/CSV/PDF의 일반 작업", self.skill)

    def test_renderer_is_not_a_preview_dependency(self):
        self.assertIn("PPT 렌더러가 없어도 HTML 시안은 제시한다", self.preview)
        self.assertIn("HTML 작성·브라우저 표시에는 PPT 렌더러가 필요하지 않다", self.routing)
        self.assertIn("HTML 시안 확인은 최종 PPT 시각 검증이 아니다", self.skill)

    def test_actual_content_and_two_distinct_variants(self):
        for value in ("대표 페이지 2~3개", "같은 실제 문구·수치·조건·이미지",
                      "색상만 바꾼 복제본", "실제 앱 화면처럼 꾸며내지 않는다"):
            self.assertIn(value, self.preview)

    def test_fixed_canvas_and_no_web_only_effects(self):
        for value in ("1280×720", "균등 축소", "재배치되는 반응형 웹페이지",
                      "웹 px를 그대로 PPT pt로 취급하지 않는다", "애니메이션·호버·스크롤"):
            self.assertIn(value, self.preview)

    def test_fallback_is_deliverable_html_not_silent_ppt(self):
        for value in ("self-contained 로컬 HTML", "실제 bind 경로 또는 첨부 경로",
                      "시안 제공 미완료", "피드백 저장 버튼을 가짜로 만들지 않는다"):
            self.assertIn(value, self.preview)
        self.assertIn("선택을 받지 않은 전체 PPT로 대체하지 않는다", self.routing)

    def test_no_automatic_install_or_external_publish(self):
        self.assertIn("도구 설치, 권한 변경, 컨테이너 재시작, 외부 전송", self.preview)
        self.assertIn("외부 게시·Discord 자동 재개·새 백그라운드 서비스는 켜지 않는다", self.preview)
        self.assertIn("--no-wake", self.skill)

    def test_cli_example_preserves_initial_local_boundary(self):
        block = re.search(r"```bash\n(.*?)\n```", self.preview, re.S).group(1)
        argv = shlex.split(block.replace("\\\n", " "))
        self.assertEqual(argv[:3], ["hermes", "mockreview", "create"])
        for flag in ("--no-wake", "--no-allow-live-demo", "--no-interactive", "--no-theme-toggle"):
            self.assertIn(flag, argv)
        for flag, expected in (("--mode", "local"), ("--footer-button", "send"),
                               ("--project", "$PROJECT"), ("--decisions", "$DECISIONS"),
                               ("--devices", "desktop")):
            self.assertEqual(argv[argv.index(flag) + 1], expected)
        for flag in ("--wake", "--allow-live-demo", "--no-design", "--off-brand", "--prototype"):
            self.assertNotIn(flag, argv)

    def test_actual_schema_and_project_are_required(self):
        for value in ("실제 스키마 또는 CLI 도움말", "대상 문서 프로젝트의 실제 Linux 절대 경로",
                      "DevKit 설치 폴더를 대상 문서의 프로젝트로 잘못 쓰지 않는다",
                      "브랜드 검사를 임의 우회하지 않는다"):
            self.assertIn(value, self.preview)

    def test_current_round_selection_is_not_fabricated(self):
        for value in ("approve", "option", "recommended", "change", "skip", "무응답",
                      "문서·회차가 다르거나", "이전 회차", "Git 게시"):
            self.assertIn(value, self.preview)
        self.assertIn("현재 후보에 대한 선택 확인 전 전체 PPT 제작 보류", self.preview)

    def test_editable_ppt_reuses_selected_html(self):
        for value in ("선택한 HTML/CSS", "기본 카드 템플릿으로 다시 작성하지 않는다",
                      "텍스트 상자·도형·표·이미지", "전체 슬라이드를 이미지 한 장으로 붙이는 방식은 기본으로 쓰지 않는다",
                      "무손실 자동 변환이 아니다"):
            self.assertIn(value, self.preview)

    def test_stage_specific_verification_and_reporting(self):
        for value in ("HTML 시안 검증", "시안 선택 확인", "내용 검증", "구조 검증", "시각 검증",
                      "통과 / 실패 / 미실행 / 해당 없음"):
            self.assertIn(value, self.review)
        self.assertIn("모델의 시안 제시 행동이나 디자인 품질을 보장", self.preview)

    def test_rule_ids_are_unique_and_complete(self):
        ids = re.findall(r"(?m)^## (HP-\d+):", self.preview)
        self.assertEqual(ids, [f"HP-{n:02}" for n in range(1, 9)])

    def test_new_assets_and_doc_links_resolve(self):
        for path in ("references/html-preview.md", "templates/pptx-html-decisions.json",
                     "tests/fixtures/html-preview-cases.json"):
            self.assertTrue((SKILL_ROOT / path).is_file())
        for path in ("docs/document-author.md", "docs/design-plugins.md"):
            self.assertTrue((REPO_ROOT / path).is_file())
            self.assertIn("HTML", (REPO_ROOT / path).read_text(encoding="utf-8"))

    def test_existing_regression_runner_discovers_this_suite(self):
        runner = (REPO_ROOT / "scripts/run_regression_tests.py").read_text(encoding="utf-8")
        self.assertIn("custom-skills/*/*/tests/test_*.py", runner)
        self.assertIn(Path(__file__).resolve(), set(REPO_ROOT.glob("custom-skills/*/*/tests/test_*.py")))

    def test_no_mandatory_new_service_or_approval_database(self):
        for value in ("승인 DB·자동 실행 서버를 만들지 않는다", "별도 승인 DB나 런타임 상태 머신은 만들지 않는다"):
            self.assertIn(value, self.preview)
        self.assertIn("중복 승인을 만들지 않는다", self.skill)


class NativeTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read("templates/pptx-html-decisions.json")
        cls.template = json.loads(cls.text)
        cls.blocks = cls.template["blocks"]

    def test_size_and_top_level_schema(self):
        self.assertLess(len(self.text.encode("utf-8")), 3_000_000)
        self.assertEqual(self.template["preset"], "design")
        self.assertNotIn("gate", self.template)
        self.assertTrue(1 <= len(self.blocks) <= 60)

    def test_two_or_three_representative_pages_and_two_options(self):
        self.assertTrue(2 <= len(self.blocks) <= 3)
        for block in self.blocks:
            self.assertEqual(block["type"], "decision")
            self.assertEqual([o["id"] for o in block["options"]], ["a", "b"])
            self.assertIn(block["layout"], ("side", "switch"))
            self.assertEqual(block["desktop_width"], 1280)

    def test_ids_and_field_limits(self):
        ids = [block["id"] for block in self.blocks]
        self.assertEqual(len(ids), len(set(ids)))
        for block in self.blocks:
            self.assertRegex(block["id"], r"^[a-z0-9][a-z0-9-]{0,23}$")
            self.assertLessEqual(len(block["title"]), 200)
            for option in block["options"]:
                self.assertLessEqual(len(option["label"]), 80)
        self.assertLessEqual(len(self.template["intro"]), 3000)
        self.assertLessEqual(len(self.template["next"]), 600)

    def test_fixed_slide_canvas(self):
        css = self.template["extra_css"]
        for value in ("width:1280px", "height:720px", "box-sizing:border-box"):
            self.assertIn(value, css)
        self.assertNotIn("@media", css)

    def test_template_is_labeled_and_is_not_presented_as_user_content(self):
        self.assertIn("형식 참고 템플릿", self.template["intro"])
        self.assertIn("실제 내용으로 교체", self.template["intro"])
        for block in self.blocks:
            for option in block["options"]:
                self.assertIn(LABEL, option["html"])
                self.assertIn("최종 PPT 렌더링 아님", option["html"])
                self.assertRegex(option["html"], r"\{\{[A-Z0-9_]+\}\}")

    def test_variants_preserve_same_placeholders(self):
        for block in self.blocks:
            a, b = block["options"]
            self.assertEqual(Counter(re.findall(r"\{\{[A-Z0-9_]+\}\}", a["html"])),
                             Counter(re.findall(r"\{\{[A-Z0-9_]+\}\}", b["html"])))
            self.assertNotEqual(a["html"], b["html"])

    def test_template_uses_only_static_local_markup(self):
        forbidden = {"script", "iframe", "frame", "object", "embed", "base", "meta", "link", "form"}
        for block in self.blocks:
            for option in block["options"]:
                parsed = MockMarkup(option["html"])
                self.assertFalse(forbidden.intersection(parsed.tags))
                for name, value in parsed.attributes:
                    self.assertFalse(name.lower().startswith("on"))
                    self.assertFalse(re.match(r"(?:javascript:|https?:|//)", value or "", re.I))
        self.assertNotRegex(self.template["extra_css"], r"(?i)@import|url\s*\(")

    def test_sending_does_not_claim_automatic_resume(self):
        self.assertIn("작업을 자동 재개하지 않습니다", self.template["next"])
        self.assertIn("같은 Hermes 세션", self.template["next"])


class ManualScenarioContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(read("tests/fixtures/html-preview-cases.json"))
        cls.cases = cls.fixture["cases"]

    def test_scenarios_are_manual_not_runtime_proof(self):
        self.assertEqual(self.fixture["version"], 1)
        self.assertIn("모델 행동 자동 검증 결과가 아니다", self.fixture["purpose"])
        self.assertGreaterEqual(len(self.cases), 16)

    def test_cases_are_unique_and_well_formed(self):
        ids = [case["id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in self.cases:
            for key in ("request", "rules", "expected", "forbidden"):
                self.assertTrue(case[key])
            self.assertFalse(set(case["expected"]).intersection(case["forbidden"]))

    def test_manual_cases_cover_all_policy_rules(self):
        declared = set(re.findall(r"(?m)^## (HP-\d+):", read("references/html-preview.md")))
        covered = {rule for case in self.cases for rule in case["rules"]}
        self.assertEqual(covered, declared)

    def test_original_failure_and_selection_edge_cases_are_retained(self):
        ids = {case["id"] for case in self.cases}
        self.assertTrue({"new-ppt", "no-renderer", "no-board", "no-access", "explicit-skip",
                         "minor-copy", "approved-template", "missing-option", "stale-round",
                         "change-skip", "selection", "injected-comment", "final-verify"} <= ids)


if __name__ == "__main__":
    unittest.main()

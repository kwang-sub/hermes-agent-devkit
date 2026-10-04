#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "screen_spec_guard.py"
SPEC = importlib.util.spec_from_file_location("screen_spec_guard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def image_spec(reference: str = "./reference.png", status: str = "APPROVED") -> str:
    return f"""---
screen: dashboard
status: {status}
source: IMAGE
reference: {reference}
fidelity: VISUAL
viewport: 1440x1024
view_strategy: RESPONSIVE
---
# Dashboard
"""


def test_valid_image_reference() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = root / "docs/ui/screens/dashboard/screen-spec.md"
        write(spec, image_spec())
        (spec.parent / "reference.png").write_bytes(b"png")
        result = MODULE.validate(spec)
        assert result["source"] == "IMAGE"
        assert result["status"] == "APPROVED"
        assert result["view_strategy"] == "RESPONSIVE"


def test_missing_image_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "screen-spec.md"
        write(spec, image_spec())
        try:
            MODULE.validate(spec)
        except MODULE.SpecError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("missing IMAGE reference must be blocked")


def test_valid_figma_reference() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "screen-spec.md"
        write(spec, """---
screen: dashboard
status: REFERENCE
source: FIGMA
reference: https://www.figma.com/design/abc/file?node-id=1-2
fidelity: STRUCTURE
viewport: UNKNOWN
---
# Dashboard
""")
        result = MODULE.validate(spec)
        assert result["source"] == "FIGMA"
        assert result["status"] == "REFERENCE"



def test_legacy_spec_without_view_strategy_remains_readable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = root / "screen-spec.md"
        write(spec, """---
screen: dashboard
status: APPROVED
source: IMAGE
reference: ./reference.png
fidelity: VISUAL
viewport: 1440x1024
---
# Dashboard
""")
        (spec.parent / "reference.png").write_bytes(b"png")
        result = MODULE.validate(spec)
        assert result["view_strategy"] == "UNSPECIFIED"


def test_invalid_view_strategy_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = root / "screen-spec.md"
        write(spec, image_spec().replace("view_strategy: RESPONSIVE", "view_strategy: DEVICE_ONLY"))
        (spec.parent / "reference.png").write_bytes(b"png")
        try:
            MODULE.validate(spec)
        except MODULE.SpecError as exc:
            assert "invalid view_strategy" in str(exc)
        else:
            raise AssertionError("invalid view strategy must be blocked")


def test_invalid_enums_are_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "screen-spec.md"
        write(spec, image_spec(status="FINAL"))
        (spec.parent / "reference.png").write_bytes(b"png")
        try:
            MODULE.validate(spec)
        except MODULE.SpecError as exc:
            assert "invalid status" in str(exc)
        else:
            raise AssertionError("invalid design status must be blocked")


# Spec v2 contract tests intentionally use the standard library only.
import subprocess
import sys
import unittest


BEHAVIOR_BODY = """
## 화면 기능 목록

| 기능 ID | 기능명 | 사용자 목적 / 설명 | 연결 UI ID | 확정 상태 | 근거 |
| --- | --- | --- | --- | --- | --- |
| F-01 | 조회 | 지정한 기간의 결과를 조회한다 | UI-01, UI-02, UI-03 | CONFIRMED | 사용자 승인 요구사항 1항 |
| F-02 | 결과 확인 | 조회 결과의 값을 읽는다 | UI-03 | CONFIRMED | 기존 결과 카드의 동작 확인 |

## UI 요소 및 기능 연결

| UI ID | 요소 / 종류 / 표시명 | 위치 / 영역 | 연결 기능 ID | 노출 조건 | 활성화 / 표시 규칙 | 플랫폼 차이 |
| --- | --- | --- | --- | --- | --- | --- |
| UI-01 | 날짜 입력 | 상단 조건 영역 | F-01 | 항상 표시 | 조회 중 비활성화 | 동일 |
| UI-02 | 조회 버튼 | 날짜 오른쪽 | F-01 | 항상 표시 | 유효한 날짜이고 조회 중이 아니면 활성화 | 모바일은 날짜 아래 |
| UI-03 | 결과 카드 | 본문 | F-01, F-02 | 항상 표시 | 빈 결과는 —, 그 외에는 정수 건수 | 동일 |

## 기능별 동작 명세

### F-01 — 조회

| 항목 | 동작 명세 |
| --- | --- |
| 관련 UI | UI-01, UI-02, UI-03 |
| 실행 시점 | 조회 버튼 클릭 또는 날짜 필드에서 Enter. 날짜 변경만으로 조회하지 않는다 |
| 사전 조건 / 입력 검증 | 시작일과 종료일 필수. 시작일이 늦으면 입력 아래 오류 표시 |
| 정상 결과 | 조회 응답의 결과 카드와 기간 표시를 함께 갱신 |
| 상태 / 예외 처리 | 로딩은 기존 결과와 기간을 유지. 빈 결과는 —. 실패는 입력과 이전 결과를 유지하고 오류 표시 |
| 화면 이동 / 저장 | 이동하지 않음. 서버에 조회 조건을 저장하지 않음 |
| 플랫폼 차이 | 공통 동작. 버튼의 배치만 다름 |
| 재시도 / 중복 방지 | 조회 중 버튼과 입력을 비활성화. 실패 후 버튼으로 재시도 |

### F-02 — 결과 확인

| 항목 | 동작 명세 |
| --- | --- |
| 관련 UI | UI-03 |
| 실행 시점 | 조회 성공/실패/빈 결과에 맞춰 자동 표시 |
| 사전 조건 / 입력 검증 | 해당 없음: 사용자가 입력하지 않는 결과 표시 기능 |
| 정상 결과 | 정수 건수와 적용된 조회 기간 표시 |
| 상태 / 예외 처리 | F-01의 결과 상태를 반영하며 독립 요청을 보내지 않음 |
| 화면 이동 / 저장 | 카드 클릭으로 이동하지 않음. 데이터를 저장하지 않음 |
| 플랫폼 차이 | 동일 |

## 기능별 검증 조건

| 검증 ID | 기능 ID | 사전 조건 / 상태 | 사용자 조작 / 트리거 | 기대 결과 | 검증 방법 |
| --- | --- | --- | --- | --- | --- |
| AC-01 | F-01 | 유효한 기간 | 조회 클릭 | 해당 기간으로 한 번 요청하고 결과와 기간을 함께 갱신 | 기존 컴포넌트 테스트 |
| AC-02 | F-02 | 조회 응답에 결과 존재 | 조회 응답 완료 | 건수를 정수로 표시하고 독립 요청 없음 | 기존 결과 표시 테스트 |
"""


def behavior_spec() -> str:
    return image_spec().replace("screen: dashboard", "screen: dashboard\nspec_version: 2\nbehavior_status: APPROVED") + BEHAVIOR_BODY


class BehaviorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "screen-spec.md"
        (self.root / "reference.png").write_bytes(b"image existence fixture")

    def validate(self, text: str | None = None, **options) -> dict[str, str]:
        write(self.path, behavior_spec() if text is None else text)
        return MODULE.validate(self.path, **options)

    def blocked(self, text: str, expected: str, **options) -> None:
        with self.assertRaisesRegex(MODULE.SpecError, expected):
            self.validate(text, **options)

    def cli(self, text: str, *flags: str) -> subprocess.CompletedProcess:
        write(self.path, text)
        return subprocess.run([sys.executable, str(SCRIPT), "--spec", str(self.path), *flags],
                              capture_output=True, text=True, encoding="utf-8", timeout=10)

    def test_valid_many_to_many_contract(self) -> None:
        result = self.validate(require_approved_behavior=True)
        self.assertEqual(result["spec_version"], "2")
        self.assertEqual(result["behavior_contract_status"], "STRUCTURE_PASS")
        self.assertEqual(result["behavior_status"], "APPROVED")

    def test_legacy_default_is_not_behavior_pass(self) -> None:
        result = self.validate(image_spec())
        self.assertEqual(result["behavior_contract_status"], "LEGACY_NOT_CHECKED")
        self.assertEqual(result["behavior_status"], "UNSPECIFIED")

    def test_explicit_legacy_version_remains_readable(self) -> None:
        text = image_spec().replace("screen: dashboard", "screen: dashboard\nspec_version: 1")
        self.assertEqual(self.validate(text)["spec_version"], "1")

    def test_legacy_is_rejected_only_when_strict_requested(self) -> None:
        self.blocked(image_spec(), "spec_version: 2 is required", require_behavior_contract=True)

    def test_approved_flag_also_requires_v2(self) -> None:
        self.blocked(image_spec(), "spec_version: 2 is required", require_approved_behavior=True)

    def test_unknown_version_is_rejected(self) -> None:
        self.blocked(behavior_spec().replace("spec_version: 2", "spec_version: 9"), "unsupported spec_version")

    def test_explicit_blank_version_is_not_legacy(self) -> None:
        self.blocked(behavior_spec().replace("spec_version: 2", "spec_version:"), "unsupported spec_version")

    def test_behavior_status_is_required(self) -> None:
        self.blocked(behavior_spec().replace("behavior_status: APPROVED\n", ""), "behavior_status must")

    def test_behavior_status_enum_is_checked(self) -> None:
        self.blocked(behavior_spec().replace("behavior_status: APPROVED", "behavior_status: FINAL"), "behavior_status must")

    def test_design_approval_does_not_approve_behavior(self) -> None:
        text = behavior_spec().replace("behavior_status: APPROVED", "behavior_status: DRAFT")
        result = self.validate(text, require_behavior_contract=True)
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["behavior_status"], "DRAFT")
        self.blocked(text, "independently of design approval", require_approved_behavior=True)

    def test_draft_can_record_explicit_unknown(self) -> None:
        text = behavior_spec().replace("behavior_status: APPROVED", "behavior_status: DRAFT")
        text = text.replace("| CONFIRMED |", "| UNKNOWN |", 1)
        text = text.replace("사용자 승인 요구사항 1항", "UNKNOWN: 조회 정책 결정 필요")
        self.assertEqual(self.validate(text)["behavior_status"], "DRAFT")

    def test_approved_contract_cannot_contain_unconfirmed_feature(self) -> None:
        for state in ("PROPOSED", "UNKNOWN"):
            with self.subTest(state=state):
                self.blocked(behavior_spec().replace("| CONFIRMED |", f"| {state} |", 1), "unconfirmed feature")

    def test_approved_contract_cannot_have_unknown_detail(self) -> None:
        text = behavior_spec().replace("| 정상 결과 | 조회 응답의 결과 카드와 기간 표시를 함께 갱신 |", "| 정상 결과 | UNKNOWN: 결과 처리 미확정 |")
        self.blocked(text, "unresolved approved behavior")

    def test_missing_each_required_section(self) -> None:
        for section in MODULE.BEHAVIOR_SECTIONS:
            with self.subTest(section=section):
                self.blocked(behavior_spec().replace(f"## {section}", "## Removed", 1), "missing behavior sections")

    def test_duplicate_section(self) -> None:
        self.blocked(behavior_spec() + "\n## 화면 기능 목록\n", "duplicate contract heading")

    def test_missing_feature_table(self) -> None:
        text = behavior_spec().replace("| 기능 ID | 기능명 | 사용자 목적 / 설명 | 연결 UI ID | 확정 상태 | 근거 |", "Feature overview")
        self.blocked(text, "missing table header")

    def test_missing_feature_rows(self) -> None:
        text = behavior_spec()
        text = "\n".join(line for line in text.splitlines() if not line.startswith(("| F-01 |", "| F-02 |")))
        self.blocked(text, "missing table header or data rows")

    def test_invalid_separator_is_rejected(self) -> None:
        self.blocked(behavior_spec().replace("| --- | --- | --- | --- | --- | --- |", "| x | --- | --- | --- | --- | --- |", 1), "invalid table separator")

    def test_duplicate_feature_id(self) -> None:
        self.blocked(behavior_spec().replace("| F-02 | 결과 확인", "| F-01 | 결과 확인"), "duplicate F ID")

    def test_invalid_feature_id(self) -> None:
        self.blocked(behavior_spec().replace("| F-01 | 조회", "| FEATURE-01 | 조회"), "invalid F ID")

    def test_duplicate_ui_id(self) -> None:
        self.blocked(behavior_spec().replace("| UI-02 | 조회 버튼", "| UI-01 | 조회 버튼"), "duplicate UI ID")

    def test_unknown_ui_reference(self) -> None:
        self.blocked(behavior_spec().replace("UI-01, UI-02, UI-03 | CONFIRMED", "UI-01, UI-99, UI-03 | CONFIRMED"), "unknown references")

    def test_unknown_feature_reference(self) -> None:
        self.blocked(behavior_spec().replace("| 상단 조건 영역 | F-01 |", "| 상단 조건 영역 | F-99 |"), "unknown references")

    def test_nonreciprocal_ui_mapping(self) -> None:
        self.blocked(behavior_spec().replace("| 본문 | F-01, F-02 |", "| 본문 | F-01 |"), "non-reciprocal")

    def test_extra_reverse_mapping_is_rejected(self) -> None:
        self.blocked(behavior_spec().replace("| 상단 조건 영역 | F-01 |", "| 상단 조건 영역 | F-01, F-02 |"), "non-reciprocal")

    def test_duplicate_id_reference(self) -> None:
        self.blocked(behavior_spec().replace("UI-01, UI-02, UI-03 | CONFIRMED", "UI-01, UI-01, UI-03 | CONFIRMED"), "duplicate UI references")

    def test_missing_detail_for_feature(self) -> None:
        text = behavior_spec()
        start = text.index("### F-02")
        end = text.index("## 기능별 검증 조건")
        self.blocked(text[:start] + text[end:], "missing behavior details")

    def test_detail_references_unknown_feature(self) -> None:
        self.blocked(behavior_spec().replace("### F-02", "### F-99"), "unknown behavior detail")

    def test_duplicate_feature_detail(self) -> None:
        self.blocked(behavior_spec().replace("### F-02 — 결과 확인", "### F-01 — Another"), "duplicate behavior detail")

    def test_missing_each_required_detail_field(self) -> None:
        for field in MODULE.DETAIL_FIELDS:
            with self.subTest(field=field):
                text = behavior_spec()
                row = next(line for line in text.splitlines() if line.startswith(f"| {field} |"))
                self.blocked(text.replace(row + "\n", "", 1), "missing behavior fields")

    def test_detail_ui_mismatch(self) -> None:
        self.blocked(behavior_spec().replace("| 관련 UI | UI-01, UI-02, UI-03 |", "| 관련 UI | UI-02 |"), "behavior detail UI mismatch")

    def test_duplicate_detail_field(self) -> None:
        self.blocked(behavior_spec().replace("| 실행 시점 | 조회", "| 정상 결과 | 조회", 1), "duplicate behavior field")

    def test_empty_required_cell(self) -> None:
        self.blocked(behavior_spec().replace("지정한 기간의 결과를 조회한다", ""), "empty or placeholder")

    def test_placeholder_cells(self) -> None:
        for placeholder in ("TODO", "TBD: 결정 필요", "...", "<사용자 목적>", "N/A"):
            with self.subTest(placeholder=placeholder):
                self.blocked(behavior_spec().replace("지정한 기간의 결과를 조회한다", placeholder), "placeholder")

    def test_visibility_and_activation_are_both_required(self) -> None:
        self.blocked(behavior_spec().replace("| 항상 표시 | 조회 중 비활성화 |", "| 항상 표시 | |"), "empty or placeholder")

    def test_unknown_ac_feature(self) -> None:
        self.blocked(behavior_spec().replace("| AC-02 | F-02 |", "| AC-02 | F-99 |"), "unknown references")

    def test_duplicate_ac_id(self) -> None:
        self.blocked(behavior_spec().replace("| AC-02 |", "| AC-01 |"), "duplicate AC ID")

    def test_missing_feature_ac_coverage(self) -> None:
        self.blocked(behavior_spec().replace("| AC-02 | F-02 |", "| AC-02 | F-01 |"), "missing acceptance coverage")

    def test_empty_expected_result(self) -> None:
        self.blocked(behavior_spec().replace("건수를 정수로 표시하고 독립 요청 없음", ""), "empty or placeholder")

    def test_comments_cannot_provide_spec_body(self) -> None:
        text = behavior_spec().replace(BEHAVIOR_BODY, "<!--\n" + BEHAVIOR_BODY + "\n-->")
        self.blocked(text, "missing behavior sections")

    def test_fenced_examples_cannot_provide_spec_body(self) -> None:
        for fence in ("```", "~~~~"):
            with self.subTest(fence=fence):
                text = behavior_spec().replace(BEHAVIOR_BODY, fence + "markdown\n" + BEHAVIOR_BODY + "\n" + fence)
                self.blocked(text, "missing behavior sections")

    def test_append_fenced_duplicate_example_is_ignored(self) -> None:
        self.validate(behavior_spec() + "\n```markdown\n" + BEHAVIOR_BODY + "\n```\n")

    def test_parent_heading_ends_contract_section(self) -> None:
        text = behavior_spec().replace("| 기능 ID | 기능명", "# Unrelated\n| 기능 ID | 기능명", 1)
        self.blocked(text, "missing table header")

    def test_escaped_pipe_and_inline_code_are_supported(self) -> None:
        text = behavior_spec().replace("조회 버튼", r"조회 \| 다시 조회 버튼")
        text = text.replace("UI-01, UI-02, UI-03", "`UI-01`, `UI-02`, `UI-03`")
        self.validate(text)

    def test_linebreak_tag_is_not_a_placeholder(self) -> None:
        self.validate(behavior_spec().replace("지정한 기간의 결과를 조회한다", "조건 입력<br>결과 조회"))

    def test_unescaped_pipe_rejected(self) -> None:
        self.blocked(behavior_spec().replace("조회 버튼", "조회 | 다시 조회"), "wrong table column count")

    def test_crlf_is_readable(self) -> None:
        self.validate(behavior_spec().replace("\n", "\r\n"))

    def test_figma_uses_same_behavior_contract(self) -> None:
        text = behavior_spec().replace("source: IMAGE", "source: FIGMA")
        text = text.replace("reference: ./reference.png", "reference: https://www.figma.com/design/abc/file?node-id=1-2")
        self.assertEqual(self.validate(text)["source"], "FIGMA")

    def test_no_ui_automatic_feature_requires_rationale(self) -> None:
        text = behavior_spec().replace("UI-01, UI-02, UI-03 | CONFIRMED", "NONE | CONFIRMED")
        text = text.replace("| 관련 UI | UI-01, UI-02, UI-03 |", "| 관련 UI | NONE |")
        text = "\n".join(line for line in text.splitlines() if not line.startswith(("| UI-01 |", "| UI-02 |")))
        text = text.replace("| 본문 | F-01, F-02 |", "| 본문 | F-02 |")
        self.blocked(text, "no-UI rationale")
        self.validate(text.replace("| 관련 UI | NONE |", "| 관련 UI | NONE |\n| 미노출 사유 | 자동 상태 정리로 직접 UI를 제공하지 않음 |"))

    def test_entirely_nonvisual_feature_can_use_none_inventory(self) -> None:
        text = behavior_spec()
        start = text.index("## UI 요소 및 기능 연결")
        end = text.index("## 기능별 동작 명세")
        text = text[:start] + "## UI 요소 및 기능 연결\n\nNONE\n\n" + text[end:]
        for refs in ("UI-01, UI-02, UI-03", "UI-03"):
            text = text.replace(f"{refs} | CONFIRMED", "NONE | CONFIRMED")
            text = text.replace(f"| 관련 UI | {refs} |", "| 관련 UI | NONE |\n| 미노출 사유 | 화면 이탈 시 자동 정리이며 직접 표시하지 않음 |")
        self.validate(text)

    def test_cli_reports_structure_separately(self) -> None:
        result = self.cli(behavior_spec(), "--require-approved-behavior")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BEHAVIOR_CONTRACT_STATUS=STRUCTURE_PASS", result.stdout)
        self.assertIn("BEHAVIOR_STATUS=APPROVED", result.stdout)

    def test_cli_warns_for_legacy(self) -> None:
        result = self.cli(image_spec())
        self.assertEqual(result.returncode, 0)
        self.assertIn("BEHAVIOR_CONTRACT_STATUS=LEGACY_NOT_CHECKED", result.stdout)
        self.assertIn("WARNING=Legacy", result.stdout)

    def test_cli_strict_legacy_failure(self) -> None:
        result = self.cli(image_spec(), "--require-behavior-contract")
        self.assertEqual(result.returncode, 2)
        self.assertIn("SCREEN_SPEC_STATUS=blocked", result.stdout)

    def test_cli_missing_file_is_controlled_error(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--spec", str(self.root / "missing.md")],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_invalid_utf8_is_controlled_error(self) -> None:
        self.path.write_bytes(b"\xff\xfe")
        result = subprocess.run([sys.executable, str(SCRIPT), "--spec", str(self.path)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    test_valid_image_reference()
    test_missing_image_is_blocked()
    test_valid_figma_reference()
    test_legacy_spec_without_view_strategy_remains_readable()
    test_invalid_view_strategy_is_blocked()
    test_invalid_enums_are_blocked()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BehaviorContractTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"[PASS] Screen specification guard tests: 6 legacy + {result.testsRun} behavior cases")

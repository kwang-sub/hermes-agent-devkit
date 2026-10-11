#!/usr/bin/env python3
"""Contract + read-only render tests for the Recovery Plan Korean preview."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import unittest
import re
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from devkit_recovery_plan_style import (
    ACCENT, ACCENT_ANSI, HEADING, split_recovery_response,
    style_recovery_response, style_stream_line, style_reasoning_recovery_line,
    PRESERVE_ANSI, PRESERVE_BAR_ANSI, BAR_ANSI, CHANGE_SECTION, PRESERVE_SECTION,
)
import patch_hermes_recovery_plan_style as patcher

SAMPLE = (
    "## 작업 복구 분석\n\n"
    "**보드:** hdc-218\n"
    "**현재 상태:** TRIAGE\n"
    "### 차단 원인\n"
    "- upstream Context Gate\n"
    "### 유지 계약\n"
    "- existing source\n\n"
    "---\n"
    "## 🛠 복구 계획\n"
    "> 1. status/read-back\n"
    "> 2. preserve existing source\n"
    "> 3. targeted test and review\n"
    "---\n"
    "### 승인 기준\n"
    "- Valid Context\n"
    "### 검증 계획\n"
    "- TARGETED_TEST\n"
    "### ⚠ 금지 사항\n"
    "- no reset\n"
    "### 구현 요약:\n"
    "Modify only context checks. Preserve previous source.\n"
)


class PresentationTests(unittest.TestCase):
    def test_splits_only_recovery_section_for_rich_border(self) -> None:
        parts = split_recovery_response(SAMPLE)
        self.assertIsNotNone(parts)
        assert parts is not None
        self.assertIn("## 작업 복구 분석", parts.before)
        self.assertNotIn(HEADING, parts.before)
        self.assertIn("1. status/read-back", parts.plan)
        self.assertIn("2. preserve existing source", parts.plan)
        self.assertNotIn("> 1.", parts.plan)
        self.assertTrue(parts.after.startswith("---\n### 승인 기준"))
        self.assertEqual(ACCENT, "#FFB347")

    def test_stream_header_uses_amber_and_vertical_rule_only_within_plan(self) -> None:
        h, active = style_stream_line(HEADING, False)
        self.assertTrue(active)
        self.assertIn(ACCENT_ANSI, h)
        self.assertIn("🛠 복구 계획", h)
        body, active = style_stream_line("> 1. Continue Task", active, body_color="\x1b[38;2;255;248;220m")
        self.assertTrue(active)
        self.assertIn("┃", body)
        self.assertIn("Continue Task", body)
        end, active = style_stream_line("---", active)
        self.assertFalse(active)
        self.assertEqual(end, "---")
        ordinary, active = style_stream_line("> Ordinary unrelated quote", active)
        self.assertFalse(active)
        self.assertEqual(ordinary, "> Ordinary unrelated quote")

    def test_reasoning_recovery_fallback_for_actual_plain_heading(self) -> None:
        # Screenshot regression: older agent rendered plain "복구 계획"
        # inside the dim reasoning box, so H2-only normal-response styling missed it.
        untouched, active = style_reasoning_recovery_line("일반 사고 과정", False)
        self.assertEqual((untouched, active), ("일반 사고 과정", False))
        title, active = style_reasoning_recovery_line("복구 계획", active)
        self.assertTrue(active)
        self.assertIn(ACCENT_ANSI, title)
        self.assertIn("🛠 복구 계획", title)
        item, active = style_reasoning_recovery_line(
            "  1. 승인 직후 같은 카드 상태를 재확인합니다.", active)
        self.assertTrue(active)
        self.assertIn("┃", item)
        self.assertIn("같은 카드", item)
        # Regression: the whole plan is accented, including numbered steps,
        # continuation lines and non-numbered nested details.
        for source in (
            "  2. 같은 카드에서 재개합니다.",
            "추가 검증 내용을 확인합니다.",
            "    - 기존 브랜치를 유지합니다.",
            "  3. 회귀 테스트를 수행합니다.",
            "  4. 독립 Reviewer에게 인계합니다.",
        ):
            rendered, active = style_reasoning_recovery_line(source, active)
            self.assertTrue(active)
            self.assertIn("┃", rendered)
            self.assertIn(source.strip(), rendered)
        blank, active = style_reasoning_recovery_line("", active)
        self.assertEqual(blank, "")
        self.assertTrue(active)
        _, active = style_reasoning_recovery_line("승인 기준", active)
        self.assertFalse(active)
        regular, active = style_reasoning_recovery_line("1. 별도 대화", active)
        self.assertEqual((regular, active), ("1. 별도 대화", False))

    def test_change_and_preserve_contracts_have_distinct_accents(self) -> None:
        for presenter in (style_reasoning_recovery_line, style_stream_line):
            with self.subTest(presenter=presenter.__name__):
                heading, state = presenter("### 변경 계약", False)
                self.assertEqual(state, CHANGE_SECTION)
                self.assertIn(ACCENT_ANSI, heading)
                first, state = presenter("1. 기존 기능 범위만 수정", state)
                self.assertIn(BAR_ANSI, first)
                self.assertIn("기존 기능 범위만 수정", first)
                continued, state = presenter("  상세 설명 줄바꿈", state)
                self.assertIn(BAR_ANSI, continued)
                self.assertEqual(state, CHANGE_SECTION)

                heading, state = presenter("### 유지 계약", state)
                self.assertEqual(state, PRESERVE_SECTION)
                self.assertIn(PRESERVE_ANSI, heading)
                body, state = presenter("Workspace 및 Branch 보존", state)
                self.assertIn(PRESERVE_BAR_ANSI, body)
                self.assertIn("Workspace 및 Branch 보존", body)
                empty, state = presenter("", state)
                self.assertEqual(empty, "")
                self.assertEqual(state, PRESERVE_SECTION)
                nested, state = presenter("- 원본 변경 사항 유지", state)
                self.assertIn(PRESERVE_BAR_ANSI, nested)

                heading, state = presenter("복구 계획", state)
                self.assertIn(ACCENT_ANSI, heading)
                self.assertEqual(state, "복구 계획")
                step, state = presenter("1. 복구 작업", state)
                self.assertIn(BAR_ANSI, step)
                unrelated, state = presenter("승인 기준", state)
                self.assertEqual(unrelated, "승인 기준")
                self.assertFalse(state)
                untouched, state = presenter("일반 설명", state)
                self.assertEqual((untouched, state), ("일반 설명", False))

    def test_rich_contract_panels_are_distinct(self) -> None:
        if importlib.util.find_spec("rich") is None:
            self.skipTest("Rich is supplied by Hermes runtime")
        from rich.console import Console
        from io import StringIO

        sample = SAMPLE.replace(
            "### 유지 계약\\n- existing source\\n",
            "### 변경 계약\\n- only scope changes\\n"
            "### 유지 계약\\n- existing source\\n",
        )
        renderable = style_recovery_response(sample)
        output = StringIO()
        Console(file=output, width=100, force_terminal=True, color_system="truecolor").print(renderable)
        visible = output.getvalue()
        self.assertIn("변경 계약", visible)
        self.assertIn("유지 계약", visible)
        self.assertIn("only scope changes", visible)
        self.assertIn("existing source", visible)
        self.assertIn("38;2;34;197;94", visible)

    def test_narrow_terminal_wrap_preserves_number_alignment(self) -> None:
        from devkit_recovery_plan_style import _display_width
        from os import terminal_size

        sentence = "4. 별도 Standard Flow에서 환경 해결 후 원래 UI 카드의 Recovery Flow로 돌아옵니다."
        with patch("devkit_recovery_plan_style.shutil.get_terminal_size", return_value=terminal_size((54, 20))):
            output, state = style_reasoning_recovery_line("복구 계획", False)
            rendered, state = style_reasoning_recovery_line(sentence, state)
            self.assertEqual(state, "복구 계획")
            plain = re.sub(r"\x1b\[[0-9;]*m", "", rendered)
            lines = plain.splitlines()
            self.assertGreater(len(lines), 1)
            self.assertTrue(lines[0].startswith("┃ 4. "))
            self.assertTrue(all(line.startswith("┃    ") for line in lines[1:]))
            self.assertTrue(all(_display_width(line) <= 46 for line in lines))
            self.assertEqual(plain.replace("\n", "").replace("┃", "").replace(" ", ""),
                             sentence.replace(" ", ""))

    def test_contract_body_is_neutral_with_colored_gutter(self) -> None:
        line, active = style_stream_line("변경 계약", False)
        body, active = style_stream_line("긴 계약 내용이 여러 줄에 걸쳐 표시됩니다.", active)
        self.assertIn(BAR_ANSI + "┃", body)
        self.assertIn("계약 내용", body)
        self.assertNotIn(ACCENT_ANSI + "긴", body)
        next_heading, active = style_stream_line("유지 계약", active)
        self.assertIn(PRESERVE_ANSI, next_heading)
        next_body, active = style_stream_line("원본 변경 보존", active)
        self.assertIn(PRESERVE_BAR_ANSI + "┃", next_body)

    def test_durable_machine_contract_does_not_get_reformatted(self) -> None:
        machine = (
            "TASK_RECOVERY_REVISION_V4\n"
            "Recovery Gate: APPROVED\n"
            "Recovery Mode: SAME_TASK_RESUME\n"
            "Recovery Plan:\n- step one\n"
        )
        self.assertIsNone(split_recovery_response(machine))
        self.assertEqual(style_stream_line("Recovery Plan:", False), ("Recovery Plan:", False))
        self.assertIsNone(style_recovery_response(machine))

    def test_code_fences_do_not_trigger_ui_style(self) -> None:
        fence = chr(96) * 3
        example = fence + "markdown\n" + HEADING + "\n> example\n" + fence + "\n"
        self.assertIsNone(split_recovery_response(example))
        self.assertIsNone(split_recovery_response("## 🛠 복구 계획\n---\n"))
        self.assertIsNone(split_recovery_response("### 다른 설명\n"))

    def test_rich_panel_when_available(self) -> None:
        if importlib.util.find_spec("rich") is None:
            self.skipTest("Rich is supplied by Hermes runtime, not every CI host")
        renderable = style_recovery_response(SAMPLE)
        self.assertIsNotNone(renderable)
        self.assertIn("Group", type(renderable).__name__)

    def test_upstream_patch_idempotent_and_fails_closed(self) -> None:
        patcher.self_test()

    def test_gate_remains_user_visible_with_korean_headers(self) -> None:
        skill = (ROOT / "custom-skills/orchestrator/dev-task-recovery/SKILL.md").read_text(encoding="utf-8")
        details = (ROOT / "custom-skills/orchestrator/dev-task-recovery/references/recovery-details.md").read_text(encoding="utf-8")
        required = (
            "RECOVERY_PLAN_PRESENTATION_V1",
            "일반 assistant 응답 영역",
            "Reasoning",
            "## 작업 복구 분석",
            "### 차단 원인",
            "### 원인 분류",
            "### 복구 방식",
            "### 변경 계약",
            "### 유지 계약",
            HEADING,
            "### 승인 기준",
            "### 검증 계획",
            "### ⚠ 금지 사항",
            "### 구현 요약:",
            "RECOVERY_GATE_COUNT=3",
            "TASK_RECOVERY_REVISION_V1",
            "TASK_RECOVERY_ESCALATION_V1",
            "Recovery Mode: SAME_TASK_RESUME",
            "위 복구 계획을 승인할까요?",
        )
        for term in required:
            with self.subTest(term=term):
                self.assertIn(term, skill)
        self.assertIn("위 복구 계획을 승인할까요?", details)
        self.assertIn("영어 key", details)
        self.assertIn("RECOVERY_PLAN_READY", skill)
        self.assertLess(skill.index(HEADING), skill.index("### 구현 요약:"))
        self.assertIn("kanban_unblock", skill)


if __name__ == "__main__":
    unittest.main(verbosity=2)

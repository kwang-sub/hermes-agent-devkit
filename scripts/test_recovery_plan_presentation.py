#!/usr/bin/env python3
"""Contract + read-only render tests for the Recovery Plan Korean preview."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from devkit_recovery_plan_style import (
    ACCENT, ACCENT_ANSI, HEADING, split_recovery_response,
    style_recovery_response, style_stream_line, style_reasoning_recovery_line,
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
        _, active = style_reasoning_recovery_line("승인 기준", active)
        self.assertFalse(active)
        regular, active = style_reasoning_recovery_line("1. 별도 대화", active)
        self.assertEqual((regular, active), ("1. 별도 대화", False))

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

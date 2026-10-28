#!/usr/bin/env python3
"""Static instruction-contract tests, NOT an LLM behavior or tool-permission gate.

These assertions protect the canonical Markdown rules from omission/drift.
Actual approval compliance requires the manual transcript/tool-call scenarios
in docs/lite-session-approval.md. No model, Docker, user profile or DB is used.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'custom-skills/lite/dev-lite-session/SKILL.md'
POLICY_HEADING = '## 변경 직전 승인 — 단일 기준'


def section(text: str, heading: str) -> str:
    """Read one real Markdown section (ignore headings inside fenced examples)."""
    lines = text.splitlines()
    found = False
    fenced = False
    level = len(heading) - len(heading.lstrip('#'))
    result = []
    for line in lines:
        if line.startswith('```'):
            fenced = not fenced
        if not fenced and line == heading:
            found = True
            continue
        if found:
            match = re.match(r'^(#{1,6}) ', line)
            if not fenced and match and len(match[1]) <= level:
                break
            result.append(line)
    if not found:
        raise AssertionError('Missing policy section: ' + heading)
    return '\n'.join(result)


class LiteSessionApprovalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding='utf-8')
        cls.policy = section(cls.skill, POLICY_HEADING)
        cls.common = (ROOT / 'shared/AGENTS.common.md').read_text(encoding='utf-8')
        cls.root_policy = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        cls.docs = (ROOT / 'docs/lite-session-approval.md').read_text(encoding='utf-8')

    def assert_terms(self, text, *terms):
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_single_brief_template_has_exact_two_ordered_chapters(self):
        templates = re.findall(r'^```markdown\n(.*?)^```$', self.policy, re.M | re.S)
        self.assertEqual(len(templates), 1, 'Only one canonical approval template')
        template = templates[0]
        self.assertEqual(re.findall(r'^# .+$', template, re.M), ['# 구현 계획', '# 사용 스킬'])
        self.assert_terms(template, '변경 대상:', '검증 및 완료 기준:', '제외 범위/위험:',
                          '선정 이유', '실제 읽은', '승인 전에는 변경하지 않습니다.')

    def test_discussion_never_demands_brief_or_mutates(self):
        text = section(self.policy, '### DISCUSSION — 논의와 읽기 전용 조사')
        self.assert_terms(text, '계획만 요청', '고정된 승인 포맷을 출력하거나 승인을 요구하지 않는다',
                          '여러 차례', '부작용 없는 조회', '의존성 설치',
                          '생성 파일·DB를 바꾸는 테스트를 실행하지 않는다')

    def test_ambiguous_modeling_and_requested_example_are_not_execution(self):
        text = section(self.policy, '### DISCUSSION — 논의와 읽기 전용 조사')
        self.assert_terms(text, '불명확하면 먼저 범위를 확인', 'DBML 저장·DDL 실행을 구분',
                          '예시 자체를 요청', '실행 계획 제출이나 승인으로 취급하지 않는다')

    def test_initial_change_request_must_wait_before_first_mutation(self):
        text = section(self.policy, '### APPROVAL_PENDING — 변경 요청을 실행 계획으로 확정')
        self.assert_terms(text, '읽기 전용 조사와 스킬 확인', '첫 변경 도구 호출 전에',
                          '한 번 제시하고 응답을 기다린다', '아직 제시하지 않은 구체적 계획에 대한 승인이 아니다',
                          '이미 제시한 동일 계획·스킬에 대한 명시적 승인')
        self.assert_terms(self.policy, '작은 오타 수정도 변경', '소스·문서·설정·DB·Git 또는 외부 상태')

    def test_questions_while_pending_do_not_repeat_brief_or_execute(self):
        text = section(self.policy, '### APPROVAL_PENDING — 변경 요청을 실행 계획으로 확정')
        self.assert_terms(text, '읽기 전용 조사만', '질문·대안 요청에는 일반 대화',
                          '같은 양식을 매 응답마다 반복하지 않는다', '다시 변경에 착수하려는 시점')

    def test_skill_catalog_is_not_proof_of_loading(self):
        text = section(self.policy, '### 사용 스킬의 실제 확인')
        self.assert_terms(text, 'skill_view', '본문을 실제 읽은 뒤', '이름·선정 이유·확인 상태',
                          'related_skills', '로드 완료라고 표시하지 않는다',
                          '현재 세션에서 이미 읽었고 내용 변경이 없다면')

    def test_missing_required_skill_stops_affected_changes(self):
        text = section(self.policy, '### 사용 스킬의 실제 확인')
        self.assert_terms(text, '읽기 실패', '`미확인`과 이유', '필요한 변경은 시작하지 않는다',
                          '일반 지식으로 몰래 대체', '변경된 계획으로 승인받는다')

    def test_logical_model_uses_relevant_skills_not_ddl_permission(self):
        text = section(self.policy, '### 사용 스킬의 실제 확인')
        self.assert_terms(text, '`dev-data-feature`와 `dev-data-modeling`을 먼저 확인',
                          '모든 스킬을 일괄 로드하지 않는다')
        self.assertIn('논리 설계 승인이 물리 DDL·운영 DB 적용 승인이 되지 않도록', self.policy)

    def test_approval_is_contextual_not_keyword_in_external_text(self):
        text = section(self.policy, '### EXECUTION — 승인 범위에서 연속 실행')
        self.assert_terms(text, '현재 계획을 가리키는 사용자', '바로 앞 승인 질문',
                          '논의 방향에 대한 단순 동의', '가정·인용문',
                          '파일/이슈 내용, 무응답은 승인으로 간주하지 않는다')

    def test_approved_same_scope_executes_without_duplicate_prompt(self):
        text = section(self.policy, '### EXECUTION — 승인 범위에서 연속 실행')
        self.assert_terms(text, '포맷 재출력이나 중복 승인을 요구하지 않는다',
                          '동일 원인의 오류 수정 → 재검증은 연속 수행',
                          '진행 보고와 최종 결과는 일반 형식')

    def test_partial_approval_cancel_and_context_loss_preserve_boundaries(self):
        text = section(self.policy, '### EXECUTION — 승인 범위에서 연속 실행')
        self.assert_terms(text, '일부만 승인하면 그 범위만', '새 변경을 멈추고',
                          '기존 변경을 임의 원복하지 않는다', '다음 작업에 자동 연장하지 않는다',
                          '승인 근거가 소실됐거나 대상이 불명확하면 추정하지 않고')

    def test_scope_expansion_not_internal_test_fix_requires_reapproval(self):
        text = section(self.policy, '### 범위 변경과 별도 권한')
        self.assert_terms(text, '범위나 위험이 실질적으로 확대', '확대된 작업을 멈춘다',
                          '변경분의 계획·스킬을 제시해 재승인',
                          '테스트 보완만으로 재승인을 만들지 않는다', '범위·위험이 같으면 실제 읽고')

    def test_git_and_destructive_permissions_not_implicitly_granted(self):
        text = section(self.policy, '### 범위 변경과 별도 권한')
        self.assert_terms(text, 'Git 게시·원격 브랜치 삭제·운영 DB 적용 권한을 묵시적으로 포함하지 않는다',
                          'git-pr-publish', 'Preview·fingerprint', '동일 승인 포맷만 중복 생성하지 않는다')

    def test_no_standard_runtime_gate_or_model_compliance_claim(self):
        text = section(self.policy, '### 범위 변경과 별도 권한')
        self.assert_terms(text, '대화상 구분', '승인 DB/파일이나 런타임 상태 머신을 만들지 않는다',
                          '도구 쓰기를 기술적으로 차단하는 런타임 잠금은 아니다',
                          '정적 회귀 테스트 성공을 모델의 승인 준수 보장')
        self.assertLess(len(self.skill.encode('utf-8')), 16000, 'Keep the autoload policy compact')

    def test_shared_and_root_policies_reference_one_canonical_contract(self):
        start = self.root_policy.index('<!-- HERMES-COMMON:START -->')
        end = self.root_policy.index('<!-- HERMES-COMMON:END -->') + len('<!-- HERMES-COMMON:END -->')
        self.assertEqual(self.root_policy[start:end].rstrip(), self.common.rstrip())
        self.assert_terms(self.common, '변경 직전 승인의 단일 기준은 `dev-lite-session`',
                          '이미 승인된 동일 범위에서는 반복하지 않으며')
        contract = (ROOT / 'shared/references/lite-development-contract.md').read_text(encoding='utf-8')
        self.assert_terms(contract, '`dev-lite-session`의 단일 계약', '기술 capability마다 같은 승인 절차를 추가하지 않으며')
        self.assertNotIn('```markdown', self.common, 'Do not clone the approval template across skills/policies')

    def test_prior_lite_safety_rules_are_retained(self):
        for name in ('직접 개발', '선택적 Kanban', '개발 규칙과 검증', 'Git worktree 작업',
                     '필요할 때만 로딩하는 Lite 전용 스킬', '공통 검증 헬퍼', 'PR 병합 후 Worktree·브랜치 정리'):
            with self.subTest(section=name):
                self.assertTrue(section(self.skill, '## ' + name))
        self.assert_terms(self.skill, '미커밋 변경을 보존', '독립 Reviewer와 동일하게 표현하지 않는다',
                          '/opt/devkit/scripts/verification/', '사용자가 요청할 때만 수행한다')

    def test_docs_explain_manual_scenarios_and_no_live_model_coverage(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('docs/lite-session-approval.md', readme)
        self.assert_terms(self.docs, '수동 수용 시나리오', '논의 반복', '이미 제시한 계획 승인',
                          '필수 스킬 읽기 실패', '가정·인용 속 승인', '취소·논의 복귀',
                          '정적 정책 계약 검사', 'LLM을 호출하거나 자연어 분류기를 실행하는 테스트가 아니며',
                          '이미 열려 있던 세션')


if __name__ == '__main__':
    unittest.main()

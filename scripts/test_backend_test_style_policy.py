#!/usr/bin/env python3
"""Static policy/link checks, not a classifier, model test or test-engine runner."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'shared/references/backend-test-style-policy.md'
POLICY_LINK = '/opt/data/shared/references/backend-test-style-policy.md'


def section(text: str, heading: str) -> str:
    """Read a policy section without matching a later section's protections."""
    marker = '## ' + heading + '\n'
    if text.count(marker) != 1:
        raise AssertionError('Expected one policy section: ' + heading)
    return text.split(marker, 1)[1].split('\n## ', 1)[0]


class BackendTestStylePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = POLICY_PATH.read_text(encoding='utf-8')

    def assert_terms(self, text: str, *terms: str) -> None:
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_scoped_policy_and_single_canonical_marker(self):
        self.assertEqual(self.policy.count('BACKEND_TEST_STYLE_POLICY_V1'), 1)
        self.assert_terms(self.policy, '백엔드 테스트를 작성하거나 수정할 때만',
                          'BehaviorSpec도 Given–When–Then')

    def test_existing_files_and_explicit_project_rules_are_preserved(self):
        text = section(self.policy, '적용 순서와 기존 코드 보존')
        self.assert_terms(text, '명시적 사용자 지시', '기존 스타일을 유지한다',
                          '관계없는 테스트를 일괄 전환하지 않는다',
                          '명시적 테스트 규격', '새 파일을 만들어',
                          '파일명·fixture·assertion 관례도 유지한다')

    def test_classification_uses_asserted_contract_not_class_layer(self):
        text = section(self.policy, '검증 대상에 따른 선택')
        self.assert_terms(text, '클래스 이름이나 계층이 아니라', '기대 결과',
                          '업무 조건', '기술적 결과', '검증 책임별로',
                          '분류가 모호하고', '기존 스타일 또는 단순한 Given–When–Then')

    def test_default_matrix_keeps_framework_specific_names(self):
        text = section(self.policy, '검증 대상에 따른 선택')
        rows = [line for line in text.splitlines() if line.startswith('|')][2:]
        self.assertEqual(len(rows), 5)
        for row, terms in zip(rows, (
            ('비즈니스', 'Kotlin + Kotest', 'BehaviorSpec'),
            ('비즈니스', 'JUnit Jupiter', '@Nested', 'Given–When–Then'),
            ('일반 기술', 'Kotlin + Kotest', 'FunSpec', 'Given–When–Then'),
            ('일반 기술', 'JUnit Jupiter', '@Test', 'Given–When–Then'),
            ('JUnit 4·기타 엔진', '지원하는 기존 스타일'),
        )):
            self.assert_terms(row, *terms)
        self.assertIn('JUnit의 시나리오형을 BehaviorSpec이라고 부르지 않는다', text)

    def test_missing_tools_do_not_trigger_install_or_fake_support(self):
        text = section(self.policy, '적용 순서와 기존 코드 보존')
        self.assert_terms(text, '지원 여부를 확인하지 못했으면',
                          '사용할 수 있다고 보고하지 않는다', '미실행',
                          '자동 추가·교체·업그레이드하지 않는다')

    def test_nesting_is_not_a_mandatory_shape(self):
        text = section(self.policy, '검증 대상에 따른 선택')
        self.assert_terms(text, '중첩은 조건별 차이', '의미 없는 @Nested 계층을 만들지 않는다',
                          '기존 BehaviorSpec 파일', '파일의 스타일을 유지한다')

    def test_tests_are_independent_without_engine_changes(self):
        text = section(self.policy, '작성 품질과 실행 범위')
        self.assert_terms(text, '변경 가능한 객체·Mock·DB', '실행 순서에 의존하지 않게',
                          '단독 실행', '독립적으로 준비', '격리 모드를 임의로 변경하지 않는다',
                          'when & then', '관련된 여러 assertion은 허용한다')

    def test_style_does_not_replace_test_scope_or_display_name_policy(self):
        text = section(self.policy, '작성 품질과 실행 범위')
        self.assert_terms(text, '작성 스타일과 단위·통합 테스트 선택은 별개',
                          '@SpringBootTest를 강제하지 않으며', 'Mock만으로',
                          'verification-level-policy.md', 'jvm-test-display-name-policy.md',
                          'Kotest에는 DSL의 한글 설명')
        for filename in ('verification-level-policy.md', 'jvm-test-display-name-policy.md'):
            self.assertTrue((POLICY_PATH.parent / filename).is_file())

    def test_notice_is_one_line_in_existing_plan_without_extra_approval(self):
        text = section(self.policy, '사용자에게 알리는 범위')
        self.assert_terms(text, '기존 구현 계획의 검증 항목', '한 줄로 한 번만',
                          '실제 도구와 선택한 형태만', '같은 줄에 대상별로',
                          '기존 스타일 유지', '선택창·추가 승인·새 챕터를 만들지 않는다',
                          '실행·재시도마다 반복하지 않는다')

    def test_notice_does_not_hide_results_or_apply_to_execution_only(self):
        text = section(self.policy, '사용자에게 알리는 범위')
        self.assert_terms(text, '스타일이 바뀌면', '의존성이나 작업 범위',
                          '작성·수정하지 않는 단순 실행', '이 안내를 강제하지 않는다',
                          '기존 구현 계획·사용 스킬 안내·승인 절차를 생략하지 않는다',
                          '실제 실행 명령', '통과·실패·미실행 사유·잔여 위험')

    def test_policy_adds_no_embedded_samples_or_runtime_gate(self):
        text = section(self.policy, '정책만 유지')
        self.assert_terms(text, '샘플 코드·샘플 테스트 프로젝트·복사용 템플릿·공통 테스트 부모 클래스',
                          '추가하지 않는다', '기존 참고 샘플은 삭제하거나',
                          '필요한 테스트 코드를 작성한다', '정적 검사', '보장하지 않는다',
                          '런타임 차단 장치는 추가하지 않는다')
        self.assertNotRegex(self.policy, r'(?m)^\s*(`{3,}|~{3,})')
        self.assertFalse((POLICY_PATH.parent / 'backend-test-style-samples').exists())

    def test_session_spring_and_review_read_same_existing_reference(self):
        for path in ('custom-skills/core/dev-session/SKILL.md',
                     'custom-skills/shared/dev-spring-test/SKILL.md',
                     'custom-skills/core/dev-review/SKILL.md'):
            text = (ROOT / path).read_text(encoding='utf-8')
            with self.subTest(path=path):
                self.assertIn(POLICY_LINK, text)
                self.assertNotIn('BACKEND_TEST_STYLE_POLICY_V1', text)
                resolved = ROOT / POLICY_LINK.removeprefix('/opt/data/')
                self.assertEqual(resolved, POLICY_PATH)
                self.assertTrue(resolved.is_file())

    def test_approval_template_and_automatic_test_discovery_remain(self):
        session = (ROOT / 'custom-skills/core/dev-session/SKILL.md').read_text(encoding='utf-8')
        templates = re.findall(r'^```markdown\n(.*?)^```$', session, re.M | re.S)
        self.assertEqual(len(templates), 1)
        self.assertEqual(re.findall(r'^# .+$', templates[0], re.M), ['# 구현 계획', '# 사용 스킬'])
        self.assertIn('테스트 스타일만 한 줄로 안내', session)
        runner = (ROOT / 'scripts/run_regression_tests.py').read_text(encoding='utf-8')
        self.assertIn("ROOT.glob('scripts/test_*.py')", runner)
        self.assertIn('run_regression_tests.py', (ROOT / 'scripts/verify.sh').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

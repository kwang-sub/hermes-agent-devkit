#!/usr/bin/env python3
"""Static policy/link/example checks; not a JUnit engine or LLM behavior test."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'shared/references/jvm-test-display-name-policy.md'


class JvmDisplayNamePolicyTests(unittest.TestCase):
    def setUp(self):self.policy=POLICY.read_text(encoding='utf-8')

    def test_required_korean_names_cover_java_and_kotlin(self):
        for term in ('JVM_KOREAN_DISPLAY_NAME_V1','한글 표시명 필수','Java와 Kotlin','Spring 사용 여부와 무관',
                     '신규/변경 테스트 메서드','기존 영어 표시명 관례만을 이유로 생략하지 않는다'):
            self.assertIn(term,self.policy)

    def test_parameterized_repeated_and_dynamic_names(self):
        for term in ('@ParameterizedTest','@RepeatedTest','@TestTemplate','@TestFactory','DynamicTest','DynamicContainer','{displayName}'):
            self.assertIn(term,self.policy)

    def test_existing_engine_and_unrelated_tests_preserved(self):
        for term in ('JUnit 4','미지원','임의 업그레이드하지 않는다','관계없는 기존 테스트','Kotest'):
            self.assertIn(term,self.policy)

    def test_backticks_and_generator_are_not_a_substitute(self):
        self.assertIn('`@DisplayNameGeneration`만으로',self.policy)
        self.assertIn('backtick 메서드명',self.policy)

    def test_java_and_kotlin_examples_use_korean_annotations(self):
        for language in ('java','kotlin'):
            example=re.search(r'```'+language+r'\n(.*?)\n```',self.policy,re.S).group(1)
            self.assertIn('org.junit.jupiter.api.DisplayName',example)
            self.assertEqual(len(re.findall(r'@DisplayName\("[^"]*[가-힣][^"]*"\)',example)),2)
            self.assertIn('usesDefaultWhenEmpty',example)

    def test_skills_route_to_single_policy(self):
        for skill in ('dev-java-guidelines','dev-kotlin-guidelines','dev-spring-test'):
            s=(ROOT/f'custom-skills/shared/{skill}/SKILL.md').read_text()
            self.assertIn('/opt/data/shared/references/jvm-test-display-name-policy.md',s)
            self.assertIn('@DisplayName("한글 설명")',s)
            self.assertIn('반드시',s)

    def test_common_and_self_review_enforce_rule(self):
        for path in ('shared/references/coding-rules.md','custom-skills/lite/dev-lite-review/SKILL.md'):
            s=(ROOT/path).read_text();self.assertIn('jvm-test-display-name-policy.md',s);self.assertIn('@DisplayName',s)

    def test_bundled_kotlin_reference_tests_have_explicit_korean_display_names(self):
        """Check the four bounded sample classes, not arbitrary user repositories."""
        folder = ROOT/'shared/references/samples/spring/kotlin/src/test/kotlin/com/example/samples'
        total = 0
        files = sorted(folder.glob('*Test.kt'))
        self.assertEqual(len(files), 4)
        for path in files:
            content = path.read_text(encoding='utf-8')
            with self.subTest(class_name=path.stem):
                self.assertIn('import org.junit.jupiter.api.DisplayName', content)
                self.assertRegex(content, r'@DisplayName\("[^"\n]*[가-힣][^"\n]*"\)\s*class\s+' + path.stem)
                matches = re.findall(
                    r'(?m)^\s*@Test\s*\n\s*@DisplayName\("[^"\n]*[가-힣][^"\n]*"\)\s*\n\s*fun\s+',
                    content,
                )
                self.assertEqual(len(matches), len(re.findall(r'(?m)^\s*@Test\b', content)))
                total += len(matches)
        self.assertEqual(total, 22)

    def test_test_labels_do_not_override_english_logs_or_leak_secrets(self):
        for term in ('코드 운영 로그 영어 작성','password/token/PII','UTF-8','실제 테스트 실행 성공을 대신하지 않는다'):
            self.assertIn(term,self.policy)


if __name__=='__main__':unittest.main()

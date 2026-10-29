#!/usr/bin/env python3
"""Policy and bundled-sample checks only, not a scanner for user repositories."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
POLICY='shared/references/junit-display-name-policy.md'


class JUnitDisplayNameTests(unittest.TestCase):
    def test_canonical_scope_and_compatibility(self):
        text=(ROOT/POLICY).read_text(encoding='utf-8')
        for token in ('JUNIT_KOREAN_DISPLAY_NAME_V1','한글','반드시','@DisplayName',
                      'JUnit 4','자동 업그레이드하지 않는다','운영 로그',
                      '@ParameterizedTest','@RepeatedTest','@TestFactory','@TestTemplate',
                      'DynamicTest.dynamicTest','@Nested','@BeforeEach','{displayName}',
                      'org.junit.jupiter.api.DisplayName','Kotlin 백틱'):
            with self.subTest(token=token): self.assertIn(token,text)

    def test_language_test_and_review_skills_link_policy(self):
        for path in ('custom-skills/shared/dev-java-guidelines/SKILL.md',
                     'custom-skills/shared/dev-kotlin-guidelines/SKILL.md',
                     'custom-skills/shared/dev-spring-test/SKILL.md',
                     'custom-skills/lite/dev-lite-review/SKILL.md'):
            with self.subTest(path=path):
                text=(ROOT/path).read_text(encoding='utf-8')
                self.assertIn('junit-display-name-policy.md',text)
                self.assertIn('한글',text);self.assertIn('@DisplayName',text)
                self.assertIn('JUNIT_KOREAN_DISPLAY_NAME_V1',text)

    def test_all_bundled_jupiter_cases_have_explicit_korean_display_names(self):
        folder=ROOT/'shared/references/samples/spring/kotlin/src/test/kotlin/com/example/samples'
        count=0
        # Deliberately bounded to the documented sample's simple declarations.
        # This is not a Java/Kotlin parser and must not be advertised as one.
        for path in sorted(folder.glob('*Test.kt')):
            text=path.read_text(encoding='utf-8')
            with self.subTest(path=path.name):
                self.assertIn('import org.junit.jupiter.api.DisplayName',text)
                self.assertRegex(text, r'@DisplayName\("[^"\n]*[가-힣][^"\n]*"\)\s*class '+path.stem)
                cases=list(re.finditer(r'@Test\b([\s\S]*?)\bfun\s+`([^`]+)`',text))
                self.assertTrue(cases)
                for case in cases:
                    with self.subTest(case=case[2]):
                        self.assertRegex(case[1],r'@DisplayName\("[^"\n]*[가-힣][^"\n]*"\)')
                        count+=1
        self.assertGreaterEqual(count,22)


if __name__=='__main__': unittest.main()

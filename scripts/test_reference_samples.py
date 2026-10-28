#!/usr/bin/env python3
"""Static sample/routing contracts only. Kotlin execution is a separate Maven CI job."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'shared/references/samples/spring'
MAIN = SAMPLES / 'kotlin/src/main/kotlin/com/example/samples'

class ReferenceSampleContractTest(unittest.TestCase):
    def text(self, path):
        return path.read_text(encoding='utf-8')

    def test_catalog_and_docs_are_local(self):
        for name in ('README.md', 'ADAPTATION.md', 'compatibility.md', 'SOURCE.md', 'crypto-jpa.md', 'error-handling.md', 'openapi.md'):
            self.assertTrue((SAMPLES / name).is_file(), name)
        for path in SAMPLES.glob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)', self.text(path)):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((path.parent / link.split('#')[0]).exists(), f'{path}: {link}')

    def test_existing_project_and_language_adaptation_are_explicit(self):
        text = self.text(SAMPLES / 'ADAPTATION.md')
        for term in ('기존 프로젝트 우선', 'Java', 'Python', '클래스 개수', '대상 언어', '자동 복사하지 않는다', '응답', '암호문', '실행 검증/미검증'):
            self.assertIn(term, text)
        self.assertIn('samples/README.md', self.text(ROOT / 'shared/references/project-pattern-rules.md'))

    def test_skills_select_samples_without_forcing_all_loading(self):
        for skill in ('dev-spring-data', 'dev-spring-feature', 'dev-spring-test', 'dev-api-docs'):
            text = self.text(ROOT / 'custom-skills/shared' / skill / 'SKILL.md')
            for term in ('samples/spring/README.md', '기존 프로젝트', 'Java/Python', '실제', '자동', '복사'):
                self.assertIn(term, text, f'{skill}: {term}')
        for skill, name in (('dev-spring-data', 'jpa-converter-reference.md'),
                            ('dev-spring-feature', 'exception-handling-reference.md'),
                            ('dev-api-docs', 'spring-openapi-reference.md')):
            self.assertTrue((ROOT / 'custom-skills/shared' / skill / 'references' / name).is_file())

    def test_samples_are_not_new_auto_loaded_skills(self):
        self.assertEqual([], list(SAMPLES.rglob('SKILL.md')))
        session = self.text(ROOT / 'custom-skills/lite/dev-lite-session/SKILL.md')
        self.assertNotIn('samples/spring/kotlin', session)
        self.assertNotIn('samples/spring', self.text(ROOT / 'scripts/lite_default_profile.py'))

    def test_source_provenance_and_known_limitations(self):
        source = self.text(SAMPLES / 'SOURCE.md')
        self.assertIn('432b29df219783eac8cfad4aa1f0ca46bc9c4fa6', source)
        self.assertIn('kwang-sub/level-up-backend-gpt', source)
        self.assertIn('원본 저장소는 수정하지 않았다', source)
        compatibility = self.text(SAMPLES / 'compatibility.md')
        self.assertIn('운영 배포 권장 버전 목록이 아니다', compatibility)
        self.assertIn('Java/Python', compatibility)

    def test_neutral_package_no_original_business_or_contact_in_source(self):
        files = list(MAIN.rglob('*.kt'))
        self.assertGreaterEqual(len(files), 14)
        for path in files:
            text = self.text(path)
            self.assertTrue(text.startswith('package com.example.samples.'), str(path))
            for forbidden in ('BookController', 'level2bookmanagementsystem', '@gmail.com', 'OUT_OF_STOCK', 'ALREADY_LOANED_BOOK'):
                self.assertNotIn(forbidden, text, str(path))

    def test_crypto_boundaries_and_no_hash_converter(self):
        converter = self.text(MAIN / 'crypto/EncryptedStringConverter.kt')
        self.assertIn('@Converter(autoApply = false)', converter)
        self.assertIn('attribute?.let', converter)
        self.assertIn('dbData?.let', converter)
        self.assertEqual([], list(MAIN.rglob('*HashConverter*')))
        hasher = self.text(MAIN / 'crypto/Argon2Hasher.kt')
        self.assertEqual(2, hasher.count('finally'))
        self.assertNotIn('return attribute', hasher)
        config = self.text(MAIN / 'example/SampleConfiguration.kt')
        self.assertIn('sample.crypto.key-base64}', config)
        self.assertNotIn('sample.crypto.key-base64:', config)

    def test_sample_versions_are_isolated_from_devkit_build(self):
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
        pom = ET.parse(SAMPLES / 'kotlin/pom.xml')
        self.assertEqual('17', pom.findtext('m:properties/m:java.version', namespaces=ns))
        self.assertEqual('${sample.build.directory}', pom.findtext('m:build/m:directory', namespaces=ns))
        workflow = self.text(ROOT / '.github/workflows/reference-samples.yml')
        self.assertIn('sample.build.directory', workflow)
        self.assertIn('generated-openapi.json', workflow)
        self.assertNotIn('-DskipTests', workflow)

    def test_runtime_tests_cover_persistence_and_actual_generated_document(self):
        tests = SAMPLES / 'kotlin/src/test/kotlin/com/example/samples'
        self.assertIn('entityManager.clear()', self.text(tests / 'JpaConverterTest.kt'))
        self.assertIn('createNativeQuery', self.text(tests / 'JpaConverterTest.kt'))
        api = self.text(tests / 'ErrorAndOpenApiIntegrationTest.kt')
        self.assertIn('/v3/api-docs', api)
        self.assertIn('OpenAPIV3Parser', api)
        self.assertIn('isMethodNotAllowed', api)
        merge = self.text(tests / 'OpenApiMergeTest.kt')
        self.assertIn('ExistingWrapper', merge)
        self.assertIn('application/problem+json', merge)
        self.assertIn('assertSame', merge)

if __name__ == '__main__':
    unittest.main()

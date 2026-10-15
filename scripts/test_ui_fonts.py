#!/usr/bin/env python3
"""Pure unit checks for the opt-in Korean browser font capability."""
from pathlib import Path
import unittest

from ui_runtime.fonts import korean_font_evidence, probe_korean_font
from ui_runtime.smoke import HTML
from ui_runtime.suite import EnvironmentBlocked


class FontCapabilityTests(unittest.TestCase):
    def test_smoke_fixture_is_real_utf8_hangul(self):
        self.assertIn('가나다 한글 화면 검증', HTML.decode('utf-8'))
        self.assertIn('font-family:', HTML.decode('utf-8'))

    def test_report_requires_actual_korean_glyphs(self):
        ok = korean_font_evidence([{'familyName': 'Noto Sans CJK KR', 'glyphCount': 7}])
        self.assertEqual(ok['status'], 'PASS')
        for fonts in ([], [{'familyName': 'DejaVu Sans', 'glyphCount': 7}],
                      [{'familyName': 'Noto Sans CJK KR', 'glyphCount': 0}], None):
            with self.assertRaises(EnvironmentBlocked):
                korean_font_evidence(fonts)

    def test_uses_cdp_platform_font_observation(self):
        class Page:
            def __init__(self):
                self.calls = []
            def evaluate(self, expression):
                return "가나다" in expression and "#ko-font" in expression
            def call(self, method, params=None):
                self.calls.append(method)
                return {'root': {'nodeId': 1}} if method == 'DOM.getDocument' else (
                    {'nodeId': 2} if method == 'DOM.querySelector' else (
                    {'fonts': [{'familyName': 'Noto Sans CJK KR', 'glyphCount': 5}]} if method == 'CSS.getPlatformFontsForNode' else {}))
        page = Page()
        self.assertEqual(probe_korean_font(page, '#ko-font', '가나다')['status'], 'PASS')
        self.assertIn('CSS.getPlatformFontsForNode', page.calls)

    def test_docker_image_and_managed_smoke_have_font_check(self):
        docker = (Path(__file__).resolve().parents[1] / 'Dockerfile').read_text()
        self.assertIn('FROM hermes-upstream-patched AS hermes-ui-smoke\nUSER root', docker)
        self.assertGreaterEqual(docker.count('fonts-noto-cjk'), 2)
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/ui-verification.yml').read_text()
        self.assertIn('--features korean-font,upload,download,popup,frame', workflow)


if __name__ == '__main__':
    unittest.main()

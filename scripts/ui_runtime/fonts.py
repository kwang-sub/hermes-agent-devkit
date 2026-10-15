"""Evidence that managed Chromium actually used Korean glyphs in a fixture.

The check is opt-in and environment-only: PASS is not design conformance.
"""
from __future__ import annotations

import json

from .suite import EnvironmentBlocked


def korean_font_evidence(fonts: list[dict]) -> dict:
    """Require rendered Hangul glyphs from the Noto CJK family shipped by DevKit."""
    if not isinstance(fonts, list):
        raise EnvironmentBlocked('Korean font observation is unavailable')
    matching = [item.get('familyName', '') for item in fonts
                if isinstance(item, dict)
                and isinstance(item.get('familyName'), str)
                and item['familyName'].startswith('Noto Sans CJK')
                and isinstance(item.get('glyphCount'), int)
                and item['glyphCount'] >= 3]
    if not matching:
        raise EnvironmentBlocked('Korean glyphs were not rendered with installed Noto CJK fonts')
    return {'status': 'PASS',
            'evidence': 'Managed Chromium reported rendered Korean glyphs from Noto Sans CJK',
            'rendered_font_families': sorted(set(matching)),
            'scope': 'browser font capability, not screenshot readability or product design approval'}


def probe_korean_font(page, selector: str, expected_text: str) -> dict:
    if not selector or not expected_text:
        raise ValueError('Korean font probe requires a fixture selector and sample')
    selector_js = json.dumps(selector, ensure_ascii=False)
    text_js = json.dumps(expected_text, ensure_ascii=False)
    if not page.evaluate('!!document.querySelector(' + selector_js + ') && '
                         'document.querySelector(' + selector_js + ').textContent.includes(' + text_js + ')'):
        raise EnvironmentBlocked('Korean fixture text is unavailable')
    page.call('DOM.enable')
    page.call('CSS.enable')
    root = page.call('DOM.getDocument')['root']['nodeId']
    node = page.call('DOM.querySelector', {'nodeId': root, 'selector': selector}).get('nodeId')
    if not node:
        raise EnvironmentBlocked('Korean fixture node was not found')
    fonts = page.call('CSS.getPlatformFontsForNode', {'nodeId': node}).get('fonts')
    return korean_font_evidence(fonts)

#!/usr/bin/env python3
"""Reject retired active names; preserve explicit compatibility and theme terms."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RETIRED = re.compile(r'(?<![A-Za-z])lite(?![A-Za-z])|라이트', re.I)
TEXT_SUFFIXES = {'.md', '.py', '.ps1', '.sh', '.yml', '.yaml', '.json'}
# Frozen inputs and old-state readers must retain the exact old names.
COMPATIBILITY = {
    'scripts/devkit_default_profile.py', 'scripts/devkit_image_fixture.py',
    'scripts/test_devkit_naming_migration.py', 'scripts/test_devkit_naming_contract.py',
    'scripts/check_devkit_naming.py', 'docs/naming-migration.md',
}
WIRE_FILES = {'scripts/devkit_approval_ui.py', 'scripts/patch_hermes_approval_ui.py'}
THEME_FILES = {'custom-skills/core/dev-session/SKILL.md', 'docs/session-approval.md'}


def violations(root: Path) -> list[str]:
    problems = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if '.git' in relative.parts or '__pycache__' in relative.parts or not path.is_file():
            continue
        name = relative.as_posix()
        if RETIRED.search(name):
            problems.append('Retired active path: ' + name)
        if name in COMPATIBILITY or path.suffix not in TEXT_SUFFIXES:
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if name in WIRE_FILES:
                line = line.replace('lite_change_approval_v1', '')
            if name in THEME_FILES:
                line = line.replace('라이트 모드', '')
            if name == 'scripts/check_update_devkit_contract.py':
                for old in ('updatekit_lite.sh', 'updatekit_lite.ps1', 'init-lite.ps1'):
                    line = line.replace(old, '')
            if RETIRED.search(line):
                problems.append(f'Retired active name: {name}:{number}')
    return problems


def main():
    problems = violations(ROOT)
    if problems:
        raise SystemExit('\n'.join(problems))
    print('[PASS] Neutral DevKit names; compatibility and theme terms are scoped')


if __name__ == '__main__':
    main()

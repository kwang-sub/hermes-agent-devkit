#!/usr/bin/env python3
"""Naming/boot-reference regressions, not assertions about model behavior."""
from pathlib import Path
import tempfile
import unittest
import check_devkit_naming as naming

ROOT = Path(__file__).resolve().parents[1]


class NamingContractTests(unittest.TestCase):
    def test_active_skills_use_core_and_new_identities(self):
        self.assertFalse((ROOT / 'custom-skills/lite').exists())
        for name in ('dev-session', 'dev-review'):
            path = ROOT / 'custom-skills/core' / name / 'SKILL.md'
            self.assertIn('name: ' + name, path.read_text())
        self.assertFalse((ROOT / 'scripts/init-lite.ps1').exists())
        self.assertFalse((ROOT / 'scripts/lite_default_profile.py').exists())

    def test_boot_and_runtime_checks_reference_same_names(self):
        init = (ROOT / 'docker/cont-init.d/018-devkit-init').read_text()
        self.assertIn('/run/devkit-ready', init)
        self.assertIn('/opt/devkit/bin/devkit_default_profile.py', init)
        for name in ('02-devkit-reconcile-guard', '019-devkit-kanban-notifier-policy'):
            self.assertIn('/run/devkit-ready', (ROOT / 'docker/cont-init.d' / name).read_text())
        runtime = (ROOT / 'scripts/verify-container-runtime.ps1').read_text()
        self.assertIn('root/"core"', runtime)
        self.assertIn('root / "core"', runtime)
        self.assertNotIn('$DefaultLiteCheck', runtime)
        metadata = (ROOT / '.hermes/project.yaml').read_text()
        self.assertIn('- scripts/init-devkit.ps1', metadata)

    def test_runtime_preflight_is_self_contained_for_old_image(self):
        text = (ROOT / 'scripts/init-devkit.ps1').read_text()
        self.assertIn("'devkit_default_profile.py'", text)
        self.assertIn('$Source | & docker run', text)
        self.assertIn('--network none', text)
        self.assertNotIn('pip install', text)

    def test_ci_keeps_full_tests_and_boots_old_default_fixture(self):
        verify = (ROOT / 'scripts/verify.sh').read_text()
        self.assertIn('check_devkit_naming', verify)
        self.assertIn('run_regression_tests.py', verify)
        smoke = (ROOT / 'scripts/smoke_devkit_image.py').read_text()
        for kind in ('previous-default', 'old-collision', 'interrupted'):
            self.assertIn(kind, smoke)
        workflow = (ROOT / '.github/workflows/approval-ui.yml').read_text()
        self.assertIn('custom-skills/core/dev-session/**', workflow)

    def test_detector_accepts_sqlite_literals_and_theme(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'code.py').write_text('import sqlite3\nfrom typing import Literal\n')
            theme = root / 'docs/session-approval.md'
            theme.parent.mkdir()
            theme.write_text('라이트 모드')
            self.assertEqual(naming.violations(root), [])

    def test_detector_rejects_old_skill_path_and_display_name(self):
        for name, text in (('README.md', 'Hermes Lite'),
                           ('custom-skills/lite/example/SKILL.md', 'name: example'),
                           ('docs/current.md', 'dev-lite-session')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
                self.assertTrue(naming.violations(root))

    def test_wire_exception_does_not_allow_old_display_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'scripts/devkit_approval_ui.py'
            path.parent.mkdir()
            path.write_text('PROTOCOL = "lite_change_approval_v1"')
            self.assertEqual(naming.violations(root), [])
            path.write_text('PROTOCOL = "lite_change_approval_v1"\nprint("Lite approval")')
            self.assertTrue(naming.violations(root))


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Offline contract tests. They do not claim actual plugin/browser verification."""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("design_plugins", HERE / "design_plugins.py")
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)


class DesignPluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.pack = dp.load_pack()
        self.config = {"model": "keep-this-model", "plugins": {
            "enabled": ["existing-plugin"], "entries": {"other": {"keep": 7}}}}
        self.write_config()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write_config(self):
        (self.home / "config.yaml").write_text(yaml.safe_dump(self.config), encoding="utf-8")

    def save_pack(self, pack):
        path = self.home / "pack.yaml"
        path.write_text(yaml.safe_dump(pack), encoding="utf-8")
        return path

    def mock_config(self, **values):
        self.config["plugins"]["entries"]["mock-review"] = values
        self.write_config()

    def test_three_exact_pins(self):
        self.assertEqual(len(self.pack["plugins"]), 3)
        for row in self.pack["plugins"]:
            self.assertRegex(row["ref"], r"^[a-f0-9]{40}$")

    def test_branch_pin_rejected(self):
        self.pack["plugins"][0]["ref"] = "main"
        with self.assertRaises(dp.SetupError): dp.load_pack(self.save_pack(self.pack))

    def test_unknown_source_rejected(self):
        self.pack["plugins"][0]["repo"] = "https://example.com/plugin"
        with self.assertRaises(dp.SetupError): dp.load_pack(self.save_pack(self.pack))

    def test_duplicate_source_rejected(self):
        self.pack["plugins"][1] = self.pack["plugins"][0]
        with self.assertRaises(dp.SetupError): dp.load_pack(self.save_pack(self.pack))

    def test_wake_cannot_be_enabled_in_pack(self):
        self.pack["config"]["mock-review"]["wake_required"] = True
        with self.assertRaises(dp.SetupError): dp.load_pack(self.save_pack(self.pack))

    def test_secret_config_rejected(self):
        self.pack["config"]["mock-review"]["webhook_secret"] = "test-not-a-secret"
        with self.assertRaises(dp.SetupError): dp.load_pack(self.save_pack(self.pack))

    def test_wrong_scalar_type_rejected(self):
        self.pack["config"]["mock-review"]["wake_required"] = "false"
        with self.assertRaises(dp.SetupError): dp.load_pack(self.save_pack(self.pack))

    def test_config_read_is_non_mutating(self):
        before = (self.home / "config.yaml").read_bytes()
        missing = dp.check_config(self.home, self.pack)
        self.assertIn("wake_required", missing)
        self.assertEqual(before, (self.home / "config.yaml").read_bytes())

    def test_existing_wake_conflict_is_not_overwritten(self):
        self.mock_config(wake_required=True)
        before = (self.home / "config.yaml").read_bytes()
        with self.assertRaises(dp.SetupError): dp.check_config(self.home, self.pack)
        self.assertEqual(before, (self.home / "config.yaml").read_bytes())

    def test_conflicting_environment_is_refused(self):
        with patch.dict(os.environ, {"MOCKREVIEW_WAKE_REQUIRED": "true"}):
            with self.assertRaises(dp.SetupError): dp.check_config(self.home, self.pack)

    def test_external_host_is_refused(self):
        self.mock_config(default_host="herenow")
        with self.assertRaises(dp.SetupError): dp.check_config(self.home, self.pack)

    def test_external_store_is_refused(self):
        self.mock_config(data_dir="/tmp/reviews")
        with self.assertRaises(dp.SetupError): dp.check_config(self.home, self.pack)

    def test_public_base_override_is_refused(self):
        with patch.dict(os.environ, {"MOCKREVIEW_PUBLIC_BASE": "https://example.invalid"}):
            with self.assertRaises(dp.SetupError): dp.check_config(self.home, self.pack)

    def test_missing_settings_are_not_ready(self):
        with self.assertRaises(dp.SetupError): dp.check_config(self.home, self.pack, complete=True)

    def test_complete_safe_config(self):
        self.mock_config(**self.pack["config"]["mock-review"])
        self.assertEqual(dp.check_config(self.home, self.pack, complete=True), [])

    def test_backup_matches_bytes_and_is_private(self):
        original = (self.home / "config.yaml").read_bytes()
        path = dp.backup_config(self.home)
        self.assertEqual(path.read_bytes(), original)
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_distinct_backups_preserved(self):
        self.assertNotEqual(dp.backup_config(self.home), dp.backup_config(self.home))

    def test_no_installed_plugin(self):
        self.assertIsNone(dp.installed_dir(self.home, "mock-review"))

    def test_find_native_manifest(self):
        path = self.home / "plugins/hermes-mock-review"
        path.mkdir(parents=True)
        (path / "plugin.yaml").write_text("name: mock-review\n")
        self.assertEqual(dp.installed_dir(self.home, "mock-review"), path)

    def test_find_agent_plugins_v1_manifest(self):
        path = self.home / "plugins/tabella"
        path.mkdir(parents=True)
        (path / "plugin.json").write_text('{"name":"tabella"}')
        self.assertEqual(dp.installed_dir(self.home, "tabella"), path)

    def test_duplicate_manifest_is_refused(self):
        for folder in ("a", "b"):
            path = self.home / "plugins" / folder
            path.mkdir(parents=True)
            (path / "plugin.yaml").write_text("name: mock-review\n")
        with self.assertRaises(dp.SetupError): dp.installed_dir(self.home, "mock-review")

    @unittest.skipUnless(os.name == "posix", "POSIX symlink semantics")
    def test_symlinked_plugin_is_refused(self):
        external = self.home / "external"
        external.mkdir()
        (external / "plugin.yaml").write_text("name: mock-review\n")
        (self.home / "plugins").mkdir()
        (self.home / "plugins/mock-review").symlink_to(external, target_is_directory=True)
        with self.assertRaises(dp.SetupError): dp.installed_dir(self.home, "mock-review")

    def test_wrong_pin_is_refused(self):
        row = self.pack["plugins"][0]
        with patch.object(dp, "run", side_effect=["0" * 40, row["repo"], ""]):
            with self.assertRaises(dp.SetupError): dp.verify_pin(self.home, row)

    def test_dirty_worktree_is_refused(self):
        row = self.pack["plugins"][0]
        with patch.object(dp, "run", side_effect=[row["ref"], row["repo"], " M mcp.json"]):
            with self.assertRaises(dp.SetupError): dp.verify_pin(self.home, row)

    def test_matching_pin(self):
        row = self.pack["plugins"][0]
        with patch.object(dp, "run", side_effect=[row["ref"], row["repo"] + ".git", ""]):
            dp.verify_pin(self.home, row)

    def test_sample_has_no_wake_or_live_demo(self):
        cmd = dp.review_command("sample")
        self.assertIn("--no-wake", cmd)
        self.assertIn("--no-allow-live-demo", cmd)
        self.assertNotIn("--wake", cmd)
        self.assertEqual(cmd[cmd.index("--mode") + 1], "local")

    def test_sample_is_labeled_as_illustration(self):
        data = json.loads(dp.SAMPLE.read_text())
        self.assertIn("실제 문서를 렌더링한 결과", data["intro"])
        self.assertEqual(len(data["blocks"][1]["options"]), 2)

    def test_serve_is_foreground_without_worker(self):
        cmd = dp.review_command("serve")
        self.assertIn("--no-worker", cmd)
        self.assertNotIn("setup", cmd)
        self.assertNotIn("publish", cmd)

    def test_feedback_validates_id(self):
        for value in (None, "--wake", "../secret", "review;sh", "x" * 129):
            with self.assertRaises(dp.SetupError): dp.review_command("feedback", review_id=value)

    def test_feedback_has_no_side_effect_action(self):
        self.assertEqual(dp.review_command("feedback", review_id="r_abc-1"),
                         ["mockreview", "feedback", "r_abc-1", "--json"])

    def test_missing_custom_decisions_refused(self):
        with self.assertRaises(dp.SetupError): dp.review_command("create")

    def test_malformed_decisions_refused(self):
        p = self.home / "bad.json"
        p.write_text("not-json")
        with self.assertRaises(dp.SetupError): dp.review_command("create", decisions=p)

    def test_empty_blocks_refused(self):
        p = self.home / "empty.json"
        p.write_text('{"blocks":[]}')
        with self.assertRaises(dp.SetupError): dp.review_command("create", decisions=p)

    def test_create_accepts_valid_decisions(self):
        self.assertIn(str(dp.SAMPLE), dp.review_command("create", decisions=dp.SAMPLE))

    def test_compose_has_only_loopback_review_port(self):
        compose = yaml.safe_load((dp.ROOT / "compose.yml").read_text())
        ports = compose["services"]["hermes"]["ports"]
        self.assertEqual([p for p in ports if "8790" in p], ["127.0.0.1:8790:8790"])
        self.assertNotIn("mock-review", compose["services"]["hermes"].get("command", []))

    def test_explicitly_disabled_plugin_is_preserved(self):
        self.config["plugins"]["disabled"] = ["mock-review"]
        self.write_config()
        before = (self.home / "config.yaml").read_bytes()
        with patch.object(dp, "run") as runner:
            with self.assertRaises(dp.SetupError): dp.install(self.home, self.pack, ["hermes"])
            runner.assert_not_called()
        self.assertEqual(before, (self.home / "config.yaml").read_bytes())

    def test_install_uses_native_commands_and_preserves_unrelated_config(self):
        commands = []
        installed = {}
        def fake_dir(home, name):
            return installed.get(name)
        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            if cmd[1:3] == ["plugins", "install"]:
                installed[dp.IDENTITIES[cmd[3]]] = self.home / "plugins" / dp.IDENTITIES[cmd[3]]
            if cmd[1:3] == ["config", "set"]:
                key = cmd[3].split(".")[-1]
                config = dp.config_at(self.home)
                config["plugins"]["entries"].setdefault("mock-review", {})[key] = yaml.safe_load(cmd[4])
                (self.home / "config.yaml").write_text(yaml.safe_dump(config))
            if cmd[1:3] == ["plugins", "enable"]:
                config = dp.config_at(self.home)
                config["plugins"]["enabled"].append(cmd[3])
                (self.home / "config.yaml").write_text(yaml.safe_dump(config))
            return ""
        with patch.object(dp, "installed_dir", side_effect=fake_dir), patch.object(dp, "verify_pin"), \
             patch.object(dp, "run", side_effect=fake_run), patch("builtins.print"):
            dp.install(self.home, self.pack, ["hermes"])
        config = dp.config_at(self.home)
        self.assertEqual(config["model"], "keep-this-model")
        self.assertEqual(config["plugins"]["entries"]["other"], {"keep": 7})
        self.assertEqual(config["plugins"]["enabled"], ["existing-plugin", *dp.IDENTITIES.values()])
        installs = [cmd for cmd in commands if cmd[1:3] == ["plugins", "install"]]
        self.assertEqual(len(installs), 3)
        self.assertTrue(all("--ref" in cmd and "--no-enable" in cmd for cmd in installs))
        self.assertTrue(all("--force" not in cmd and "remove" not in cmd for cmd in commands))
        first_enable = next(i for i, cmd in enumerate(commands) if cmd[1:3] == ["plugins", "enable"])
        last_set = max(i for i, cmd in enumerate(commands) if cmd[1:3] == ["config", "set"])
        self.assertLess(last_set, first_enable)

    def test_existing_matching_plugins_are_not_reinstalled(self):
        self.mock_config(**self.pack["config"]["mock-review"])
        self.config["plugins"]["enabled"].extend(dp.IDENTITIES.values())
        self.write_config()
        with patch.object(dp, "installed_dir", side_effect=lambda home, name: home / "plugins" / name), patch.object(dp, "verify_pin"), \
             patch.object(dp, "run", return_value="") as runner, patch("builtins.print"):
            dp.install(self.home, self.pack, ["hermes"])
        commands = [call.args[0] for call in runner.call_args_list]
        self.assertFalse(any(cmd[1:3] == ["plugins", "install"] for cmd in commands))
        self.assertFalse(any(cmd[1:3] == ["config", "set"] for cmd in commands))

    def test_failed_install_does_not_enable_plugins_or_seed_config(self):
        before = (self.home / "config.yaml").read_bytes()
        with patch.object(dp, "installed_dir", return_value=None), \
             patch.object(dp, "run", side_effect=dp.SetupError("native refusal")) as runner, \
             patch("builtins.print"):
            with self.assertRaises(dp.SetupError): dp.install(self.home, self.pack, ["hermes"])
        self.assertEqual(before, (self.home / "config.yaml").read_bytes())
        self.assertEqual(len(runner.call_args_list), 1)
        self.assertEqual(runner.call_args.args[0][1:3], ["plugins", "install"])

    def test_enabled_directory_key_is_recognized(self):
        self.config["plugins"]["enabled"].append("hermes-mock-review")
        self.write_config()
        self.assertTrue(dp.plugin_enabled(self.home, "mock-review", self.home / "plugins/hermes-mock-review"))

    def test_disabled_directory_key_is_preserved(self):
        self.config["plugins"]["disabled"] = ["hermes-mock-review"]
        self.write_config()
        with patch.object(dp, "run") as runner:
            with self.assertRaises(dp.SetupError): dp.install(self.home, self.pack, ["hermes"])
            runner.assert_not_called()

    def test_disabled_alias_overrides_enabled_name(self):
        self.config["plugins"]["enabled"].append("mock-review")
        self.config["plugins"]["disabled"] = ["hermes-mock-review"]
        self.write_config()
        self.assertFalse(dp.plugin_enabled(self.home, "mock-review", self.home / "plugins/hermes-mock-review"))

    def test_plugin_registration_outside_store_is_refused(self):
        with self.assertRaises(dp.SetupError): dp.plugin_keys(self.home, "mock-review", self.home / "other")

    def test_native_enable_without_activation_is_not_reported_success(self):
        self.mock_config(**self.pack["config"]["mock-review"])
        with patch.object(dp, "installed_dir", side_effect=lambda home, name: home / "plugins" / name), \
             patch.object(dp, "verify_pin"), patch.object(dp, "run", return_value=""), patch("builtins.print"):
            with self.assertRaises(dp.SetupError): dp.install(self.home, self.pack, ["hermes"])

    def test_plan_requires_no_hermes_home(self):
        with patch("builtins.print"):
            self.assertEqual(dp.main(["plan"]), 0)

    def test_install_without_persistent_home_fails_closed(self):
        with patch("builtins.print"):
            self.assertEqual(dp.main(["install"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

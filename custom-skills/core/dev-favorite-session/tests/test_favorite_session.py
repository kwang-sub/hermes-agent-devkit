#!/usr/bin/env python3
"""Hermes native pin integration contract tests; never touch a real state.db."""
from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "favorite_session.py"
spec = importlib.util.spec_from_file_location("favorite_session", SCRIPT)
favorite = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = favorite
spec.loader.exec_module(favorite)

ID1 = "20261117_101500_a1b2c3"
ID2 = "20261116_091200_b2c3d4"
ID3 = "20261115_091200_c3d4e5"


class FakeHermesCli:
    def __init__(self, records, pinned=(), fail_rename=False, fail_unpin=False, fail_pin=False):
        self.records = dict(records)
        self.pinned_ids = set(pinned)
        self.calls = []
        self.fail_rename = fail_rename
        self.fail_unpin = fail_unpin
        self.fail_pin = fail_pin

    def pinned(self):
        self.calls.append(("pinned",))
        return [favorite.PinnedSession(id=sid, title=self.records[sid], source="cli",
                last_active=1730000000, message_count=10)
                for sid in self.records if sid in self.pinned_ids]

    def pin(self, session_id):
        self.calls.append(("pin", session_id))
        if self.fail_pin:
            raise favorite.FavoriteError("hermes_command_failed", "pin failed")
        if session_id not in self.records:
            raise favorite.FavoriteError("hermes_command_failed", "no session")
        self.pinned_ids.add(session_id)

    def unpin(self, session_id):
        self.calls.append(("unpin", session_id))
        if self.fail_unpin:
            raise favorite.FavoriteError("hermes_command_failed", "unpin failed")
        self.pinned_ids.discard(session_id)

    def rename(self, session_id, title):
        self.calls.append(("rename", session_id, title))
        if self.fail_rename or title in [v for k, v in self.records.items() if k != session_id]:
            raise favorite.FavoriteError("hermes_command_failed", "title conflict")
        self.records[session_id] = title


class FavoriteSessionTests(unittest.TestCase):
    def test_register_new_with_title_update(self):
        cli = FakeHermesCli({ID1: "old name"})
        result = favorite.register(cli, ID1, "XOCR-인증개선")
        self.assertTrue(result["ok"])
        self.assertTrue(result["pin_added"])
        self.assertTrue(result["title_updated"])
        self.assertIn(ID1, cli.pinned_ids)
        self.assertEqual(cli.records[ID1], "XOCR-인증개선")
        self.assertEqual([c[0] for c in cli.calls].count("rename"), 1)

    def test_register_existing_same_title_already_pinned_is_idempotent(self):
        cli = FakeHermesCli({ID1: "XOCR-인증개선"}, pinned=[ID1])
        result = favorite.register(cli, ID1, "XOCR-인증개선")
        self.assertFalse(result["pin_added"])
        self.assertFalse(result["title_updated"])
        self.assertEqual({c[0] for c in cli.calls}, {"pinned"})

    def test_register_same_title_unpinned_never_renames(self):
        cli = FakeHermesCli({ID1: "XOCR-인증개선"})
        result = favorite.register(cli, ID1, "XOCR-인증개선")
        self.assertTrue(result["pin_added"])
        self.assertFalse(result["title_updated"])
        self.assertNotIn("rename", [c[0] for c in cli.calls])

    def test_register_existing_pin_updates_title(self):
        cli = FakeHermesCli({ID1: "old"}, pinned=[ID1])
        result = favorite.register(cli, ID1, "new")
        self.assertFalse(result["pin_added"])
        self.assertTrue(result["title_updated"])
        self.assertIn(ID1, cli.pinned_ids)
        self.assertNotIn("unpin", [c[0] for c in cli.calls])

    def test_title_collision_restores_original_unpinned_state(self):
        cli = FakeHermesCli({ID1: "old", ID2: "name exists"})
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.register(cli, ID1, "name exists")
        self.assertEqual(caught.exception.code, "hermes_command_failed")
        self.assertNotIn(ID1, cli.pinned_ids)
        self.assertEqual(cli.records[ID1], "old")
        self.assertIn(("unpin", ID1), cli.calls)

    def test_title_collision_preserves_previously_pinned_state(self):
        cli = FakeHermesCli({ID1: "old", ID2: "taken"}, pinned=[ID1])
        with self.assertRaises(favorite.FavoriteError):
            favorite.register(cli, ID1, "taken")
        self.assertIn(ID1, cli.pinned_ids)
        self.assertNotIn("unpin", [c[0] for c in cli.calls])

    def test_failed_pin_never_renames(self):
        cli = FakeHermesCli({ID1: "old"}, fail_pin=True)
        with self.assertRaises(favorite.FavoriteError):
            favorite.register(cli, ID1, "new")
        self.assertNotIn("rename", [c[0] for c in cli.calls])

    def test_rollback_failure_is_visible(self):
        cli = FakeHermesCli({ID1: "old"}, fail_rename=True, fail_unpin=True)
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.register(cli, ID1, "new")
        self.assertEqual(caught.exception.code, "partial_failure")
        self.assertTrue(caught.exception.details["verify_manually"])
        self.assertIn(ID1, cli.pinned_ids)

    def test_list_pagination_and_empty(self):
        cli = FakeHermesCli({ID1: "A", ID2: "B", ID3: "C"}, pinned=[ID1, ID2, ID3])
        first = favorite.list_pins(cli, offset=0, limit=2)
        second = favorite.list_pins(cli, offset=2, limit=2)
        self.assertEqual(first["total"], 3)
        self.assertEqual([v["id"] for v in first["sessions"]], [ID1, ID2])
        self.assertTrue(first["has_more"])
        self.assertEqual(second["sessions"][0]["id"], ID3)
        self.assertTrue(second["has_previous"])
        self.assertFalse(second["has_more"])
        self.assertEqual(favorite.list_pins(FakeHermesCli({}))["sessions"], [])

    def test_invalid_pagination_refused(self):
        cli = FakeHermesCli({})
        for offset, limit in ((-1, 2), (0, 0), (0, 5)):
            with self.subTest(offset=offset, limit=limit):
                with self.assertRaises(favorite.FavoriteError):
                    favorite.list_pins(cli, offset=offset, limit=limit)
        self.assertEqual(cli.calls, [])

    def test_resume_by_exact_title_prefers_exact_to_prefix(self):
        cli = FakeHermesCli({ID1: "XOCR", ID2: "XOCR-개선"}, pinned=[ID1, ID2])
        result = favorite.prepare_resume(cli, session_id=None, title="XOCR")
        self.assertEqual(result["session"]["id"], ID1)
        self.assertEqual(result["resume_slash"], f"/resume {ID1}")
        self.assertIn("입력창", result["note"])

    def test_resume_by_unique_prefix_and_id(self):
        cli = FakeHermesCli({ID1: "XOCR-인증개선"}, pinned=[ID1])
        self.assertEqual(favorite.prepare_resume(cli, session_id=None, title="XOCR")["session"]["id"], ID1)
        self.assertEqual(favorite.prepare_resume(cli, session_id=ID1, title=None)["session"]["id"], ID1)

    def test_ambiguous_title_does_not_pick_silently(self):
        cli = FakeHermesCli({ID1: "XOCR-개선", ID2: "XOCR-테스트"}, pinned=[ID1, ID2])
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.prepare_resume(cli, session_id=None, title="XOCR")
        self.assertEqual(caught.exception.code, "ambiguous_title")
        self.assertEqual(len(caught.exception.details["candidates"]), 2)

    def test_missing_pinned_session_no_resume(self):
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.prepare_resume(FakeHermesCli({ID1: "hi"}), session_id=ID1, title=None)
        self.assertEqual(caught.exception.code, "not_pinned")

    def test_remove_requires_confirmation_and_exact_title(self):
        cli = FakeHermesCli({ID1: "XOCR-인증개선"}, pinned=[ID1])
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.remove_pin(cli, ID1, expected_title="XOCR-인증개선", confirmed=False)
        self.assertEqual(caught.exception.code, "confirmation_required")
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.remove_pin(cli, ID1, expected_title="old title", confirmed=True)
        self.assertEqual(caught.exception.code, "session_changed")
        self.assertIn(ID1, cli.pinned_ids)
        self.assertNotIn("unpin", [c[0] for c in cli.calls])
        result = favorite.remove_pin(cli, ID1, expected_title="XOCR-인증개선", confirmed=True)
        self.assertTrue(result["ok"])
        self.assertFalse(result["conversation_deleted"])
        self.assertNotIn(ID1, cli.pinned_ids)
        self.assertEqual(cli.records[ID1], "XOCR-인증개선")

    def test_remove_already_unpinned_fails_without_writing(self):
        cli = FakeHermesCli({ID1: "test"})
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.remove_pin(cli, ID1, expected_title="test", confirmed=True)
        self.assertEqual(caught.exception.code, "not_pinned")
        self.assertNotIn("unpin", [c[0] for c in cli.calls])

    def test_validate_title_and_id(self):
        for title in ("", "\n", "title\nnext", "t" * 101):
            with self.subTest(title=repr(title)):
                with self.assertRaises(favorite.FavoriteError):
                    favorite.validate_title(title)
        for session_id in ("", "--", "abc;rm", "a b", "x/../y"):
            with self.subTest(session_id=session_id):
                with self.assertRaises(favorite.FavoriteError):
                    favorite.validate_session_id(session_id)
        self.assertEqual(favorite.validate_title(" XOCR-인증개선 "), "XOCR-인증개선")
        self.assertEqual(favorite.validate_title("XOCR   인증개선"), "XOCR 인증개선")

    def test_native_cli_is_argv_only_not_shell(self):
        completed = subprocess.CompletedProcess(["hermes"], 0, stdout="[]\n", stderr="")
        with patch.object(favorite.subprocess, "run", return_value=completed) as spy:
            cli = favorite.HermesCli("/usr/bin/hermes")
            cli.pinned()
            cli.rename(ID1, "title;echo injected")
            cli.pin(ID1)
            cli.unpin(ID1)
        cmds = [call.args[0] for call in spy.call_args_list]
        self.assertEqual(cmds[0], ["/usr/bin/hermes", "sessions", "pinned", "--json"])
        self.assertEqual(cmds[1], ["/usr/bin/hermes", "sessions", "rename", ID1, "--", "title;echo injected"])
        self.assertTrue(all(c[1] == "sessions" for c in cmds))
        self.assertTrue(all(call.kwargs.get("shell") is None for call in spy.call_args_list))
        self.assertTrue(all(call.kwargs.get("timeout") == 30 for call in spy.call_args_list))

    def test_native_cli_json_response_validation(self):
        cli = favorite.HermesCli("/usr/bin/hermes")
        for output in ("not json", "{}", '[{"id":""}]', '[{"id":"abc"},{"id":"abc"}]'):
            with self.subTest(output=output):
                proc = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
                with patch.object(favorite.subprocess, "run", return_value=proc):
                    with self.assertRaises(favorite.FavoriteError):
                        cli.pinned()

    def test_cli_error_does_not_claim_success(self):
        cli = favorite.HermesCli("/usr/bin/hermes")
        proc = subprocess.CompletedProcess([], 2, stdout="", stderr="No such session")
        with patch.object(favorite.subprocess, "run", return_value=proc):
            with self.assertRaises(favorite.FavoriteError) as caught:
                cli.pin(ID1)
        self.assertEqual(caught.exception.code, "hermes_command_failed")

    def test_argparse_delete_fails_closed_without_confirm(self):
        cli = FakeHermesCli({ID1: "XOCR"}, pinned=[ID1])
        args = favorite.build_parser().parse_args(
            ["remove", "--session-id", ID1, "--expected-title", "XOCR"])
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.dispatch(args, cli)
        self.assertEqual(caught.exception.code, "confirmation_required")

    def test_subprocess_smoke_register_list_resume_and_unpin(self):
        """Real argv/JSON round trip against a fake native CLI executable, not a user DB."""
        with tempfile.TemporaryDirectory(prefix="hermes-pin-test-") as tmp:
            temp = Path(tmp)
            state = temp / "state.json"
            state.write_text(json.dumps({"records": {ID1: "old title"}, "pinned": []}), encoding="utf-8")
            exe = temp / "hermes"
            exe.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ["FAKE_HERMES_STATE"])
state = json.loads(path.read_text(encoding="utf-8"))
a = sys.argv[1:]
assert a[0] == "sessions", a
a = a[1:]
if a[:2] == ["pinned", "--json"]:
    print(json.dumps([{"id": key, "title": value, "source": "cli", "last_active": 0,
                       "message_count": 1} for key, value in state["records"].items()
                       if key in state["pinned"]]))
elif a[0] == "pin":
    if a[1] not in state["records"]: sys.exit(2)
    state["pinned"] = sorted(set(state["pinned"] + [a[1]]))
elif a[0] == "unpin":
    state["pinned"] = [i for i in state["pinned"] if i != a[1]]
elif a[0] == "rename":
    sid = a[1]
    title = a[-1]
    if title in [v for k, v in state["records"].items() if k != sid]: sys.exit(2)
    state["records"][sid] = title
else:
    sys.exit(2)
path.write_text(json.dumps(state), encoding="utf-8")
''', encoding="utf-8")
            exe.chmod(0o755)
            env = dict(os.environ, FAKE_HERMES_STATE=str(state))

            def call(*args):
                run = subprocess.run([sys.executable, str(SCRIPT), "--hermes-bin", str(exe), *args],
                                     capture_output=True, text=True, env=env, timeout=10)
                return run.returncode, json.loads(run.stdout)

            code, result = call("register", "--session-id", ID1, "--title=XOCR-인증개선")
            self.assertEqual(code, 0, result)
            self.assertTrue(result["pin_added"])
            code, result = call("list")
            self.assertEqual(code, 0)
            self.assertEqual(result["sessions"][0]["title"], "XOCR-인증개선")
            code, result = call("prepare-resume", "--title", "XOCR")
            self.assertEqual(code, 0)
            self.assertEqual(result["resume_slash"], "/resume " + ID1)
            code, result = call("remove", "--session-id", ID1, "--expected-title", "XOCR-인증개선")
            self.assertEqual(code, 1)
            self.assertEqual(result["code"], "confirmation_required")
            code, result = call("remove", "--session-id", ID1, "--expected-title", "XOCR-인증개선", "--confirmed")
            self.assertEqual(code, 0)
            self.assertFalse(result["conversation_deleted"])
            final = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(final["records"][ID1], "XOCR-인증개선")
            self.assertEqual(final["pinned"], [])

    def test_unpin_without_title_uses_id_and_double_confirmation(self):
        cli = FakeHermesCli({ID1: ""}, pinned=[ID1])
        result = favorite.remove_pin(cli, ID1, expected_title="", confirmed=True)
        self.assertTrue(result["ok"])
        self.assertFalse(result["conversation_deleted"])

    def test_new_pin_after_rename_success_but_readback_failure_reports_partial(self):
        class PostRenameReadFailure(FakeHermesCli):
            def pinned(self):
                if self.records[ID1] == "new":
                    raise favorite.FavoriteError("hermes_command_failed", "readback failed")
                return super().pinned()
        cli = PostRenameReadFailure({ID1: "old"})
        with self.assertRaises(favorite.FavoriteError) as caught:
            favorite.register(cli, ID1, "new")
        self.assertEqual(caught.exception.code, "partial_failure")
        self.assertTrue(caught.exception.details["verify_manually"])

    def test_skill_contract_and_no_unsafe_mutations(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")
        for required in ("name: dev-favorite-session", "requires_tools: [terminal, clarify]",
                         '"신규 등록"', '"즐겨찾기 목록"', '"즐겨찾기 재개"', '"즐겨찾기 삭제"',
                         "${HERMES_SESSION_ID}", "prepare-resume", "--confirmed", "대화 내용은 보존"):
            self.assertIn(required, skill)
        self.assertNotIn("shell=True", script)
        self.assertNotIn("sqlite3.connect", script)
        self.assertNotIn('self._run("delete"', script)
        self.assertNotIn('self._run("prune"', script)


if __name__ == "__main__":
    unittest.main()

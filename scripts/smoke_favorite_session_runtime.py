#!/usr/bin/env python3
"""Test favorites against the image's real Hermes CLI using a disposable profile."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


def main() -> None:
    with TemporaryDirectory(prefix="devkit-favorite-smoke-") as tmp:
        # Never run this against the invoking profile's sessions or /opt/data.
        os.environ["HERMES_HOME"] = tmp
        scripts = Path("/opt/devkit-tests/custom-skills/core/dev-favorite-session/scripts")
        sys.path.insert(0, str(scripts))
        from hermes_state import SessionDB
        from favorite_session import HermesCli, register, list_pins, prepare_resume, remove_pin

        sid = "20261117_101500_a1b2c3"
        db = SessionDB(db_path=Path(tmp) / "state.db")
        try:
            db.create_session(session_id=sid, source="cli")
            db.append_message(sid, role="user", content="pin integration fixture")
        finally:
            db.close()

        cli = HermesCli("/opt/hermes/.venv/bin/hermes")
        registered = register(cli, sid, "XOCR-인증개선")
        assert registered["ok"] and registered["pin_added"] and registered["title_updated"], registered
        listed = list_pins(cli)
        assert [row["id"] for row in listed["sessions"]] == [sid], listed
        prepared = prepare_resume(cli, session_id=None, title="XOCR-인증개선")
        assert prepared["resume_slash"] == f"/resume {sid}", prepared
        removed = remove_pin(cli, sid, expected_title="XOCR-인증개선", confirmed=True)
        assert removed["ok"] and not removed["conversation_deleted"], removed
        assert list_pins(cli)["sessions"] == []

        db = SessionDB(db_path=Path(tmp) / "state.db", read_only=True)
        try:
            row = db.get_session(sid)
            assert row is not None and row["title"] == "XOCR-인증개선", row
        finally:
            db.close()
    print("[PASS] Real Hermes CLI register/list/resolve/unpin; transcript preserved")


if __name__ == "__main__":
    main()

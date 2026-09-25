#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "recovery_board_inventory.py"


def make_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def run_inventory(fake_hermes: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--hermes-bin",
            str(fake_hermes),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_object_payload_filters_archived_and_prioritizes_current() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fake = root / "hermes"
        payload = {
            "current": "chagok",
            "boards": [
                {
                    "slug": "default",
                    "name": "Default",
                    "counts": {"ready": 2, "blocked": 1},
                    "archived": False,
                },
                {
                    "slug": "chagok",
                    "name": "Chagok",
                    "counts": {"blocked": 3, "triage": 1, "done": 7},
                    "total": 11,
                    "archived": False,
                },
                {
                    "slug": "old-board",
                    "name": "Old",
                    "counts": {"blocked": 9},
                    "archived": True,
                },
            ],
        }
        make_executable(
            fake,
            "#!/usr/bin/env sh\n"
            'test "$1" = "kanban"\n'
            'test "$2" = "boards"\n'
            'test "$3" = "list"\n'
            'test "$4" = "--json"\n'
            f"printf '%s\\n' {json.dumps(json.dumps(payload))}\n",
        )

        result = run_inventory(fake)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "pass"
        assert data["source"] == "hermes kanban boards list --json"
        assert data["current"] == "chagok"
        assert data["count"] == 2
        assert [row["slug"] for row in data["boards"]] == ["chagok", "default"]
        assert data["boards"][0]["is_current"] is True
        assert data["boards"][0]["blocked_count"] == 3
        assert data["boards"][0]["total"] == 11
        assert data["boards"][1]["blocked_count"] == 1
        assert data["boards"][1]["total"] == 3


def test_list_payload_is_supported_without_current_pointer() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fake = root / "hermes"
        payload = [
            {
                "slug": "beta",
                "name": "Beta",
                "is_current": False,
                "counts": {"blocked": 0},
            },
            {
                "slug": "alpha",
                "name": "Alpha",
                "is_current": True,
                "counts": {"blocked": 2},
            },
        ]
        make_executable(
            fake,
            "#!/usr/bin/env sh\n"
            f"printf '%s\\n' {json.dumps(json.dumps(payload))}\n",
        )

        result = run_inventory(fake)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["current"] is None
        assert [row["slug"] for row in data["boards"]] == ["alpha", "beta"]
        assert data["boards"][0]["is_current"] is True


def test_invalid_json_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fake = root / "hermes"
        make_executable(
            fake,
            "#!/usr/bin/env sh\n"
            "printf 'not-json\\n'\n",
        )

        result = run_inventory(fake)
        assert result.returncode == 2
        data = json.loads(result.stderr)
        assert data["status"] == "blocked"
        assert data["blocker"] == "BOARD_INVENTORY_UNAVAILABLE"
        assert "invalid JSON" in data["error"]


def test_cli_failure_fails_closed_without_switch_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fake = root / "hermes"
        make_executable(
            fake,
            "#!/usr/bin/env sh\n"
            "printf 'permission denied\\n' >&2\n"
            "exit 7\n",
        )

        result = run_inventory(fake)
        assert result.returncode == 2
        data = json.loads(result.stderr)
        assert data["status"] == "blocked"
        assert data["blocker"] == "BOARD_INVENTORY_UNAVAILABLE"
        assert "permission denied" in data["error"]


def main() -> int:
    tests = (
        test_object_payload_filters_archived_and_prioritizes_current,
        test_list_payload_is_supported_without_current_pointer,
        test_invalid_json_fails_closed,
        test_cli_failure_fails_closed_without_switch_fallback,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

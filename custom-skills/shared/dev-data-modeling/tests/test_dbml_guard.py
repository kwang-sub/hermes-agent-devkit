#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dbml_guard.py"
SPEC = importlib.util.spec_from_file_location("dbml_guard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_valid_schema() -> None:
    result = MODULE.analyze('''
Table account {
  id bigint [pk]
}
Table tx {
  id bigint [pk]
  account_id bigint
}
Ref: tx.account_id > account.id
''')
    assert result["status"] == "pass"
    assert result["table_count"] == 2
    assert result["ref_count"] == 1
    assert result["errors"] == []


def test_duplicate_table_is_blocked() -> None:
    result = MODULE.analyze('''
Table account { id bigint [pk] }
Table account { id bigint [pk] }
''')
    assert result["status"] == "blocked"
    assert any("duplicate Table" in item for item in result["errors"])


def test_missing_ref_target_is_blocked() -> None:
    result = MODULE.analyze('''
Table tx {
  account_id bigint
}
Ref: tx.account_id > account.id
''')
    assert result["status"] == "blocked"
    assert any("account" in item for item in result["errors"])


def test_vendor_token_is_warning_in_logical_mode() -> None:
    result = MODULE.analyze('''
Table account {
  name nvarchar(100)
}
''', mode="logical")
    assert result["status"] == "pass"
    assert result["warnings"]


def test_vendor_token_allowed_in_physical_mode() -> None:
    result = MODULE.analyze('''
Table account {
  name nvarchar(100)
}
''', mode="physical")
    assert result["status"] == "pass"
    assert result["warnings"] == []


if __name__ == "__main__":
    test_valid_schema()
    test_duplicate_table_is_blocked()
    test_missing_ref_target_is_blocked()
    test_vendor_token_is_warning_in_logical_mode()
    test_vendor_token_allowed_in_physical_mode()
    print("[PASS] DBML lightweight guard tests")

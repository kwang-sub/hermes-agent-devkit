#!/usr/bin/env python3
"""Validate browser verification handoff evidence without launching a browser."""
import argparse
import json
from pathlib import Path

AC_STATES = {"PASS", "FAIL", "NOT_RUN"}
RUN_STATES = AC_STATES | {"BLOCKED_ENV", "UNSUPPORTED", "INCONCLUSIVE"}
REQUIRED = {"schema", "task_id", "provider", "session", "verified_at",
            "capabilities", "acceptance_criteria", "cleanup"}

def validate(data):
    if not isinstance(data, dict) or not REQUIRED.issubset(data):
        raise ValueError("missing evidence fields")
    if data["schema"] != "browser_verification_v1":
        raise ValueError("unsupported schema")
    for key in ("task_id", "provider", "session", "verified_at"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError("invalid " + key)
    if not isinstance(data["capabilities"], list) or not isinstance(data["acceptance_criteria"], list):
        raise ValueError("capabilities and acceptance_criteria must be arrays")
    names = set()
    for cap in data["capabilities"]:
        if not isinstance(cap, dict):
            raise ValueError("invalid capability")
        name = cap.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("duplicate/invalid capability name")
        names.add(name)
        if cap.get("status") not in AC_STATES or cap.get("execution_status") not in RUN_STATES:
            raise ValueError("invalid capability result")
        if cap["status"] == "PASS" and cap["execution_status"] != "PASS":
            raise ValueError("capability PASS without execution PASS")
        if cap["execution_status"] in ("BLOCKED_ENV", "UNSUPPORTED", "INCONCLUSIVE") and cap["status"] != "NOT_RUN":
            raise ValueError("environment outcome must be NOT_RUN")
        if not isinstance(cap.get("evidence"), str):
            raise ValueError("missing capability evidence")
    seen = set()
    for ac in data["acceptance_criteria"]:
        if not isinstance(ac, dict):
            raise ValueError("invalid AC")
        aid = ac.get("ac_id")
        if not isinstance(aid, str) or not aid or aid in seen:
            raise ValueError("invalid/duplicate AC ID")
        seen.add(aid)
        if ac.get("status") not in AC_STATES or ac.get("capability") not in names:
            raise ValueError("invalid AC result/capability")
        if not isinstance(ac.get("method"), str) or not isinstance(ac.get("evidence"), str):
            raise ValueError("missing AC evidence/method")
        cap = next(c for c in data["capabilities"] if c["name"] == ac["capability"])
        if ac["status"] == "PASS" and cap["status"] != "PASS":
            raise ValueError("AC PASS without required capability PASS")
    if not isinstance(data["cleanup"], dict) or data["cleanup"].get("status") not in ("PASS", "WARNING", "NOT_RUN"):
        raise ValueError("invalid cleanup status")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        validate(json.loads(args.path.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        print("BROWSER_EVIDENCE_STATUS=FAIL")
        print("BROWSER_EVIDENCE_REASON=" + str(exc))
        return 1
    print("BROWSER_EVIDENCE_STATUS=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

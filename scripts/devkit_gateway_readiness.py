#!/usr/bin/env python3
"""Read-only readiness probe for the live default Hermes Gateway.

Never treats s6 'up', configuration, or a stale PID as proof of serving profiles.
A standalone default Gateway is valid when its running record belongs to the
verified process. Empty served_profiles means no multiplexed profiles, not a
missing default Gateway. Never accept configuration or an unverified PID alone.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REQUIRED = frozenset(("default",))
LEGACY_ROLE_PROFILES = frozenset(("coder", "orchestrator", "reviewer"))


def classify(live_pid, record, served, expected=REQUIRED):
    record = record if isinstance(record, dict) else {}
    if live_pid is None:
        return "NO_VERIFIED_LIVE_GATEWAY"
    if served is None:
        return "SERVED_PROFILE_RECORD_UNAVAILABLE"
    if LEGACY_ROLE_PROFILES.intersection(served):
        return "LEGACY_ROLE_PROFILES_STILL_SERVED"
    if not served and expected == REQUIRED:
        # Upstream intentionally records [] for the sole default profile.
        # Require the actual running process and its own status, not just s6 up.
        if (record.get("pid") == live_pid
                and record.get("gateway_state") == "running"
                and record.get("multiplex_standalone_reason")
                == "only one profile exists (nothing to multiplex)"):
            return "READY"
        return "STANDALONE_OR_INCOMPLETE_MULTIPLEX"
    if not expected.issubset(set(served)):
        return "STANDALONE_OR_INCOMPLETE_MULTIPLEX"
    return "READY"


def snapshot():
    from hermes_constants import get_default_hermes_root
    from gateway.status import read_runtime_status
    from hermes_cli.gateway_multiplex_served import live_default_gateway_pid, recorded_served_profiles
    root = Path(get_default_hermes_root())
    record = read_runtime_status(root / "gateway_state.json") or {}
    pid = live_default_gateway_pid()
    served = recorded_served_profiles()
    return root, pid, record, served


def explain(root, pid, record, served, reason):
    # Never dump raw status: it can contain integration endpoints/config values.
    recorded = record.get("served_profiles")
    if not isinstance(recorded, list):
        recorded = None
    flags = {
        "reason": reason,
        "root": str(root),
        "verified_live_pid": pid,
        "gateway_state": str(record.get("gateway_state", "<missing>")),
        "raw_served_profiles": recorded,
        "verified_served_profiles": served,
        "standalone_reason": str(record.get("multiplex_standalone_reason") or "<none>"),
        "required": sorted(REQUIRED),
    }
    for key, value in flags.items():
        print(f"GATEWAY_{key.upper()}={value}", file=sys.stderr)
    if reason == "STANDALONE_OR_INCOMPLETE_MULTIPLEX":
        print("Default Gateway is not yet proven running; inspect its verified PID and current status. Do not create role profiles to satisfy readiness.", file=sys.stderr)
    elif reason == "NO_VERIFIED_LIVE_GATEWAY":
        print("s6 up is not proof of a live gateway. Check 'docker logs hermes-dev' and gateway PID/state identity.", file=sys.stderr)
    else:
        print("Gateway has no verified served-profile record yet; inspect gateway_state.json and startup logs.", file=sys.stderr)


def wait_ready(timeout: float, poll: float = 1.0) -> int:
    deadline = time.monotonic() + max(0.0, timeout)
    rescanned = False
    while True:
        root, pid, record, served = snapshot()
        status = classify(pid, record, served)
        if status == "READY":
            print("PASS: verified live Gateway serves default (legacy roles absent)")
            return 0
        if pid is not None and not rescanned and served is not None and "default" in served:
            from hermes_cli.gateway_multiplex_served import notify_multiplexer_profiles_changed
            notify_multiplexer_profiles_changed("devkit-runtime-check", timeout=3.0)
            rescanned = True
        if time.monotonic() >= deadline:
            explain(root, pid, record, served, status)
            return 1
        time.sleep(min(poll, max(0.0, deadline - time.monotonic())))


def self_test():
    assert classify(None, {}, None) == "NO_VERIFIED_LIVE_GATEWAY"
    assert classify(12, {}, None) == "SERVED_PROFILE_RECORD_UNAVAILABLE"
    assert classify(12, {"served_profiles": []}, []) == "STANDALONE_OR_INCOMPLETE_MULTIPLEX"
    assert classify(12, {}, ["default"]) == "READY"
    assert classify(12, {}, ["default", "reviewer", "coder", "orchestrator"]) == "LEGACY_ROLE_PROFILES_STILL_SERVED"
    assert classify(None, {"served_profiles": list(REQUIRED)}, list(REQUIRED)) == "NO_VERIFIED_LIVE_GATEWAY"
    single = {"pid": 12, "gateway_state": "running",
              "multiplex_standalone_reason": "only one profile exists (nothing to multiplex)"}
    assert classify(12, single, []) == "READY"
    assert classify(None, single, []) == "NO_VERIFIED_LIVE_GATEWAY"
    assert classify(13, single, []) == "STANDALONE_OR_INCOMPLETE_MULTIPLEX"
    assert classify(12, dict(single, gateway_state="starting"), []) != "READY"
    assert classify(12, dict(single, gateway_state="stopped"), []) != "READY"
    assert classify(12, dict(single, multiplex_standalone_reason="unknown"), []) != "READY"
    assert classify(12, single, ["coder"]) == "LEGACY_ROLE_PROFILES_STILL_SERVED"
    print("PASS: live default standalone/multiplex readiness and stale PID rejection")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--wait-seconds", type=float, default=60)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
    else:
        raise SystemExit(wait_ready(args.wait_seconds))

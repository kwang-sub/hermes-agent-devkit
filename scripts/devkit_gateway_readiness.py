#!/usr/bin/env python3
"""Read-only readiness probe for the live default Hermes multiplex Gateway.

Never treats s6 'up', configuration, or a stale PID as proof of serving profiles.
A bounded control-socket profile rescan is attempted only for an authenticated
live multiplexer, not for a standalone/missing Gateway.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REQUIRED = frozenset(("default", "coder", "orchestrator", "reviewer"))


def classify(live_pid, record, served, expected=REQUIRED):
    record = record if isinstance(record, dict) else {}
    if live_pid is None:
        return "NO_VERIFIED_LIVE_GATEWAY"
    if served is None:
        return "SERVED_PROFILE_RECORD_UNAVAILABLE"
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
        print("Gateway may be standalone or incompletely migrated. Inspect 'hermes gateway migrate --multiplex' plan and gateway logs.", file=sys.stderr)
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
            print("PASS: verified live Gateway serves default/coder/orchestrator/reviewer")
            return 0
        if pid is not None and not rescanned and served is not None and "default" in served:
            # Ask the actual live multiplexer to refresh its profile inventory.
            # This is an in-memory profile rescan, not a service restart/migration.
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
    assert classify(12, {}, ["default"]) == "STANDALONE_OR_INCOMPLETE_MULTIPLEX"
    assert classify(12, {}, ["default", "reviewer", "coder", "orchestrator"]) == "READY"
    assert classify(None, {"served_profiles": list(REQUIRED)}, list(REQUIRED)) == "NO_VERIFIED_LIVE_GATEWAY"
    print("PASS: gateway readiness identity and served-profile contract fixtures")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--wait-seconds", type=float, default=60)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
    else:
        raise SystemExit(wait_ready(args.wait_seconds))

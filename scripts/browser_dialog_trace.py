#!/usr/bin/env python3
"""Classify redacted browser dialog event traces; never launch/modify a provider."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

def _event(record):
    if not isinstance(record, dict):
        return "", {}
    return str(record.get("method", "")), record.get("params", {}) if isinstance(record.get("params"), dict) else {}

def analyze(data):
    """Inspect a single attempt; require explicit response evidence for PASS."""
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError("events array is required")
    events = data["events"]
    opened = [(i, e, p) for i, e0 in enumerate(events) for e, p in [_event(e0)]
              if e == "Page.javascriptDialogOpening" and p.get("type") == "beforeunload"]
    if not opened:
        classification = "NO_BEFOREUNLOAD_EVENT"
        state = "INCONCLUSIVE"
    else:
        ix, _, opening_params = opened[-1]
        opened_entry = events[ix]
        sid = opened_entry.get("sessionId", "")
        closed = [(j, p) for j, e0 in enumerate(events[ix + 1:], ix + 1)
                  for e, p in [_event(e0)]
                  if e == "Page.javascriptDialogClosed" and e0.get("sessionId") == sid]
        dismiss = data.get("dismiss")
        # Do not infer response ordering from the event array alone; require
        # timestamps of dispatch and close from a single monotonic clock.
        sent_at = dismiss.get("sent_at") if isinstance(dismiss, dict) else None
        opening_at = opened_entry.get("time")
        closing_at = events[closed[0][0]].get("time") if closed else None
        if closed and sent_at is None:
            classification = "CLOSED_WITHOUT_RECORDED_RESPONSE"
            state = "BLOCKED_ENV"
        elif closed and all(type(t) in (float, int) and math.isfinite(t) for t in (opening_at, sent_at, closing_at)) and closing_at < sent_at:
            classification = "CLOSED_BEFORE_RESPONSE"
            state = "BLOCKED_ENV"
        elif (closed and isinstance(dismiss, dict) and dismiss.get("success") is True
              and closed[0][1].get("result") is False
              and all(type(t) in (float,int) and math.isfinite(t) for t in (opening_at,sent_at,closing_at))
              and opening_at <= sent_at <= closing_at
              and sid and (not opening_params.get("frameId") or
                           opening_params["frameId"] == closed[0][1].get("frameId"))
              and data.get("page_preserved") is True and data.get("input_preserved") is True):
            classification = "DISMISS_AND_PRESERVATION_CONFIRMED"
            state = "PASS"
        else:
            classification = "DIALOG_RESPONSE_UNCONFIRMED"
            state = "INCONCLUSIVE"
    provider = str(data.get("provider", "unknown"))
    capability = "beforeunload-dismiss"
    signature = classification
    digest = hashlib.sha256(json.dumps([provider, capability, signature], separators=(",", ":")).encode()).hexdigest()[:16]
    return {"schema": "browser_dialog_diagnostic_v1", "provider": provider,
            "capability": capability, "classification": classification,
            "execution_status": state, "recovery_fingerprint": digest,
            "next_action": ("STOP_RETRY_ESCALATE" if state == "BLOCKED_ENV"
                            else "REVIEW_EVIDENCE" if state == "INCONCLUSIVE"
                            else "CONTINUE_PRODUCT_VERIFICATION")}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(json.loads(args.input.read_text(encoding="utf-8-sig")))
        payload = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 0 if result["execution_status"] == "PASS" else 2
    except (ValueError, OSError) as exc:
        print("BROWSER_DIALOG_DIAGNOSTIC=INVALID_INPUT: " + str(exc))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

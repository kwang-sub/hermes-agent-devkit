"""One final outcome, with consistent status, action and retry identity."""
from __future__ import annotations
import hashlib
import json
import math

STATES = {'PASS', 'FAIL', 'NOT_RUN', 'INCONCLUSIVE', 'BLOCKED_ENV', 'UNSUPPORTED'}


def positive_seconds(value: float, name: str = 'timeout') -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')
    return float(value)


def outcome(status: str, classification: str, *, provider: str = 'browser_exec',
            capability: str = 'ui-verification', environment: str = '',
            failed_phase: str = '') -> dict:
    if status not in STATES or not classification:
        raise ValueError('invalid verification outcome')
    identity = [provider, capability, classification, failed_phase]
    digest = lambda value: hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()[:16]
    return {
        'execution_status': status, 'classification': classification,
        'next_action': ('REVIEW_EVIDENCE' if provider in ('cdp-test', 'policy-model') else
                        'CONTINUE_PRODUCT_VERIFICATION' if status == 'PASS' else
                        'FIX_VERIFIED_BEHAVIOR' if status == 'FAIL' else
                        'STOP_RETRY_ESCALATE' if status == 'BLOCKED_ENV' else 'REVIEW_EVIDENCE'),
        # Error grouping and permission to retry are deliberately different keys.
        'recovery_fingerprint': digest(identity),
        'retry_fingerprint': digest([identity, environment]),
    }


def replace_outcome(report: dict, status: str, classification: str) -> None:
    report.update(outcome(status, classification, provider=report.get('provider', 'browser_exec'),
                          capability=report.get('capability', 'ui-verification'),
                          environment=report.get('environment_fingerprint', ''),
                          failed_phase=report.get('failed_phase', '')))

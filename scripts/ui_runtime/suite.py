"""Checkpointed checks, dependency-local blocking and explicit completion."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import time
from .artifacts import atomic_json, attempt_directory
from .result import STATES, outcome

KINDS = {'functional', 'accessibility', 'responsive', 'visual', 'static', 'capability', 'integration'}


class Unsupported(RuntimeError):
    """The approved provider does not expose a requested optional operation."""


class EnvironmentBlocked(RuntimeError):
    """Infrastructure prevented verification; not an application assertion."""


def aggregate(checks: list[dict], required: list[str], cleanup: dict) -> dict:
    by_id = {c['id']: c for c in checks}
    if len(by_id) != len(checks) or len(set(required)) != len(required):
        raise ValueError('duplicate verification ID')
    outstanding = [key for key in required if by_id.get(key, {}).get('status') != 'PASS']
    failed = [key for key in required if by_id.get(key, {}).get('status') == 'FAIL']
    optional_outstanding = [c['id'] for c in checks
                            if c['id'] not in required and c['status'] != 'PASS']
    if not required:
        status, reason = 'NOT_RUN', 'NO_REQUIRED_CHECKS'
    elif failed:
        status, reason = 'FAIL', 'REQUIRED_ASSERTION_FAILED'
    elif outstanding:
        status, reason = 'INCONCLUSIVE', 'REQUIRED_CHECKS_OUTSTANDING'
    elif cleanup.get('status') != 'PASS':
        status, reason = 'INCONCLUSIVE', 'CLEANUP_UNCONFIRMED'
    else:
        status, reason = 'PASS', 'REQUIRED_CHECKS_CONFIRMED'
    return {**outcome(status, reason), 'verification_final': status == 'PASS',
            'required_outstanding': outstanding, 'failed_checks': failed,
            'optional_outstanding': optional_outstanding}


def validate_report(data: dict) -> None:
    if not isinstance(data, dict) or data.get('schema') != 'ui_verification_v1':
        raise ValueError('UI verification schema required')
    if not isinstance(data.get('scope'), str) or not data['scope'].strip():
        raise ValueError('UI verification scope required')
    required, checks = data.get('required'), data.get('checks')
    if not isinstance(required, list) or not isinstance(checks, list):
        raise ValueError('required plan and checks must be arrays')
    if any(not isinstance(k, str) or not k.strip() for k in required):
        raise ValueError('invalid required check ID')
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get('id'), str) or not check['id']:
            raise ValueError('invalid check')
        if check.get('status') not in STATES:
            raise ValueError('invalid check status')
        if check['status'] == 'PASS' and (not isinstance(check.get('evidence'), str) or not check['evidence'].strip()):
            raise ValueError('check PASS requires evidence')
    if not isinstance(data.get('cleanup'), dict) or data['cleanup'].get('status') not in ('PASS', 'WARNING', 'NOT_RUN'):
        raise ValueError('invalid cleanup')
    aggregate(checks, required, data['cleanup'])


class Suite:
    def __init__(self, root: Path, *, task_id: str, required: list[str], scope: str,
                 provider: str = 'browser_exec', environment: dict | None = None):
        if not task_id or not scope or any(not isinstance(k, str) or not k for k in required):
            raise ValueError('task, scope and required check IDs are mandatory')
        if len(set(required)) != len(required):
            raise ValueError('duplicate required check ID')
        self.directory = attempt_directory(root)
        self.required = list(required)
        self.report = {'schema': 'ui_verification_v1', 'task_id': task_id,
                       'provider': provider, 'scope': scope, 'environment': environment or {},
                       'started_at': datetime.now(timezone.utc).isoformat(),
                       'required': self.required, 'checks': [], 'cleanup': {'status': 'NOT_RUN'}}
        self.save()

    def save(self):
        self.report.update(aggregate(self.report['checks'], self.required, self.report['cleanup']))
        self.report['environment_fingerprint'] = hashlib.sha256(json.dumps(
            self.report['environment'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.report.update(outcome(self.report['execution_status'], self.report['classification'],
                                   provider=self.report['provider'],
                                   environment=self.report['environment_fingerprint']))
        atomic_json(self.directory / 'ui-report.json', self.report)

    def check(self, key: str, kind: str, callback, *, depends=(), context=None, observe=None) -> dict:
        if kind not in KINDS or not key or any(c['id'] == key for c in self.report['checks']):
            raise ValueError('unknown check kind or duplicate ID')
        known = {c['id']: c for c in self.report['checks']}
        entry = {'id': key, 'kind': kind, 'criticality': 'REQUIRED' if key in self.required else 'OPTIONAL',
                 'status': 'NOT_RUN', 'context': context or {},
                 'depends': list(depends), 'evidence': '', 'started_at': time.monotonic()}
        self.report['checks'].append(entry)
        self.save()  # A crash must not erase the attempted check or earlier results.
        missing = [dep for dep in depends if known.get(dep, {}).get('status') != 'PASS']
        if missing:
            entry.update(reason='PREREQUISITE_UNVERIFIED', blocked_by=missing)
        else:
            self._execute(entry, callback)
        if observe is not None:
            try: entry['diagnostics'] = observe()
            except Exception as exc: entry['diagnostics'] = {'collector_error': type(exc).__name__}
        entry['duration_s'] = time.monotonic() - entry.pop('started_at')
        atomic_json(self.directory / ('check-' + str(len(self.report['checks'])) + '.json'), entry)
        self.save()
        return entry

    @staticmethod
    def _execute(entry, callback):
        try:
            value = callback()
            if value is True:
                value = {'status': 'PASS', 'evidence': 'Observed assertion returned true'}
            elif value is False:
                value = {'status': 'FAIL', 'evidence': 'Observed assertion returned false'}
            if not isinstance(value, dict) or value.get('status') not in STATES:
                raise ValueError('check must return a measured result')
            evidence = value.get('evidence') or value.get('path')
            if value['status'] == 'PASS' and not evidence:
                raise ValueError('PASS needs an observation or artifact reference')
            entry.update(status=value['status'], evidence=evidence or '', detail=value)
        except AssertionError:
            entry.update(status='FAIL', reason='ASSERTION_FAILED', evidence='Assertion evaluated false')
        except Unsupported:
            entry.update(status='UNSUPPORTED', reason='PROVIDER_CAPABILITY_UNAVAILABLE')
        except EnvironmentBlocked:
            entry.update(status='BLOCKED_ENV', reason='EXECUTION_ENVIRONMENT_BLOCKED')
        except Exception as exc:
            entry.update(status='INCONCLUSIVE', reason='CHECK_EXECUTION_FAILED', error_type=type(exc).__name__)

    def finish(self, cleanup: dict) -> dict:
        if cleanup.get('status') not in ('PASS', 'WARNING', 'NOT_RUN'):
            raise ValueError('invalid cleanup state')
        self.report['cleanup'] = cleanup
        self.report['finished_at'] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.report

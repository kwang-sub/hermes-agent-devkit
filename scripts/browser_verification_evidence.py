#!/usr/bin/env python3
"""Validate evidence structure; report completion only against an explicit AC plan."""
import argparse
import json
from pathlib import Path
from ui_runtime.suite import aggregate

AC_STATES = {'PASS', 'FAIL', 'NOT_RUN'}
RUN_STATES = AC_STATES | {'BLOCKED_ENV', 'UNSUPPORTED', 'INCONCLUSIVE'}
REQUIRED = {'schema', 'task_id', 'provider', 'session', 'verified_at',
            'capabilities', 'acceptance_criteria', 'cleanup'}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate(data):
    if not isinstance(data, dict) or not REQUIRED.issubset(data):
        raise ValueError('missing evidence fields')
    if data['schema'] != 'browser_verification_v1':
        raise ValueError('unsupported schema')
    for key in ('task_id', 'provider', 'session', 'verified_at'):
        if not _text(data[key]):
            raise ValueError('invalid ' + key)
    if not isinstance(data['capabilities'], list) or not isinstance(data['acceptance_criteria'], list):
        raise ValueError('capabilities and acceptance_criteria must be arrays')
    caps = {}
    for cap in data['capabilities']:
        if not isinstance(cap, dict) or not _text(cap.get('name')) or cap['name'] in caps:
            raise ValueError('duplicate/invalid capability')
        caps[cap['name']] = cap
        if cap.get('status') not in AC_STATES or cap.get('execution_status') not in RUN_STATES:
            raise ValueError('invalid capability result')
        expected = cap['execution_status'] if cap['execution_status'] in AC_STATES else 'NOT_RUN'
        if cap['status'] != expected:
            raise ValueError('capability status contradicts execution status')
        if not isinstance(cap.get('evidence'), str) or (cap['status'] == 'PASS' and not _text(cap['evidence'])):
            raise ValueError('PASS requires nonempty capability evidence')
    seen = set()
    for ac in data['acceptance_criteria']:
        if not isinstance(ac, dict) or not _text(ac.get('ac_id')) or ac['ac_id'] in seen:
            raise ValueError('invalid/duplicate AC ID')
        seen.add(ac['ac_id'])
        if ac.get('status') not in AC_STATES or ac.get('capability') not in caps:
            raise ValueError('invalid AC result/capability')
        if not _text(ac.get('method')) or not isinstance(ac.get('evidence'), str):
            raise ValueError('missing AC method/evidence')
        if ac['status'] == 'PASS' and (caps[ac['capability']]['status'] != 'PASS' or not _text(ac['evidence'])):
            raise ValueError('AC PASS requires capability PASS and evidence')
    if not isinstance(data['cleanup'], dict) or data['cleanup'].get('status') not in ('PASS', 'WARNING', 'NOT_RUN'):
        raise ValueError('invalid cleanup status')
    # A supplied summary may not contradict even the checks present in the file.
    if data.get('verification_final') is True:
        if not seen or any(ac['status'] != 'PASS' for ac in data['acceptance_criteria']) or data['cleanup']['status'] != 'PASS':
            raise ValueError('verification_final contradicts recorded evidence')
    return True


def completion(data, required_ac_ids):
    validate(data)
    if not isinstance(required_ac_ids, list) or any(not _text(v) for v in required_ac_ids):
        raise ValueError('required AC plan must be an array of IDs')
    return aggregate([{'id': ac['ac_id'], 'status': ac['status']} for ac in data['acceptance_criteria']],
                     required_ac_ids, data['cleanup'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--required-acs', type=Path, help='Approved JSON array of required AC IDs')
    args = parser.parse_args()
    try:
        data = json.loads(args.path.read_text(encoding='utf-8-sig'))
        validate(data)
        print('BROWSER_EVIDENCE_STATUS=PASS')  # Kept for existing structure-only callers.
        print('BROWSER_EVIDENCE_STRUCTURE=VALID')
        if args.required_acs is None:
            print('BROWSER_VERIFICATION_COMPLETION=NOT_EVALUATED')
            return 0
        result = completion(data, json.loads(args.required_acs.read_text(encoding='utf-8-sig')))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['verification_final'] else 2
    except (ValueError, OSError, TypeError) as exc:
        print('BROWSER_EVIDENCE_STATUS=FAIL')
        print('BROWSER_EVIDENCE_REASON=' + type(exc).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

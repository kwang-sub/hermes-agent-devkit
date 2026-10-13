#!/usr/bin/env python3
"""Strict capability evidence, separate from product acceptance and fixture models."""
from __future__ import annotations
import math
import hashlib
from ui_runtime.result import outcome

EXPECTED={(s,a) for s in ('reload','navigate','confirm') for a in ('dismiss','accept')}


def _time(value):
    return type(value) in (int,float) and math.isfinite(value)


def summarize(data):
    def result(status, reason, next_action):
        return outcome(status, reason, capability='managed-native-dialog-v1')
    def blocked(reason):
        return result('INCONCLUSIVE',reason,'REVIEW_EVIDENCE')
    if not isinstance(data,dict) or data.get('schema')!='managed_dialog_probe_v1':
        raise ValueError('managed dialog report schema is required')
    if data.get('mode')!='hermes' or data.get('source_policy_model') is not False:
        return blocked('OFFICIAL_RESPONSE_PATH_NOT_TESTED')
    cases=data.get('cases')
    if isinstance(cases,list):
        for case in cases:
            if not isinstance(case,dict): raise ValueError('invalid case')
            if case.get('closed_before_response') is True:
                return result('BLOCKED_ENV','CLOSED_BEFORE_RESPONSE','STOP_RETRY_ESCALATE')
            if case.get('result')=='BLOCKED' and case.get('failed_phase'):
                phase=case['failed_phase']
                known={'prepare','managed_launch','chromium_launch','agent_browser_attach',
                       'target_match','fixture_ready','activate','trigger','opening','respond','closed'}
                if not isinstance(phase,str) or phase not in known: phase='unknown'
                reasons={'target_match':'FIXTURE_TARGET_UNCONFIRMED', 'fixture_ready':'FIXTURE_NOT_READY'}
                summary=blocked(reasons.get(phase,'MANAGED_PROBE_BLOCKED'))
                summary['failed_phase']=phase
                key=(case.get('scenario'),case.get('action'))
                if all(isinstance(v,str) for v in key) and key in EXPECTED:
                    summary['failed_case']='/'.join(key)
                return summary
            # Only an actually executed, explicitly answered assertion can be FAIL.
            response=case.get('response')
            if (case.get('result')=='FAIL' and isinstance(response,dict)
                    and response.get('success') is True
                    and case.get('response_owner')=='hermes.browser_dialog'
                    and isinstance(case.get('final'),dict) and case.get('final')):
                return result('FAIL','MANAGED_DIALOG_ASSERTION_FAILED','FIX_VERIFIED_BEHAVIOR')
    if data.get('complete_matrix') is not True:
        return blocked('INCOMPLETE_DIALOG_MATRIX')
    cases=data.get('cases')
    if not isinstance(cases,list) or len(cases)!=len(EXPECTED):
        return blocked('INCOMPLETE_DIALOG_MATRIX')
    seen=set()
    for case in cases:
        if not isinstance(case,dict): raise ValueError('invalid case')
        key=(case.get('scenario'),case.get('action'))
        if not all(isinstance(x,str) for x in key): return blocked('INVALID_CASE_ID')
        if any(not isinstance(case.get(k,{}),dict) for k in ('response','initial','final','cleanup')):
            return blocked('INVALID_CASE_STRUCTURE')
        if key not in EXPECTED or key in seen: return blocked('DUPLICATE_OR_UNKNOWN_CASE')
        seen.add(key)
        if case.get('closed_before_response') is True:
            return result('BLOCKED_ENV','CLOSED_BEFORE_RESPONSE','STOP_RETRY_ESCALATE')
        if (case.get('result')!='PASS' or case.get('automatic_control') is not False
                or case.get('response_owner')!='hermes.browser_dialog'
                or case.get('effective_no_auto_dialog')!='1'
                or case.get('cleanup',{}).get('status')!='PASS'):
            return blocked('OFFICIAL_DIALOG_CASE_UNVERIFIED')
        response=case.get('response',{})
        initial=case.get('initial',{}); final=case.get('final',{})
        if (response.get('success') is not True or response.get('action')!=key[1]
                or not isinstance(response.get('dialog_id'),str) or not response['dialog_id']
                or initial.get('activated') is not True or initial.get('dirty') is not True
                or initial.get('input')!='SAMPLE' or not initial.get('docId')):
            return blocked('DIALOG_RESPONSE_EVIDENCE_MISSING')
        accepted=key[1]=='accept'
        if case.get('dialog_result') is not accepted: return blocked('DIALOG_RESULT_MISMATCH')
        if key[0]=='confirm' and final.get('answer') is not accepted:
            return blocked('CONFIRM_VALUE_UNCONFIRMED')
        if not isinstance(final.get('path'),str):
            return blocked('FINAL_DOCUMENT_EVIDENCE_MISSING')
        keep=key[0]=='confirm' or not accepted
        if keep:
            if (case.get('page_preserved') is not True or case.get('input_preserved') is not True
                    or final.get('docId')!=initial['docId'] or final.get('input')!='SAMPLE'
                    or final.get('path')!=initial.get('path')):
                return blocked('INPUT_OR_DOCUMENT_NOT_PRESERVED')
        elif ('docId' not in final or final['docId'] is None
              or final.get('docId')==initial['docId'] or case.get('page_preserved') is not False):
            return blocked('NAVIGATION_NOT_CONFIRMED')
        if not keep and key[0]=='navigate' and final['path']!='/next':
            return blocked('NAVIGATION_NOT_CONFIRMED')
        if not keep and key[0]=='reload' and (not final.get('docId') or final['path']!=initial.get('path')):
            return blocked('NAVIGATION_NOT_CONFIRMED')
        events=case.get('events',[])
        if not isinstance(events,list): raise ValueError('events must be an array')
        if key[0]=='confirm' and case.get('capture_kind')=='hermes-bridge':
            if final.get('answer') is not accepted: return blocked('CONFIRM_VALUE_UNCONFIRMED')
            opening=[e for e in events if isinstance(e,dict) and e.get('method')=='Hermes.dialogPending']
            closing=[e for e in events if isinstance(e,dict) and e.get('method')=='Hermes.dialogResponded']
        else:
            sid=case.get('observer_session_id')
            if not isinstance(sid,str) or not sid: return blocked('OBSERVER_SESSION_MISSING')
            opening=[e for e in events if isinstance(e,dict) and e.get('method')=='Page.javascriptDialogOpening' and e.get('sessionId')==sid]
            closing=[e for e in events if isinstance(e,dict) and e.get('method')=='Page.javascriptDialogClosed' and e.get('sessionId')==sid]
            if len(opening)!=1 or len(closing)!=1: return blocked('NATIVE_DIALOG_EVENTS_MISSING')
            kind='confirm' if key[0]=='confirm' else 'beforeunload'
            op=opening[0].get('params',{}); cl=closing[0].get('params',{})
            if (op.get('type')!=kind or not op.get('frameId') or op.get('frameId')!=cl.get('frameId')
                    or cl.get('result') is not accepted):
                return blocked('DIALOG_FRAME_OR_RESULT_MISMATCH')
        if len(opening)!=1 or len(closing)!=1: return blocked('DIALOG_EVENTS_MISSING')
        timestamps=(opening[0].get('time'),response.get('sent_at'),closing[0].get('time'))
        if not all(_time(v) for v in timestamps) or not timestamps[0]<=timestamps[1]<=timestamps[2]:
            return blocked('RESPONSE_ORDER_UNCONFIRMED')
    return result('PASS','MANAGED_DIALOG_CAPABILITY_CONFIRMED','CONTINUE_PRODUCT_VERIFICATION')

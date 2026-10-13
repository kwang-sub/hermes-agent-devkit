"""Bounded, scoped diagnostics without page text, URLs, cookies, or console arguments."""
from collections import deque


class Diagnostics:
    def __init__(self, session_id: str, limit=100):
        self.session_id = session_id
        self.records = deque(maxlen=limit)
        self.dropped = 0

    def feed(self, event: dict):
        if event.get('sessionId', event.get('session_id')) != self.session_id:
            return
        method, params = event.get('method'), event.get('params') or {}
        if method not in {'Runtime.exceptionThrown', 'Log.entryAdded', 'Network.loadingFailed', 'Network.responseReceived'}:
            return
        status = params.get('response', {}).get('status')
        if method == 'Network.responseReceived' and (not isinstance(status, (int,float)) or status < 400):
            return
        record = {'method': method}
        if method == 'Network.responseReceived': record['http_status'] = status
        if method == 'Network.loadingFailed': record['canceled'] = params.get('canceled') is True
        if method == 'Log.entryAdded': record['level'] = params.get('entry', {}).get('level', 'unknown')
        if len(self.records) == self.records.maxlen: self.dropped += 1
        self.records.append(record)

    def snapshot(self):
        return {'events': list(self.records), 'dropped': self.dropped,
                'scope': 'diagnostic only; expected errors are not automatic test failures'}

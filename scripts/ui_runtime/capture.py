"""Scoped screenshot capture. A saved PNG is not a visual approval."""
from __future__ import annotations
import base64
import binascii
from dataclasses import dataclass
from pathlib import Path
import struct
import time
import uuid
import zlib
from .artifacts import file_digest, inside
from .result import positive_seconds


@dataclass(frozen=True)
class TimeBudget:
    action: float = 10
    navigation: float = 20
    capture: float = 60
    transport_margin: float = 15

    def __post_init__(self):
        for name in ('action', 'navigation', 'capture', 'transport_margin'):
            positive_seconds(getattr(self, name), name)

    def outer(self, inner: float) -> float:
        return positive_seconds(inner) + self.transport_margin


def png_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('capture is not PNG')
    offset, size, seen_data, ended = 8, None, False, False
    while offset + 12 <= len(data):
        length = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError('truncated PNG')
        payload = data[offset + 8:offset + 8 + length]
        checksum = struct.unpack('>I', data[end - 4:end])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != checksum:
            raise ValueError('corrupt PNG chunk')
        if kind == b'IHDR':
            if offset != 8 or length != 13:
                raise ValueError('invalid PNG header')
            size = struct.unpack('>II', payload[:8])
        seen_data |= kind == b'IDAT' and bool(payload)
        offset = end
        if kind == b'IEND':
            ended = length == 0 and offset == len(data)
            break
    if not size or not all(size) or not seen_data or not ended:
        raise ValueError('incomplete PNG')
    return size


def capture(page, directory: Path, *, full_page: bool = False,
            recovery=None, visual_ready=None) -> dict:
    """At most one explicit recovery retry, never silently change capture scope."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    attempts = []
    for index in range(2 if recovery else 1):
        started = time.monotonic()
        try:
            page.activate()  # Activates this owned target, not a daemon default tab.
            if visual_ready is not None:
                visual_ready(page)
            params = {'format': 'png', 'captureBeyondViewport': full_page}
            if full_page:
                metrics = page.call('Page.getLayoutMetrics')
                size = metrics.get('cssContentSize') or metrics.get('contentSize')
                if not size or size.get('width', 0) <= 0 or size.get('height', 0) <= 0:
                    raise ValueError('page capture dimensions unavailable')
                params['clip'] = {k: size[k] for k in ('x', 'y', 'width', 'height')}
                params['clip']['scale'] = 1
            response = page.call('Page.captureScreenshot', params, timeout=page.budget.capture)
            data = base64.b64decode(response['data'], validate=True)
            width, height = png_dimensions(data)
            path = inside(directory, directory / ('capture-' + uuid.uuid4().hex + '.png'))
            with path.open('xb') as output:
                output.write(data)
            attempts.append({'status': 'PASS', 'duration_s': time.monotonic() - started})
            return {'status': 'PASS', 'path': str(path), 'sha256': file_digest(path),
                    'width': width, 'height': height, 'full_page': full_page,
                    'target_id': page.target_id, 'viewport': dict(page.viewport_state),
                    'visual_review': 'NOT_RUN', 'attempts': attempts}
        except (TimeoutError, OSError, ValueError, RuntimeError, KeyError, binascii.Error) as exc:
            attempts.append({'status': 'INCONCLUSIVE', 'error': type(exc).__name__,
                             'duration_s': time.monotonic() - started})
            if index or recovery is None or not page.healthy():
                break
            # No implicit replay of navigation, submit, or another mutable action.
            if recovery(page) is not True:
                break
    return {'status': 'INCONCLUSIVE', 'classification': 'CAPTURE_UNCONFIRMED',
            'full_page': full_page, 'attempts': attempts, 'visual_review': 'NOT_RUN'}

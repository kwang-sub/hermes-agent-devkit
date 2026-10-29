"""Render only a Lite approval brief through Hermes' native assistant renderer.

This is a presentation adapter, not consent detection. No theme/palette is
copied, no conversation entry is appended and no turn is completed here.
"""
from __future__ import annotations

import re
from types import SimpleNamespace


def is_approval_brief(text: object) -> bool:
    """Find the two ordered standalone headings, never quoted/fenced examples."""
    if not isinstance(text, str):
        return False
    headings = []
    fence = None
    for line in text.splitlines():
        # Four-space/tab-indented blocks and blockquotes are examples, not a brief.
        if line.startswith(('    ', '\t')):
            continue
        line = line.strip()
        if line.startswith(('```', '~~~')):
            marker = line[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence or line.startswith('>'):
            continue
        line = re.sub(r'^#{1,6}\s+', '', line)
        line = re.sub(r'\s+#+$', '', line).strip()
        if line.startswith('**') and line.endswith('**'):
            line = line[2:-2].strip()
        if line in ('구현 계획', '사용 스킬'):
            headings.append(line)
    return headings == ['구현 계획', '사용 스킬']


class _MessageView:
    """Read-only presentation view: reuse the real renderer without turn flags.

    A prior segment/TTS/interrupt must not suppress a NEW interim brief. These
    display-only values do not overwrite the live CLI's streaming or turn state.
    Theme, markdown mode, width and layout remain owned by the actual CLI.
    """
    _last_turn_interrupted = False
    _stream_started = False
    _stream_box_opened = False
    _streamed_text_this_turn = ''

    def __init__(self, cli):
        object.__setattr__(self, '_cli', cli)

    def __getattr__(self, name):
        return getattr(self._cli, name)

    def __setattr__(self, name, value):
        raise AttributeError('Approval rendering cannot mutate live CLI state')


def render_interim(cli, text, *, already_streamed=False) -> None:
    """Gateway interim callback; ordinary progress retains its native log path."""
    if not isinstance(text, str) or not text.strip():
        return
    if not is_approval_brief(text):
        cli._agent_status_print(text)
        return
    # An upstream 'streamed' bit alone is insufficient: this viewer may have
    # streaming disabled. Suppress only when the text was really displayed here.
    shown = getattr(cli, '_streamed_text_this_turn', '') or ''
    if (already_streamed and isinstance(shown, str)
            and ' '.join(text.split()) in ' '.join(shown.split())):
        return
    cli._flush_stream()  # close buffered native stream/reasoning before the panel
    turn = SimpleNamespace(result={}, use_streaming_tts=False, box_opened=False)
    # Call the actual normal-response renderer, not a manually colored copy.
    # This honors active skin, light mode, classic/modern and raw/strip/Markdown.
    type(cli)._chat_print_response_panel(_MessageView(cli), turn, text)


def make_callback(cli):
    def callback(text, *, already_streamed=False):
        return render_interim(cli, text, already_streamed=already_streamed)
    return callback

"""Theme-aware presentation only; never interprets or grants development approval.

Approval plans arrive as interim messages before Clarify. Use the same content
renderer, skin, layout and console as normal Hermes replies, not status stdout.
"""
from __future__ import annotations
import re


def is_plan_brief(text: str) -> bool:
    """Recognize the two ordered standalone headings, never a fenced example."""
    if not isinstance(text, str):
        return False
    headings = []
    fence = None
    for line in text.splitlines():
        value = line.strip()
        if value.startswith(('```', '~~~')):
            marker = value[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence:
            continue
        value = re.sub(r'^#{1,6}\s+', '', value)
        if value.startswith('**') and value.endswith('**'):
            value = value[2:-2].strip()
        if value in ('구현 계획', '사용 스킬'):
            headings.append(value)
    return headings == ['구현 계획', '사용 스킬']


def response_style():
    """Resolve the live skin at call time, including native light-mode mapping."""
    from cli import _maybe_remap_for_light_mode
    # These fallbacks are the native _chat_print_response_panel defaults, not a
    # DevKit palette. Normally every value comes from the active skin.
    try:
        from hermes_cli.skin_engine import get_active_skin
        skin = get_active_skin()
        label = skin.get_branding('response_label', '☤ Hermes')
        border = skin.get_color('response_border', '#CD7F32')
        text = skin.get_color('banner_text', '#FFF8DC')
    except Exception:
        label, border, text = '☤ Hermes', '#CD7F32', '#FFF8DC'
    return (label, _maybe_remap_for_light_mode(border),
            _maybe_remap_for_light_mode(text))


def render_interim(cli, text, *, already_streamed=False):
    """Only approval briefs use chat presentation; ordinary progress is unchanged."""
    if not isinstance(text, str) or not text.strip():
        return
    if not is_plan_brief(text):
        cli._agent_status_print(text)
        return
    # Gateway closes an already displayed streaming segment before this callback.
    # Without a local streaming consumer, a remote 'already_streamed' is not proof.
    if already_streamed and getattr(cli, 'streaming_enabled', False):
        return
    from cli import ChatConsole, _cprint, _render_final_assistant_content
    from rich import box
    from rich.panel import Panel
    label, border, body = response_style()
    content = _render_final_assistant_content(text, mode=cli.final_response_markdown)
    if getattr(cli, '_modern_layout', False):
        from hermes_cli.cli_modern_layout import answer_label, closing_separator
        _cprint(answer_label())
        ChatConsole().print(content, style=body, soft_wrap=True)
        _cprint(closing_separator(True))
    else:
        ChatConsole().print(Panel(content, title=f'[{border} bold]{label}[/]',
                                 title_align='left', border_style=border, style=body,
                                 box=box.HORIZONTALS, padding=(1, 0),
                                 width=cli._scrollback_box_width()))


def approval_fragments(state, fragments):
    """Recolor native approval rows only; preserve text, layout and mouse handlers."""
    if not isinstance(state, dict):
        return fragments
    entries = state.get('questions')
    index = state.get('active', 0)
    entry = (entries[index] if isinstance(entries, list) and isinstance(index, int)
             and 0 <= index < len(entries) else state)
    if not isinstance(entry, dict) or entry.get('devkit_approval') is not True:
        return fragments
    # Appearance must not break an otherwise valid approval response on headless
    # test surfaces. Production's skin API is checked by the installation test.
    try:
        _, border, body = response_style()
    except (ImportError, AttributeError):
        return fragments
    styles = {
        'class:clarify-border': border,
        'class:clarify-title': f'{border} bold',
        'class:clarify-question': f'{body} bold',
        'class:clarify-choice': body,
        'class:clarify-selected': f'{border} bold',
        'class:clarify-recommended': f'{border} bold',
        'class:clarify-active-other': f'{body} italic',
        'class:clarify-answer': body,
    }
    return [(styles.get(row[0], row[0]), *row[1:]) for row in fragments]

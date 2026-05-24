#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

"""
Keymap filter kitten – an interactive TUI that lets you search/filter all
kitty keybindings as you type.

Usage in kitty.conf:
    map kitty_mod+/ kitten keymap_filter

Navigation:
    Type        – filter the list in real time
    ↑ / ↓       – move selection up / down
    ctrl+u      – clear the filter
    Enter       – copy the selected key-combo to clipboard
    Esc / q     – quit without copying
    ctrl+c      – quit without copying
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kitty.fast_data_types import get_options, wcswidth
from kitty.key_encoding import EventType
from kitty.typing_compat import BossType, KeyEventType, ScreenSize

from ..tui.handler import Handler, result_handler
from ..tui.line_edit import LineEdit
from ..tui.loop import Loop
from ..tui.operations import (
    clear_screen,
    colored,
    set_cursor_position,
    styled,
)

if TYPE_CHECKING:
    pass


# ─────────────────────────── data model ───────────────────────────────────── #

class KeyEntry:
    """One resolved keybinding: key-combo string → action string."""

    __slots__ = ('key_repr', 'action', 'mode', 'lower')

    def __init__(self, key_repr: str, action: str, mode: str = '') -> None:
        self.key_repr = key_repr
        self.action   = action
        self.mode     = mode          # '' = default mode, else named mode
        self.lower    = (key_repr + ' ' + action + ' ' + mode).lower()

    def matches(self, query: str) -> bool:
        """Return True when every space-separated token appears in the entry."""
        if not query:
            return True
        return all(tok in self.lower for tok in query.lower().split())

    def display(self, key_width: int, act_width: int, selected: bool = False) -> str:
        key_part = self.key_repr.ljust(key_width)[:key_width]
        act_part = self.action.ljust(act_width)[:act_width]
        mode_tag = f'  [{self.mode}]' if self.mode else ''
        line = f'{key_part}  →  {act_part}{mode_tag}'
        if selected:
            return styled(line, fg='green', bold=True)
        return line


def _collect_entries() -> list[KeyEntry]:
    opts = get_options()
    kitty_mod = opts.kitty_mod
    entries: list[KeyEntry] = []
    seen: set[tuple[str, str, str]] = set()

    for mode_name, kb_mode in opts.keyboard_modes.items():
        for trigger, defns in kb_mode.keymap.items():
            # The last definition in the list wins (most recently configured).
            kd = defns[-1]
            if not kd.definition:       # explicit no-op / unmapped
                continue

            from kitty.types import Shortcut
            sc = Shortcut((trigger,))
            key_repr = sc.human_repr(kitty_mod)

            # Include any chained keys stored in rest
            if kd.is_sequence and kd.rest:
                from kitty.types import human_repr_of_single_key
                rest_repr = ' > '.join(human_repr_of_single_key(k, kitty_mod) for k in kd.rest)
                key_repr = f'{key_repr} > {rest_repr}'

            action = kd.definition
            dedup_key = (key_repr, action, mode_name)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            entries.append(KeyEntry(key_repr, action, mode_name))

    entries.sort(key=lambda e: (e.mode, e.action, e.key_repr))
    return entries


# ─────────────────────────── TUI handler ──────────────────────────────────── #

PROMPT = 'Filter: '
HEADER_LINES = 3   # prompt + blank + column header


class KeymapFilter(Handler):
    use_alternate_screen = True

    def __init__(self) -> None:
        self._all_entries: list[KeyEntry] = _collect_entries()
        self._filtered: list[KeyEntry] = list(self._all_entries)
        self._selected: int = 0
        self._scroll_offset: int = 0
        self._line_edit = LineEdit()
        self.result: str = ''

    # ── lifecycle ──────────────────────────────────────────────── #

    def initialize(self) -> None:
        self.cmd.set_cursor_visible(False)
        self._redraw()

    def on_resize(self, screen_size: ScreenSize) -> None:
        super().on_resize(screen_size)
        self._clamp()
        self._redraw()

    # ── input ──────────────────────────────────────────────────── #

    def on_text(self, text: str, in_bracketed_paste: bool = False) -> None:
        self._line_edit.on_text(text, in_bracketed_paste)
        self._apply_filter()

    def on_key(self, key_event: KeyEventType) -> None:
        if key_event.type is EventType.RELEASE:
            return

        if key_event.matches('escape') or key_event.matches('q'):
            self.quit_loop(0)
            return

        if key_event.matches('enter'):
            if self._filtered:
                self.result = self._filtered[self._selected].key_repr
            self.quit_loop(0)
            return

        if key_event.matches('up') or key_event.matches('ctrl+p'):
            self._move(-1)
            return

        if key_event.matches('down') or key_event.matches('ctrl+n'):
            self._move(1)
            return

        if key_event.matches('page_up'):
            self._move(-self._visible_rows())
            return

        if key_event.matches('page_down'):
            self._move(self._visible_rows())
            return

        if key_event.matches('ctrl+u'):
            self._line_edit.clear()
            self._apply_filter()
            return

        if self._line_edit.on_key(key_event):
            self._apply_filter()

    def on_interrupt(self) -> None:
        self.quit_loop(1)

    def on_eot(self) -> None:
        self.quit_loop(1)

    # ── filtering / selection helpers ──────────────────────────── #

    def _apply_filter(self) -> None:
        query = self._line_edit.current_input
        if query:
            self._filtered = [e for e in self._all_entries if e.matches(query)]
        else:
            self._filtered = list(self._all_entries)
        self._selected = 0
        self._scroll_offset = 0
        self._redraw()

    def _move(self, delta: int) -> None:
        if not self._filtered:
            return
        self._selected = max(0, min(len(self._filtered) - 1, self._selected + delta))
        self._ensure_visible()
        self._redraw()

    def _visible_rows(self) -> int:
        return max(1, self.screen_size.rows - HEADER_LINES - 1)

    def _ensure_visible(self) -> None:
        visible = self._visible_rows()
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + visible:
            self._scroll_offset = self._selected - visible + 1

    def _clamp(self) -> None:
        if not self._filtered:
            self._selected = 0
            self._scroll_offset = 0
            return
        self._selected = min(self._selected, len(self._filtered) - 1)
        self._ensure_visible()

    # ── rendering ──────────────────────────────────────────────── #

    def _redraw(self) -> None:
        cols  = self.screen_size.cols
        rows  = self.screen_size.rows
        lines: list[str] = []

        # ── row 0: prompt + filter input ──────────────────────── #
        prompt_text = PROMPT + self._line_edit.current_input
        lines.append(styled(prompt_text, bold=True)[:cols])

        # ── row 1: stats ──────────────────────────────────────── #
        total   = len(self._all_entries)
        showing = len(self._filtered)
        stat = f'{showing}/{total} bindings'
        if self._line_edit.current_input:
            stat += f'  (filter: {self._line_edit.current_input!r})'
        lines.append(colored(stat, 'blue')[:cols])

        # ── row 2: column header ──────────────────────────────── #
        key_w, act_w = self._column_widths()
        header = f'{"Key combo":<{key_w}}  →  {"Action":<{act_w}}'
        lines.append(styled(header[:cols], fg='yellow', dim=True))

        # ── rows 3…: entries ─────────────────────────────────── #
        visible = self._visible_rows()
        start   = self._scroll_offset
        end     = min(start + visible, len(self._filtered))

        for idx in range(start, end):
            entry = self._filtered[idx]
            selected = (idx == self._selected)
            line = entry.display(key_w, act_w, selected)
            lines.append(line[:cols])

        # ── footer hint ───────────────────────────────────────── #
        hint = ' ↑/↓ navigate  Enter copy key  Esc/q quit  ctrl+u clear '
        hint_line = styled(hint[:cols], dim=True)

        # Assemble output: clear screen then write all lines.
        output = clear_screen()
        output += set_cursor_position(0, 0)
        output += '\r\n'.join(lines)

        # Position footer on the last row.
        output += set_cursor_position(0, rows - 1)
        output += hint_line

        # Park the cursor at the end of the filter prompt (row 0).
        cursor_col = wcswidth(prompt_text)
        output += set_cursor_position(min(cursor_col, cols - 1), 0)

        self.write(output)

    def _column_widths(self) -> tuple[int, int]:
        """Return (key_width, action_width) that fit within screen columns."""
        cols = self.screen_size.cols
        # Reserve: key_w + "  →  " (5) + act_w + optional mode tag
        # Split remaining space roughly 30/70 between key and action.
        usable = max(20, cols - 5)
        key_w  = max(14, usable * 30 // 100)
        act_w  = max(14, usable - key_w)
        return key_w, act_w


# ─────────────────────────── kitten entry points ──────────────────────────── #

def main(args: list[str]) -> str:
    loop = Loop()
    handler = KeymapFilter()
    loop.loop(handler)
    return handler.result


@result_handler(no_ui=True)
def handle_result(
    args: list[str],
    result: str,
    target_window_id: int,
    boss: BossType,
) -> None:
    if result:
        # Copy the selected key-combo string to the system clipboard.
        from kitty.clipboard import set_clipboard_string
        set_clipboard_string(result)
        boss.handle_clipboard_loss('clipboard')

#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>
#+ keymap_filter - Interactive TUI browser for all configured kitty keybindings
#: DESCRIPTION: Opens a full-screen alternate-screen overlay listing every kitty
#:   keybinding across all keyboard modes (default + named).  As the user types,
#:   bindings are filtered in real time via multi-token substring match.
#:   Pressing Enter copies the highlighted key-combo to the system clipboard.
#:
#: TYPE: ORCHESTRATOR
#:
#: REQUIRES: kitty.fast_data_types  (get_options, wcswidth)
#:           kitty.key_encoding     (EventType)
#:           kittens.tui.handler    (Handler, result_handler)
#:           kittens.tui.line_edit  (LineEdit)
#:           kittens.tui.loop       (Loop)
#:           kittens.tui.operations (clear_screen, colored, set_cursor_position, styled)
#:           kitty.clipboard        (set_clipboard_string) — imported lazily in handle_result
#:           kitty.types            (Shortcut, human_repr_of_single_key) — imported lazily in _collect_entries
#:
#: SIDE EFFECTS:
#:   - Renders kitty alternate screen; restores terminal state on exit
#:   - Hides terminal cursor for duration of session
#:   - On Enter: writes selected key-combo str to system clipboard via set_clipboard_string
#:   - Signals kitty clipboard ownership via boss.handle_clipboard_loss('clipboard')
#:
#: USAGE: map kitty_mod+/ kitten keymap_filter
#:
#: INPUTS:  args list[str] — passed by kitty; ignored (no CLI options defined)
#:
#: OUTPUTS:
#:   main()         → str: selected key_repr on Enter; '' on cancel or empty filtered list
#:   handle_result  → clipboard: key_repr string written via set_clipboard_string
#:
#: KEY BINDINGS (hardcoded):
#:   type text   filter (multi-token; all tokens must match key_repr, action, or mode)
#:   ↑ / ctrl+p  move selection up one row
#:   ↓ / ctrl+n  move selection down one row
#:   page_up     move selection up one viewport
#:   page_down   move selection down one viewport
#:   ctrl+u      clear filter, show all entries
#:   enter       copy highlighted key-combo to clipboard, quit
#:   esc / q     quit without copying
#:   ctrl+c      quit without copying (return code 1)
#:   ctrl+d      quit without copying (return code 1)
#:
#: EXAMPLES:
#:   # kitty.conf
#:   map kitty_mod+/ kitten keymap_filter
#:   # type "scroll"   → shows only scroll_* action bindings
#:   # type "ctrl tab" → entries containing both "ctrl" AND "tab"
#:   # type "insert"   → entries belonging to a keyboard mode named "insert"

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
    from kitty.types import SingleKey


# ─────────────────────────── data model ───────────────────────────────────── #

#+ KeyEntry - Immutable record of one resolved keybinding
#: DESCRIPTION: Holds the display strings for a single key → action mapping and
#:   a pre-lowercased search field covering all three attributes.
#:
#: INPUTS:
#:   key_repr str — human-readable key combo, e.g. "ctrl+shift+t" or "kitty_mod+f > n"
#:   action   str — kitty action string, e.g. "new_window"
#:   mode     str — keyboard mode name; '' for the default (unnamed) mode
#:
#: OUTPUTS:
#:   .lower str — precomputed lowercase concatenation: "{key_repr} {action} {mode}"
#:                used exclusively by matches(); not safe to parse back into fields
class KeyEntry:

    __slots__ = ('key_repr', 'action', 'mode', 'lower')

    def __init__(self, key_repr: str, action: str, mode: str = '') -> None:
        self.key_repr = key_repr
        self.action   = action
        self.mode     = mode
        self.lower    = (key_repr + ' ' + action + ' ' + mode).lower()

    #+ matches - Test whether all query tokens appear in this entry
    #: INPUTS:  query str — space-separated search tokens (case-insensitive)
    #: OUTPUTS: bool
    #: RETURNS: True when query is empty or every token is a substring of .lower
    def matches(self, query: str) -> bool:
        if not query:
            return True
        return all(tok in self.lower for tok in query.lower().split())

    #+ display - Render one formatted display line
    #: INPUTS:
    #:   key_width int  — output width for key-combo field; ljust then slice to exact width
    #:   act_width int  — output width for action field;    ljust then slice to exact width
    #:   selected  bool — when True, wraps entire line in green+bold ANSI styling
    #:
    #: OUTPUTS: str — "{key_part}  →  {act_part}{mode_tag}"
    #:   key_part : exactly key_width chars
    #:   act_part : exactly act_width chars
    #:   mode_tag : "  [{mode}]" when mode is non-empty, else absent; NOT bounded by act_width
    #:   ANSI codes present when selected=True; caller must truncate result if length matters
    def display(self, key_width: int, act_width: int, selected: bool = False) -> str:
        key_part = self.key_repr.ljust(key_width)[:key_width]
        act_part = self.action.ljust(act_width)[:act_width]
        mode_tag = f'  [{self.mode}]' if self.mode else ''
        line = f'{key_part}  →  {act_part}{mode_tag}'
        if selected:
            return styled(line, fg='green', bold=True)
        return line


#+ _collect_entries - Build deduplicated KeyEntry list from live kitty options
#: TYPE: ACTION
#:
#: INPUTS:  none — reads get_options().keyboard_modes and .kitty_mod at call time
#:
#: OUTPUTS: list[KeyEntry] sorted by (mode, action, key_repr)
#:   - Covers all keyboard modes: default ('') and every named mode
#:   - Resolves kitty_mod bitmask via opts.kitty_mod
#:   - Sequence bindings: key_repr = "trigger > rest1 > rest2 …"
#:   - Deduplicates by (key_repr, action, mode_name); retains last definition per trigger
#:   - Omits entries with empty definition (explicit no-ops / unmapped)
#:
#: RETURNS: [] when no bindings are configured
def _collect_entries() -> list[KeyEntry]:
    opts = get_options()
    kitty_mod = opts.kitty_mod
    entries: list[KeyEntry] = []
    seen: set[tuple[str, str, str]] = set()

    for mode_name, kb_mode in opts.keyboard_modes.items():
        for trigger, defns in kb_mode.keymap.items():
            # Last definition wins (most recently configured in kitty.conf).
            kd = defns[-1]
            if not kd.definition:
                continue

            from kitty.types import Shortcut
            sc = Shortcut((trigger,))
            key_repr = sc.human_repr(kitty_mod)

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
HEADER_LINES = 3   # row 0: prompt  row 1: stats  row 2: column header


#+ KeymapFilter - TUI Handler: owns filter/selection state and drives the keymap browser
#: TYPE: ORCHESTRATOR
#:
#: DESCRIPTION: Constructed once per session; _all_entries populated at __init__ via
#:   _collect_entries().  Every keystroke either mutates _filtered or moves _selected,
#:   then triggers _redraw().  Exits via quit_loop(); result is read back by main().
#:
#: INPUTS:  none at construction
#:
#: STATE (mutated during session):
#:   _all_entries    list[KeyEntry]  — full unfiltered binding list; never modified after init
#:   _filtered       list[KeyEntry]  — current filtered view; subset of _all_entries
#:   _selected       int             — index into _filtered of the highlighted row
#:   _scroll_offset  int             — index of the topmost visible row in _filtered
#:   _line_edit      LineEdit        — manages the filter prompt input buffer
#:   result          str             — populated with key_repr on Enter; '' otherwise
#:
#: OUTPUTS:  self.result str — selected key_repr when user presses Enter;
#:                            '' on cancel (Esc/q/ctrl+c/ctrl+d)
#:
#: SIDE EFFECTS: hides terminal cursor on initialize(); loop restores terminal on exit
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

    #+ initialize - Session start: hide cursor and render initial state
    #: SIDE EFFECTS: cmd.set_cursor_visible(False); calls _redraw()
    def initialize(self) -> None:
        self.cmd.set_cursor_visible(False)
        self._redraw()

    #+ on_resize - Respond to terminal resize
    #: INPUTS:  screen_size ScreenSize — new terminal dimensions
    #: SIDE EFFECTS: updates self.screen_size via super(); calls _clamp(); calls _redraw()
    def on_resize(self, screen_size: ScreenSize) -> None:
        super().on_resize(screen_size)
        self._clamp()
        self._redraw()

    # ── input ──────────────────────────────────────────────────── #

    #+ on_text - Handle printable character input
    #: INPUTS:  text str — one or more printable characters from the keyboard
    #:          in_bracketed_paste bool — True when text arrived via bracketed paste
    #: SIDE EFFECTS: appends text to _line_edit; calls _apply_filter() → _redraw()
    def on_text(self, text: str, in_bracketed_paste: bool = False) -> None:
        self._line_edit.on_text(text, in_bracketed_paste)
        self._apply_filter()

    #+ on_key - Dispatch non-text key events
    #: INPUTS:  key_event KeyEventType
    #: SIDE EFFECTS (by match):
    #:   RELEASE         → no-op
    #:   escape / q      → quit_loop(0); result stays ''
    #:   enter           → result = _filtered[_selected].key_repr if _filtered non-empty; quit_loop(0)
    #:   up / ctrl+p     → _move(-1)
    #:   down / ctrl+n   → _move(+1)
    #:   page_up         → _move(-_visible_rows())
    #:   page_down       → _move(+_visible_rows())
    #:   ctrl+u          → _line_edit.clear(); _apply_filter()
    #:   other           → delegated to _line_edit.on_key(); if handled → _apply_filter()
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

    #+ on_interrupt - Handle ctrl+c
    #: SIDE EFFECTS: quit_loop(1); result stays ''
    def on_interrupt(self) -> None:
        self.quit_loop(1)

    #+ on_eot - Handle ctrl+d
    #: SIDE EFFECTS: quit_loop(1); result stays ''
    def on_eot(self) -> None:
        self.quit_loop(1)

    # ── filtering / selection helpers ──────────────────────────── #

    #+ _apply_filter - Rebuild _filtered from current line_edit input; reset selection
    #: INPUTS:  reads _line_edit.current_input
    #: SIDE EFFECTS:
    #:   _filtered    ← all entries matching query; full list when query is empty
    #:   _selected    ← 0
    #:   _scroll_offset ← 0
    #:   calls _redraw()
    def _apply_filter(self) -> None:
        query = self._line_edit.current_input
        if query:
            self._filtered = [e for e in self._all_entries if e.matches(query)]
        else:
            self._filtered = list(self._all_entries)
        self._selected = 0
        self._scroll_offset = 0
        self._redraw()

    #+ _move - Move selection by delta rows; clamp to valid range
    #: INPUTS:  delta int — signed row count (negative = up, positive = down)
    #: SIDE EFFECTS:
    #:   _selected ← clamped to [0, len(_filtered)-1]
    #:   calls _ensure_visible(); calls _redraw()
    #:   no-op when _filtered is empty
    def _move(self, delta: int) -> None:
        if not self._filtered:
            return
        self._selected = max(0, min(len(self._filtered) - 1, self._selected + delta))
        self._ensure_visible()
        self._redraw()

    #+ _visible_rows - Number of entry rows that fit on screen
    #: INPUTS:  reads screen_size.rows
    #: OUTPUTS: int = max(1, rows - HEADER_LINES - 1)
    #:   HEADER_LINES = 3 (prompt + stats + column header); -1 reserves footer row
    def _visible_rows(self) -> int:
        return max(1, self.screen_size.rows - HEADER_LINES - 1)

    #+ _ensure_visible - Adjust _scroll_offset so _selected is within the viewport
    #: INPUTS:  reads _selected, _scroll_offset, _visible_rows()
    #: SIDE EFFECTS:
    #:   _scroll_offset ← _selected          when _selected < _scroll_offset (scrolled above)
    #:   _scroll_offset ← _selected - visible + 1  when _selected >= _scroll_offset + visible
    #:   no-op when _selected is already visible
    #: NOTE: does not call _redraw(); caller is responsible
    def _ensure_visible(self) -> None:
        visible = self._visible_rows()
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + visible:
            self._scroll_offset = self._selected - visible + 1

    #+ _clamp - Recover valid selection/scroll state after resize or filter change
    #: INPUTS:  reads _filtered, _selected
    #: SIDE EFFECTS:
    #:   when _filtered empty: _selected ← 0, _scroll_offset ← 0
    #:   otherwise:            _selected ← min(_selected, len(_filtered)-1); _ensure_visible()
    #: NOTE: does not call _redraw(); called before _redraw in on_resize
    def _clamp(self) -> None:
        if not self._filtered:
            self._selected = 0
            self._scroll_offset = 0
            return
        self._selected = min(self._selected, len(self._filtered) - 1)
        self._ensure_visible()

    # ── rendering ──────────────────────────────────────────────── #

    #+ _redraw - Render the full TUI to the terminal in one write call
    #: INPUTS:  reads screen_size, _all_entries, _filtered, _selected,
    #:          _scroll_offset, _line_edit.current_input
    #:
    #: OUTPUTS: writes one concatenated escape-sequence string via self.write()
    #:
    #: LAYOUT (row indices, 0-based):
    #:   row 0            : bold prompt text + current filter input
    #:   row 1            : blue stats line "{showing}/{total} bindings [filter: '…']"
    #:   row 2            : yellow dim column header "Key combo  →  Action"
    #:   rows 3 … 3+N-1   : up to _visible_rows() entries from _filtered[_scroll_offset:]
    #:                       selected row rendered in green+bold via KeyEntry.display()
    #:   last row (rows-1): dim footer hint bar
    #:
    #: SIDE EFFECTS: positions cursor at col=min(wcswidth(prompt_text), cols-1), row=0
    #:
    #: NOTE: line[:cols] truncation is applied per line but does not account for ANSI
    #:       escape code bytes; lines with styling may be visually correct yet byte-longer
    def _redraw(self) -> None:
        cols  = self.screen_size.cols
        rows  = self.screen_size.rows
        lines: list[str] = []

        # row 0: prompt
        prompt_text = PROMPT + self._line_edit.current_input
        lines.append(styled(prompt_text, bold=True)[:cols])

        # row 1: stats
        total   = len(self._all_entries)
        showing = len(self._filtered)
        stat = f'{showing}/{total} bindings'
        if self._line_edit.current_input:
            stat += f'  (filter: {self._line_edit.current_input!r})'
        lines.append(colored(stat, 'blue')[:cols])

        # row 2: column header
        key_w, act_w = self._column_widths()
        header = f'{"Key combo":<{key_w}}  →  {"Action":<{act_w}}'
        lines.append(styled(header[:cols], fg='yellow', dim=True))

        # rows 3…: visible entries
        visible = self._visible_rows()
        start   = self._scroll_offset
        end     = min(start + visible, len(self._filtered))

        for idx in range(start, end):
            entry = self._filtered[idx]
            selected = (idx == self._selected)
            line = entry.display(key_w, act_w, selected)
            lines.append(line[:cols])

        # footer on last row
        hint = ' ↑/↓ navigate  Enter copy key  Esc/q quit  ctrl+u clear '
        hint_line = styled(hint[:cols], dim=True)

        output = clear_screen()
        output += set_cursor_position(0, 0)
        output += '\r\n'.join(lines)
        output += set_cursor_position(0, rows - 1)
        output += hint_line
        cursor_col = wcswidth(prompt_text)
        output += set_cursor_position(min(cursor_col, cols - 1), 0)

        self.write(output)

    #+ _column_widths - Compute key and action column widths from screen width
    #: INPUTS:  reads screen_size.cols
    #: OUTPUTS: tuple[int, int] — (key_width, act_width)
    #:   usable  = max(20, cols - 5)       # reserve "  →  " separator
    #:   key_w   = max(14, usable * 30 // 100)
    #:   act_w   = max(14, usable - key_w)
    def _column_widths(self) -> tuple[int, int]:
        cols = self.screen_size.cols
        usable = max(20, cols - 5)
        key_w  = max(14, usable * 30 // 100)
        act_w  = max(14, usable - key_w)
        return key_w, act_w


# ─────────────────────────── kitten entry points ──────────────────────────── #

#+ main - Kitten entry point: run the TUI event loop
#: TYPE: ORCHESTRATOR
#: INPUTS:  args list[str] — ignored
#: OUTPUTS: str — handler.result: key_repr on Enter, '' on cancel
#: SIDE EFFECTS: blocks; runs alternate-screen TUI loop until quit_loop() is called
def main(args: list[str]) -> str:
    loop = Loop()
    handler = KeymapFilter()
    loop.loop(handler)
    return handler.result


#+ handle_result - Kitten result handler: write selected key-combo to clipboard
#: TYPE: ACTION
#: INPUTS:
#:   args             list[str] — ignored
#:   result           str       — key_repr returned by main(); '' means no selection made
#:   target_window_id int       — kitty window that launched the kitten (unused)
#:   boss             BossType  — kitty Boss instance
#: SIDE EFFECTS when result is non-empty:
#:   set_clipboard_string(result) — writes result to system clipboard
#:   boss.handle_clipboard_loss('clipboard') — notifies kitty of clipboard ownership
#: RETURNS: None; no stdout
@result_handler(no_ui=True)
def handle_result(
    args: list[str],
    result: str,
    target_window_id: int,
    boss: BossType,
) -> None:
    if result:
        from kitty.clipboard import set_clipboard_string
        set_clipboard_string(result)
        boss.handle_clipboard_loss('clipboard')

#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>
#+ float_window - Toggle always-on-top (floating) state of the active OS Window
#: DESCRIPTION: No-UI kitten. Calls boss.toggle_floating() on the OS Window
#:   that contains the kitty window which launched this kitten.
#:   On each invocation the floating state is toggled: normal → floating → normal.
#:
#: TYPE: ACTION
#:
#: REQUIRES: kitty.fast_data_types (toggle_floating, via boss.toggle_floating)
#:
#: PLATFORM SUPPORT:
#:   macOS   — sets NSWindow level NSFloatingWindowLevel / NSNormalWindowLevel ✓
#:   X11     — sends _NET_WM_STATE_ABOVE add/remove to the window manager ✓
#:   Wayland — no-op (compositor controls stacking; returns None silently)  ✗
#:
#: SIDE EFFECTS:
#:   macOS: NSWindow.level toggled between NSFloatingWindowLevel / NSNormalWindowLevel
#:   X11:   _NET_WM_STATE_ABOVE added or removed on the X11 window
#:   Wayland / layer-shell panels: no change, no error
#:
#: USAGE: map kitty_mod+shift+f kitten float_window
#:        kitten @ resize-os-window --action=toggle-floating [--match …]
#:
#: INPUTS:  args list[str] — ignored (no CLI options)
#:
#: OUTPUTS:
#:   no_ui=True: main() is never called; handle_result operates entirely within
#:   the kitty process. No stdout, no TUI overlay.
#:
#: EXAMPLES:
#:   # kitty.conf — toggle the current OS window's floating state
#:   map kitty_mod+shift+f kitten float_window
#:
#:   # Remote-control — float every window whose title contains "notes"
#:   kitten @ resize-os-window --action=toggle-floating --match title:notes

from __future__ import annotations

from kitty.typing_compat import BossType

from ..tui.handler import result_handler


#+ main - Kitten entry point (never called when no_ui=True)
#: INPUTS:  args list[str] — ignored
#: OUTPUTS: str '' — placeholder; handle_result receives None, not this value
def main(args: list[str]) -> str:
    return ''


#+ handle_result - Toggle floating state of the OS Window that launched this kitten
#: INPUTS:
#:   args             list[str]  — ignored
#:   result           str | None — always None (no_ui=True bypasses main())
#:   target_window_id int        — kitty window id of the launcher window
#:   boss             BossType
#: SIDE EFFECTS: calls boss.toggle_floating(w.os_window_id) for the launcher's OS Window
#:   No-op when target_window_id is not in boss.window_id_map (window already closed)
#: RETURNS: None; no stdout
@result_handler(no_ui=True)
def handle_result(
    args: list[str],
    result: str | None,
    target_window_id: int,
    boss: BossType,
) -> None:
    w = boss.window_id_map.get(target_window_id)
    if w is not None:
        boss.toggle_floating(w.os_window_id)

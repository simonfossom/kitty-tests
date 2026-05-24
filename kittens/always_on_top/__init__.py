#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>
#+ always_on_top - Toggle the always-on-top state of the active OS Window
#: DESCRIPTION: No-UI kitten. Calls boss.toggle_always_on_top() on the OS Window
#:   that contains the kitty window which launched this kitten.
#:   On each invocation the state is toggled: normal → always-on-top → normal.
#:
#: TYPE: ACTION
#:
#: REQUIRES: kitty.fast_data_types (toggle_always_on_top, via boss.toggle_always_on_top)
#:
#: PLATFORM SUPPORT (per Kovid Goyal, kitty issue #7145):
#:   macOS   — NSStatusWindowLevel + collectionBehavior (canJoinAllSpaces,
#:             fullScreenAuxiliary, transient) — true above-everything window
#:             that also appears on every Space and over full-screen apps. ✓
#:   X11     — _NET_WM_STATE_ABOVE; effect depends on window-manager support. ✓
#:   Wayland — unsupported (compositor controls stacking); returns None silently. ✗
#:
#: SIDE EFFECTS:
#:   macOS:   sets window level and collection behavior on the NSWindow
#:   X11:     sends a _NET_WM_STATE_ABOVE add/remove ClientMessage to the WM
#:   Wayland or layer-shell panels: no change, no error
#:
#: USAGE: map kitty_mod+shift+a kitten always_on_top
#:        kitten @ resize-os-window --action=toggle-always-on-top [--match …]
#:
#: INPUTS:  args list[str] — ignored (no CLI options)
#:
#: OUTPUTS:
#:   no_ui=True: main() is never called; handle_result operates entirely within
#:   the kitty process. No stdout, no TUI overlay.
#:
#: SEE ALSO:
#:   - Direct action (no kitten needed): map kitty_mod+shift+a toggle_always_on_top
#:   - Launch with always-on-top: kitty --start-as=always-on-top
#:
#: EXAMPLES:
#:   # kitty.conf — toggle the current OS window's always-on-top state
#:   map kitty_mod+shift+a kitten always_on_top
#:
#:   # Remote-control — pin every window whose title contains "notes"
#:   kitten @ resize-os-window --action=toggle-always-on-top --match title:notes

from __future__ import annotations

from kitty.typing_compat import BossType

from ..tui.handler import result_handler


#+ main - Kitten entry point (never called when no_ui=True)
#: INPUTS:  args list[str] — ignored
#: OUTPUTS: str '' — placeholder; handle_result receives None, not this value
def main(args: list[str]) -> str:
    return ''


#+ handle_result - Toggle always-on-top state of the OS Window that launched this kitten
#: INPUTS:
#:   args             list[str]  — ignored
#:   result           str | None — always None (no_ui=True bypasses main())
#:   target_window_id int        — kitty window id of the launcher window
#:   boss             BossType
#: SIDE EFFECTS: calls boss.toggle_always_on_top(w.os_window_id) for the launcher's OS Window
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
        boss.toggle_always_on_top(w.os_window_id)

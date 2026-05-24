#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>
#+ always_on_top tests - Unit tests for the always_on_top kitten, action and parser
#: DESCRIPTION: Tests that do not require a compiled kitty binary or a running kitty instance.
#:   Covers: kitten module structure, no-UI contract, handle_result dispatch,
#:   RC command payload construction, options_spec correctness,
#:   parse_os_window_state recognizes the new always-on-top value, and the
#:   --start-as CLI choice list includes always-on-top.

from unittest.mock import MagicMock, patch

from . import BaseTest


#+ TestAlwaysOnTopKitten - Tests for kittens/always_on_top/__init__.py
#: INPUTS:  none
#: OUTPUTS: unittest pass/fail
class TestAlwaysOnTopKitten(BaseTest):

    def test_main_returns_empty_string(self) -> None:
        from kittens.always_on_top import main
        self.assertEqual(main([]), '')
        self.assertEqual(main(['ignored', 'args']), '')

    def test_handle_result_is_no_ui(self) -> None:
        # The @result_handler(no_ui=True) decorator must be applied so kitty
        # skips the TUI loop and calls handle_result(None, …) directly.
        from kittens.always_on_top import handle_result
        self.assertTrue(handle_result.no_ui)

    def test_handle_result_calls_toggle_for_known_window(self) -> None:
        from kittens.always_on_top import handle_result
        fake_window = MagicMock()
        fake_window.os_window_id = 42
        boss = MagicMock()
        boss.window_id_map = {7: fake_window}
        handle_result([], None, 7, boss)
        boss.toggle_always_on_top.assert_called_once_with(42)

    def test_handle_result_noop_for_unknown_window(self) -> None:
        # target_window_id not in window_id_map — must not raise, must not call boss method
        from kittens.always_on_top import handle_result
        boss = MagicMock()
        boss.window_id_map = {}
        handle_result([], None, 999, boss)
        boss.toggle_always_on_top.assert_not_called()

    def test_handle_result_noop_when_window_is_none(self) -> None:
        # window_id_map returns None (e.g. window closed between dispatch and execution)
        from kittens.always_on_top import handle_result
        boss = MagicMock()
        boss.window_id_map = {1: None}
        handle_result([], None, 1, boss)
        boss.toggle_always_on_top.assert_not_called()


#+ TestResizeOSWindowToggleAlwaysOnTop - Tests for the toggle-always-on-top RC action
#: INPUTS:  none
#: OUTPUTS: unittest pass/fail
class TestResizeOSWindowToggleAlwaysOnTop(BaseTest):

    def test_options_spec_includes_action(self) -> None:
        from kitty.rc.resize_os_window import resize_os_window
        self.assertIn('toggle-always-on-top', resize_os_window.options_spec)

    def test_protocol_spec_includes_action(self) -> None:
        from kitty.rc.resize_os_window import resize_os_window
        self.assertIn('toggle-always-on-top', resize_os_window.protocol_spec)

    def test_message_to_kitty_payload(self) -> None:
        from kitty.rc.resize_os_window import resize_os_window
        from kitty.rc.base import RCOptions
        opts = MagicMock()
        opts.match = ''
        opts.action = 'toggle-always-on-top'
        opts.unit = 'cells'
        opts.width = 0
        opts.height = 0
        opts.self = True
        opts.incremental = False
        payload = resize_os_window.message_to_kitty(RCOptions(), opts, [])
        self.assertEqual(payload['action'], 'toggle-always-on-top')
        self.assertTrue(payload['self'])

    def test_unsupported_returns_none_raises_error(self) -> None:
        # When toggle_always_on_top returns None (Wayland / panel), an RC error is raised.
        from kitty.rc.resize_os_window import resize_os_window
        from kitty.rc.base import RemoteControlErrorWithoutTraceback

        fake_window = MagicMock()
        fake_window.os_window_id = 5

        boss = MagicMock()

        payload_values = {'action': 'toggle-always-on-top', 'os_panel': []}
        payload_get = payload_values.__getitem__

        with patch('kitty.rc.resize_os_window.ResizeOSWindow.windows_for_match_payload',
                   return_value=[fake_window]):
            with patch('kitty.fast_data_types.get_os_window_size',
                       return_value={'is_layer_shell': False, 'width': 800, 'height': 600}):
                with patch('kitty.fast_data_types.toggle_always_on_top', return_value=None):
                    with self.assertRaises(RemoteControlErrorWithoutTraceback):
                        resize_os_window.response_from_kitty(boss, fake_window, payload_get)


#+ TestStartAsAlwaysOnTop - Tests for --start-as=always-on-top integration
#: INPUTS:  none
#: OUTPUTS: unittest pass/fail
class TestStartAsAlwaysOnTop(BaseTest):

    def test_parse_os_window_state_recognizes_value(self) -> None:
        from kitty.utils import parse_os_window_state
        from kitty.fast_data_types import WINDOW_ALWAYS_ON_TOP, WINDOW_NORMAL
        self.assertEqual(parse_os_window_state('always-on-top'), WINDOW_ALWAYS_ON_TOP)
        self.assertEqual(parse_os_window_state('always_on_top'), WINDOW_ALWAYS_ON_TOP)
        # Unknown values still fall back to WINDOW_NORMAL.
        self.assertEqual(parse_os_window_state('bogus'), WINDOW_NORMAL)

    def test_cli_choices_include_always_on_top(self) -> None:
        # The --start-as choices list lives in simple_cli_definitions.py as a
        # raw RST/conf snippet. Verify the new value is mentioned there.
        from kitty.simple_cli_definitions import kitty_options_spec
        spec = kitty_options_spec()
        self.assertIn('always-on-top', spec)
        # And specifically inside the --start-as choices line.
        for line in spec.splitlines():
            if line.startswith('choices=') and 'fullscreen' in line and 'maximized' in line:
                self.assertIn('always-on-top', line)
                break
        else:
            self.fail('Did not find --start-as choices line in kitty_options_spec()')

    def test_window_always_on_top_enum_exported(self) -> None:
        from kitty.fast_data_types import (
            WINDOW_ALWAYS_ON_TOP,
            WINDOW_FULLSCREEN,
            WINDOW_HIDDEN,
            WINDOW_MAXIMIZED,
            WINDOW_MINIMIZED,
            WINDOW_NORMAL,
        )
        # Distinct integer constant, greater than the prior maximum (WINDOW_HIDDEN).
        existing = {WINDOW_NORMAL, WINDOW_FULLSCREEN, WINDOW_MAXIMIZED, WINDOW_MINIMIZED, WINDOW_HIDDEN}
        self.assertNotIn(WINDOW_ALWAYS_ON_TOP, existing)
        self.assertGreater(WINDOW_ALWAYS_ON_TOP, WINDOW_HIDDEN)

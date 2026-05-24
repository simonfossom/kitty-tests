#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>
#+ float_window tests - Unit tests for the float_window kitten and toggle-floating RC action
#: DESCRIPTION: Tests that do not require a compiled kitty binary or a running kitty instance.
#:   Covers: kitten module structure, no-UI contract, handle_result dispatch,
#:   RC command payload construction, and options_spec correctness.

from unittest.mock import MagicMock, call, patch

from . import BaseTest


#+ TestFloatWindowKitten - Tests for kittens/float_window/__init__.py
#: INPUTS:  none
#: OUTPUTS: unittest pass/fail
class TestFloatWindowKitten(BaseTest):

    def test_main_returns_empty_string(self) -> None:
        from kittens.float_window import main
        self.assertEqual(main([]), '')
        self.assertEqual(main(['ignored', 'args']), '')

    def test_handle_result_is_no_ui(self) -> None:
        # The @result_handler(no_ui=True) decorator must be applied so kitty
        # skips the TUI loop and calls handle_result(None, …) directly.
        from kittens.float_window import handle_result
        self.assertTrue(handle_result.no_ui)

    def test_handle_result_calls_toggle_floating_for_known_window(self) -> None:
        from kittens.float_window import handle_result
        fake_window = MagicMock()
        fake_window.os_window_id = 42
        boss = MagicMock()
        boss.window_id_map = {7: fake_window}
        handle_result([], None, 7, boss)
        boss.toggle_floating.assert_called_once_with(42)

    def test_handle_result_noop_for_unknown_window(self) -> None:
        # target_window_id not in window_id_map — must not raise, must not call toggle_floating
        from kittens.float_window import handle_result
        boss = MagicMock()
        boss.window_id_map = {}
        handle_result([], None, 999, boss)
        boss.toggle_floating.assert_not_called()

    def test_handle_result_noop_when_window_is_none(self) -> None:
        # window_id_map returns None (e.g. window closed between dispatch and execution)
        from kittens.float_window import handle_result
        boss = MagicMock()
        boss.window_id_map = {1: None}
        handle_result([], None, 1, boss)
        boss.toggle_floating.assert_not_called()


#+ TestResizeOSWindowToggleFloating - Tests for the toggle-floating RC action
#: INPUTS:  none
#: OUTPUTS: unittest pass/fail
class TestResizeOSWindowToggleFloating(BaseTest):

    def test_options_spec_includes_toggle_floating(self) -> None:
        from kitty.rc.resize_os_window import resize_os_window
        self.assertIn('toggle-floating', resize_os_window.options_spec)

    def test_protocol_spec_includes_toggle_floating(self) -> None:
        from kitty.rc.resize_os_window import resize_os_window
        self.assertIn('toggle-floating', resize_os_window.protocol_spec)

    def test_message_to_kitty_toggle_floating_payload(self) -> None:
        from kitty.rc.resize_os_window import resize_os_window
        from kitty.rc.base import RCOptions
        opts = MagicMock()
        opts.match = ''
        opts.action = 'toggle-floating'
        opts.unit = 'cells'
        opts.width = 0
        opts.height = 0
        opts.self = True
        opts.incremental = False
        payload = resize_os_window.message_to_kitty(RCOptions(), opts, [])
        self.assertEqual(payload['action'], 'toggle-floating')
        self.assertTrue(payload['self'])

    def test_toggle_floating_returns_none_raises_error(self) -> None:
        # When toggle_floating returns None (Wayland / panel), an RC error is raised.
        from kitty.rc.resize_os_window import resize_os_window
        from kitty.rc.base import RemoteControlErrorWithoutTraceback

        fake_window = MagicMock()
        fake_window.os_window_id = 5

        boss = MagicMock()
        boss.toggle_floating = MagicMock()

        payload_values = {'action': 'toggle-floating', 'os_panel': []}

        def payload_get(key: str):
            return payload_values[key]

        # Patch get_os_window_size to return a non-panel metrics dict,
        # and toggle_floating to return None (unsupported).
        with patch('kitty.rc.resize_os_window.ResizeOSWindow.windows_for_match_payload',
                   return_value=[fake_window]):
            with patch('kitty.fast_data_types.get_os_window_size',
                       return_value={'is_layer_shell': False, 'width': 800, 'height': 600}):
                with patch('kitty.fast_data_types.toggle_floating', return_value=None):
                    with self.assertRaises(RemoteControlErrorWithoutTraceback):
                        resize_os_window.response_from_kitty(boss, fake_window, payload_get)

#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>
#+ keymap_filter tests - Unit tests for the keymap_filter kitten
#: DESCRIPTION: Covers KeyEntry matching/display contracts, _collect_entries()
#:   invariants (no duplicates, no empty actions, sort order), and KeymapFilter
#:   navigation and scroll-tracking helpers.  All tests requiring live kitty options
#:   call _collect_entries() which reads get_options().keyboard_modes; tests that
#:   need a screen size inject a FakeSize stub.
#:
#: REQUIRES: kitty.fast_data_types (get_options — accessed indirectly via _collect_entries)
#:           kittens.keymap_filter  (KeyEntry, KeymapFilter, _collect_entries, HEADER_LINES)

from . import BaseTest


#+ TestKeymapFilter - Test suite for KeyEntry and KeymapFilter
#: INPUTS:  none (setUp not overridden; uses BaseTest infrastructure)
#: OUTPUTS: unittest pass/fail assertions
class TestKeymapFilter(BaseTest):

    #+ _make_entry - Convenience factory for KeyEntry test fixtures
    #: INPUTS:  key_repr str (default 'ctrl+c'), action str (default 'copy_to_clipboard'),
    #:          mode str (default '')
    #: OUTPUTS: KeyEntry instance
    def _make_entry(self, key_repr: str = 'ctrl+c', action: str = 'copy_to_clipboard', mode: str = '') -> 'KeyEntry':
        from kittens.keymap_filter import KeyEntry
        return KeyEntry(key_repr, action, mode)

    # ── KeyEntry.matches ──────────────────────────────────────────── #

    def test_key_entry_matches_empty_query(self) -> None:
        entry = self._make_entry()
        self.assertTrue(entry.matches(''))

    def test_key_entry_matches_single_token(self) -> None:
        entry = self._make_entry(key_repr='ctrl+c', action='copy_to_clipboard')
        self.assertTrue(entry.matches('copy'))
        self.assertTrue(entry.matches('ctrl'))
        self.assertFalse(entry.matches('paste'))

    def test_key_entry_matches_multiple_tokens(self) -> None:
        entry = self._make_entry(key_repr='ctrl+c', action='copy_to_clipboard')
        self.assertTrue(entry.matches('ctrl copy'))
        self.assertFalse(entry.matches('ctrl paste'))

    def test_key_entry_case_insensitive(self) -> None:
        entry = self._make_entry(key_repr='ctrl+c', action='copy_to_clipboard')
        self.assertTrue(entry.matches('COPY'))
        self.assertTrue(entry.matches('Ctrl'))

    def test_key_entry_matches_mode(self) -> None:
        entry = self._make_entry(mode='insert')
        self.assertTrue(entry.matches('insert'))
        self.assertFalse(entry.matches('normal'))

    # ── KeyEntry.display ─────────────────────────────────────────── #

    def test_key_entry_display_no_mode(self) -> None:
        entry = self._make_entry(key_repr='ctrl+c', action='copy_to_clipboard')
        display = entry.display(key_width=10, act_width=20)
        self.assertIn('ctrl+c', display)
        self.assertIn('copy_to_clipboard', display)
        self.assertNotIn('[', display)

    def test_key_entry_display_with_mode(self) -> None:
        entry = self._make_entry(key_repr='ctrl+c', action='copy_to_clipboard', mode='mymode')
        display = entry.display(key_width=10, act_width=20)
        self.assertIn('[mymode]', display)

    def test_key_entry_display_selected_differs(self) -> None:
        # selected=True adds ANSI styling; the two strings must differ
        entry = self._make_entry()
        normal   = entry.display(key_width=10, act_width=20, selected=False)
        selected = entry.display(key_width=10, act_width=20, selected=True)
        self.assertNotEqual(normal, selected)

    # ── _collect_entries invariants ───────────────────────────────── #

    def test_collect_entries_returns_list(self) -> None:
        from kittens.keymap_filter import _collect_entries
        entries = _collect_entries()
        self.assertGreater(len(entries), 0)

    def test_collect_entries_no_duplicates(self) -> None:
        from kittens.keymap_filter import _collect_entries
        entries = _collect_entries()
        seen: set[tuple[str, str, str]] = set()
        for e in entries:
            key = (e.key_repr, e.action, e.mode)
            self.assertNotIn(key, seen, f'Duplicate entry: {key}')
            seen.add(key)

    def test_collect_entries_no_empty_actions(self) -> None:
        from kittens.keymap_filter import _collect_entries
        for entry in _collect_entries():
            self.assertTrue(entry.action, f'Empty action for key {entry.key_repr!r}')

    def test_collect_entries_sorted(self) -> None:
        # sort key is (mode, action, key_repr)
        from kittens.keymap_filter import _collect_entries
        entries = _collect_entries()
        keys = [(e.mode, e.action, e.key_repr) for e in entries]
        self.assertEqual(keys, sorted(keys))

    # ── KeymapFilter filter / selection logic ─────────────────────── #

    def test_handler_filter_reduces_list(self) -> None:
        from kittens.keymap_filter import KeymapFilter
        h = KeymapFilter()
        original_count = len(h._all_entries)
        h._line_edit.on_text('zzzzzzzzzzzzznomatch', False)
        h._apply_filter()
        self.assertEqual(len(h._filtered), 0)
        h._line_edit.clear()
        h._apply_filter()
        self.assertEqual(len(h._filtered), original_count)

    def test_handler_move_clamps(self) -> None:
        from kittens.keymap_filter import KeymapFilter
        h = KeymapFilter()
        h._move(-9999)
        self.assertEqual(h._selected, 0)
        h._move(9999)
        self.assertEqual(h._selected, len(h._filtered) - 1)

    def test_handler_move_no_entries(self) -> None:
        from kittens.keymap_filter import KeymapFilter
        h = KeymapFilter()
        h._filtered = []
        h._selected = 0
        h._move(1)   # must not raise
        self.assertEqual(h._selected, 0)

    # ── KeymapFilter layout helpers ───────────────────────────────── #

    def test_handler_visible_rows(self) -> None:
        from kittens.keymap_filter import HEADER_LINES, KeymapFilter

        class FakeSize:
            rows = 30
            cols = 80
            cell_width = 8
            cell_height = 16

        h = KeymapFilter()
        h.screen_size = FakeSize()  # type: ignore[assignment]
        self.assertEqual(h._visible_rows(), 30 - HEADER_LINES - 1)

    def test_handler_scroll_follows_selection(self) -> None:
        from kittens.keymap_filter import KeymapFilter

        class FakeSize:
            rows = 10    # visible_rows = 10 - 3 - 1 = 6
            cols = 80
            cell_width = 8
            cell_height = 16

        h = KeymapFilter()
        h.screen_size = FakeSize()  # type: ignore[assignment]

        if len(h._filtered) < 20:
            self.skipTest('Not enough keybindings loaded for scroll test')

        h._selected = 0
        h._scroll_offset = 0
        h._move(15)
        self.assertGreater(h._scroll_offset, 0)
        self.assertGreaterEqual(h._selected, h._scroll_offset)
        self.assertLess(h._selected, h._scroll_offset + h._visible_rows())

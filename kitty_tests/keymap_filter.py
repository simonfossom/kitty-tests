#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

"""Tests for the keymap_filter kitten."""

from . import BaseTest


class TestKeymapFilter(BaseTest):

    def _make_entry(self, key_repr: str = 'ctrl+c', action: str = 'copy_to_clipboard', mode: str = '') -> 'KeyEntry':
        from kittens.keymap_filter import KeyEntry
        return KeyEntry(key_repr, action, mode)

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

    def test_key_entry_display_no_mode(self) -> None:
        entry = self._make_entry(key_repr='ctrl+c', action='copy_to_clipboard')
        display = entry.display(key_width=10, act_width=20)
        self.assertIn('ctrl+c', display)
        self.assertIn('copy_to_clipboard', display)
        self.assertNotIn('[', display)   # no mode tag

    def test_key_entry_display_with_mode(self) -> None:
        entry = self._make_entry(key_repr='ctrl+c', action='copy_to_clipboard', mode='mymode')
        display = entry.display(key_width=10, act_width=20)
        self.assertIn('[mymode]', display)

    def test_key_entry_display_selected_differs(self) -> None:
        entry = self._make_entry()
        normal   = entry.display(key_width=10, act_width=20, selected=False)
        selected = entry.display(key_width=10, act_width=20, selected=True)
        # Selected display uses ANSI styling, so the strings differ.
        self.assertNotEqual(normal, selected)

    def test_collect_entries_returns_list(self) -> None:
        from kittens.keymap_filter import _collect_entries
        entries = _collect_entries()
        # kitty has built-in default keybindings, so the list must be non-empty.
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
        from kittens.keymap_filter import _collect_entries
        entries = _collect_entries()
        keys = [(e.mode, e.action, e.key_repr) for e in entries]
        self.assertEqual(keys, sorted(keys))

    def test_handler_filter_reduces_list(self) -> None:
        from kittens.keymap_filter import KeymapFilter
        h = KeymapFilter()
        original_count = len(h._all_entries)
        # Simulate typing a very specific query that shouldn't match everything.
        h._line_edit.on_text('zzzzzzzzzzzzznomatch', False)
        h._apply_filter()
        self.assertEqual(len(h._filtered), 0)
        # Clear the filter and all entries come back.
        h._line_edit.clear()
        h._apply_filter()
        self.assertEqual(len(h._filtered), original_count)

    def test_handler_move_clamps(self) -> None:
        from kittens.keymap_filter import KeymapFilter
        h = KeymapFilter()
        # Move up past the beginning: should stay at 0.
        h._move(-9999)
        self.assertEqual(h._selected, 0)
        # Move down past the end: should stop at last index.
        h._move(9999)
        self.assertEqual(h._selected, len(h._filtered) - 1)

    def test_handler_move_no_entries(self) -> None:
        from kittens.keymap_filter import KeymapFilter
        h = KeymapFilter()
        h._filtered = []
        h._selected = 0
        # Should not raise even with an empty list.
        h._move(1)
        self.assertEqual(h._selected, 0)

    def test_handler_visible_rows(self) -> None:
        from kittens.keymap_filter import KeymapFilter, HEADER_LINES
        from kitty.utils import read_screen_size
        h = KeymapFilter()
        # Manually set a fake screen size so we can assert the formula.
        from kitty.typing_compat import ScreenSize
        # ScreenSize is a NamedTuple-like; patch via the attribute.
        class FakeSize:
            rows = 30
            cols = 80
            cell_width = 8
            cell_height = 16
        h.screen_size = FakeSize()  # type: ignore[assignment]
        expected = 30 - HEADER_LINES - 1
        self.assertEqual(h._visible_rows(), expected)

    def test_handler_scroll_follows_selection(self) -> None:
        from kittens.keymap_filter import KeymapFilter, HEADER_LINES
        h = KeymapFilter()

        class FakeSize:
            rows = 10    # very small window → visible_rows = 10 - 3 - 1 = 6
            cols = 80
            cell_width = 8
            cell_height = 16

        h.screen_size = FakeSize()  # type: ignore[assignment]
        # Ensure there are enough entries to scroll.
        if len(h._filtered) < 20:
            self.skipTest('Not enough keybindings loaded for scroll test')

        h._selected = 0
        h._scroll_offset = 0
        h._move(15)   # move 15 rows down
        self.assertGreater(h._scroll_offset, 0)
        self.assertGreaterEqual(h._selected, h._scroll_offset)
        self.assertLess(h._selected, h._scroll_offset + h._visible_rows())

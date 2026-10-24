"""The menu bar of the main window: where the items are and that no access key is used twice."""

import re

import pytest
import wx

from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

FILE, CONVERSATION, TOOLS = 0, 1, 2
_ACCESS_KEY = re.compile(r"&(?!&)(.)")


def _labels(menu: wx.Menu) -> list[str]:
    return [item.GetItemLabel() for item in menu.GetMenuItems() if not item.IsSeparator()]


def test_preferences_is_in_the_file_menu_just_above_quit(window: MainWindow) -> None:
    labels = _labels(window.GetMenuBar().GetMenu(FILE))
    assert labels[-2:] == ["Pre&ferences…", "&Quit\tCtrl+Q"]


def test_the_tools_menu_has_no_preferences_any_more(window: MainWindow) -> None:
    assert not any("references" in label for label in _labels(window.GetMenuBar().GetMenu(TOOLS)))


def test_preferences_is_available_without_a_workspace(window: MainWindow) -> None:
    item = next(
        item
        for item in window.GetMenuBar().GetMenu(FILE).GetMenuItems()
        if item.GetItemLabel() == "Pre&ferences…"
    )
    assert item.IsEnabled()


def test_no_access_key_is_used_twice_in_a_menu(window: MainWindow) -> None:
    bar = window.GetMenuBar()
    for index in range(bar.GetMenuCount()):
        keys = [
            match.group(1).lower()
            for label in _labels(bar.GetMenu(index))
            if (match := _ACCESS_KEY.search(label.split("\t")[0]))
        ]
        assert len(keys) == len(set(keys)), (bar.GetMenuLabel(index), keys)

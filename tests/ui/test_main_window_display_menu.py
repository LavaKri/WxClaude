"""Tests of the main window: the Display submenu and the removal of the marks of bold and italic."""

from pathlib import Path

import pytest
import wx
from main_window_support import _settings

from wxclaude.core.conversation.messages import Message, Role
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

MESSAGES = [
    Message("1", Role.USER, "A **bold** question"),
    Message("2", Role.ASSISTANT, "An *italic* and **bold** answer", model="m"),
]


def _submenu(window: MainWindow) -> wx.Menu:
    conversation_menu = window.GetMenuBar().GetMenu(1)
    items = {i.GetItemLabel(): i.GetSubMenu() for i in conversation_menu.GetMenuItems()}
    submenu = items["Dis&play"]
    assert submenu is not None
    return submenu


def _choose(window: MainWindow, *, checked: bool) -> None:
    item = window._menu.marks_item
    item.Check(checked)
    event = wx.CommandEvent(wx.wxEVT_MENU, item.GetId())
    event.SetInt(int(checked))
    window.ProcessEvent(event)


def test_the_display_menu_holds_the_two_check_items(window: MainWindow) -> None:
    labels = [item.GetItemLabel() for item in _submenu(window).GetMenuItems()]
    assert labels == ["Remove the &Markdown formatting", "Summary of the &tools under the answers"]
    assert all(item.IsCheckable() for item in _submenu(window).GetMenuItems())


def test_the_marks_are_removed_by_default(window: MainWindow) -> None:
    item = window._menu.marks_item
    assert item.IsChecked()
    assert item.IsEnabled()  # it needs neither a workspace nor a conversation
    assert window._settings.remove_markdown_marks
    window._conversation.set_messages(MESSAGES)
    text = window._conversation.GetValue()
    assert "A bold question" in text
    assert "An italic and bold answer" in text
    assert "**" not in text


def test_the_item_shows_and_removes_the_marks_and_the_setting_is_kept(window: MainWindow) -> None:
    view = window._conversation
    view.set_messages(MESSAGES)
    _choose(window, checked=False)
    assert not window._settings.remove_markdown_marks
    assert "An *italic* and **bold** answer" in view.GetValue()
    _choose(window, checked=True)
    assert window._settings.remove_markdown_marks
    assert "An italic and bold answer" in view.GetValue()


def test_the_item_follows_the_setting_at_the_start(wx_app: wx.App, tmp_path: Path) -> None:
    settings = _settings()
    settings.remove_markdown_marks = False
    window = MainWindow(settings)
    try:
        assert not window._menu.marks_item.IsChecked()
        window._conversation.set_messages(MESSAGES)
        assert "**bold**" in window._conversation.GetValue()
    finally:
        window.Destroy()
        wx.SafeYield()


def test_the_export_keeps_the_marks(window: MainWindow) -> None:
    window._conversation.set_messages(MESSAGES)
    assert "**" not in window._conversation.GetValue()
    markdown = window._conversation.markdown_text()
    assert "A **bold** question" in markdown
    assert "An *italic* and **bold** answer" in markdown

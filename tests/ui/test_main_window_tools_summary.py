"""Tests of the main window: the line under the answers that sums up the tools used."""

from pathlib import Path

import pytest
import wx
from main_window_support import _send, _settings, _wait_until_idle

from wxclaude.core.conversation.details import DetailAction
from wxclaude.ui import desktop
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

LABEL = "Summary of the &tools under the answers"


def _item(window: MainWindow) -> wx.MenuItem:
    return window._menu.tools_summary_item


def test_the_item_is_in_the_conversation_menu_and_checked_by_default(window: MainWindow) -> None:
    item = _item(window)
    assert item.GetItemLabel() == LABEL
    assert item.IsCheckable()
    assert item.IsChecked()
    assert item.IsEnabled()  # it needs neither a workspace nor a conversation
    assert item.GetMenu() is window.GetMenuBar().GetMenu(1)


def test_the_item_follows_the_setting_at_the_start(wx_app: wx.App, tmp_path: Path) -> None:
    settings = _settings()
    settings.show_tools_summary = False
    window = MainWindow(settings)
    try:
        assert not _item(window).IsChecked()
    finally:
        window.Destroy()
        wx.SafeYield()


def test_an_answer_that_used_tools_gets_its_line_at_the_end_of_the_message(
    conversation: MainWindow,
) -> None:
    _send(conversation, "hello")
    text = conversation._conversation.GetValue()
    assert "Echo: hello\n\n1 file read\n\n" in text  # the fake CLI reads one file


def _choose(window: MainWindow, *, checked: bool) -> None:
    """The user picks the item: the menu flips its check mark and tells the window."""
    item = _item(window)
    item.Check(checked)
    event = wx.CommandEvent(wx.wxEVT_MENU, item.GetId())
    event.SetInt(int(checked))
    window.ProcessEvent(event)


def test_the_item_hides_and_shows_the_line_and_the_setting_is_kept(
    conversation: MainWindow,
) -> None:
    _send(conversation, "hello")
    view = conversation._conversation
    _choose(conversation, checked=False)
    assert not conversation._settings.show_tools_summary
    assert "1 file read" not in view.GetValue()
    _choose(conversation, checked=True)
    assert conversation._settings.show_tools_summary
    assert "1 file read" in view.GetValue()


def test_the_line_comes_without_moving_the_caret_or_the_focus(conversation: MainWindow) -> None:
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    view = conversation._conversation
    caret = view.GetInsertionPoint()  # the start of the prompt just sent
    _wait_until_idle(conversation)
    assert "1 file read" in view.GetValue()
    assert view.GetInsertionPoint() == caret
    assert view.HasFocus()


def test_copying_the_exchange_leaves_the_line_out(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "hello")
    copied: list[str] = []

    def keep(text: str) -> bool:
        copied.append(text)
        return True

    monkeypatch.setattr(desktop, "set_clipboard", keep)
    answer = conversation._conversation.document.spans[-1].message
    conversation._actions.act(DetailAction.COPY_EXCHANGE, answer, -1)
    (text,) = copied
    assert text.endswith("Echo: hello")
    assert "file read" not in text

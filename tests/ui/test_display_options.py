"""The display choices (system messages, summary of the tools, marks of bold and italic) put
together: shown as the settings say, at the start and after the Preferences, and saved when the
menu changes one. The items of the menu are tested through the window in
``test_main_window_display_menu.py`` and ``test_main_window_tools_summary.py``."""

import pytest
import wx
from main_window_support import _runner, _settings

from wxclaude.core.conversation.messages import Message, Role
from wxclaude.ui.display_options import DisplayOptions
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

MESSAGES = [
    Message("1", Role.USER, "continue", hidden=True),
    Message("2", Role.ASSISTANT, "The answer", model="m"),
]


def test_the_system_messages_are_hidden_by_default(window: MainWindow) -> None:
    window._conversation.set_messages(MESSAGES)
    assert "continue" not in window._conversation.GetValue()


def test_the_system_messages_are_shown_at_the_start_when_the_setting_says_so(
    wx_app: wx.App,
) -> None:
    settings = _settings()
    settings.hide_system_messages = False
    window = MainWindow(settings, _runner())
    try:
        window._conversation.set_messages(MESSAGES)
        assert "continue" in window._conversation.GetValue()
    finally:
        window.Destroy()
        wx.SafeYield()


def test_the_preferences_show_the_system_messages_in_the_conversation_at_once(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window._conversation.set_messages(MESSAGES)
    assert "continue" not in window._conversation.GetValue()

    def modal(dialog: wx.Dialog) -> int:
        dialog.workspace.hide_system_messages.SetValue(False)
        return int(wx.ID_OK)

    monkeypatch.setattr(window._feedback, "modal", modal)
    window._open_preferences(claude_page=False)
    assert not window._settings.hide_system_messages
    assert "continue" in window._conversation.GetValue()


def test_applying_puts_the_check_items_of_the_menu_as_the_settings_say(
    window: MainWindow,
) -> None:
    window._settings.show_tools_summary = False
    window._settings.remove_markdown_marks = False
    window._display.apply()
    assert not window._menu.tools_summary_item.IsChecked()
    assert not window._menu.marks_item.IsChecked()
    window._settings.show_tools_summary = True
    window._settings.remove_markdown_marks = True
    window._display.apply()
    assert window._menu.tools_summary_item.IsChecked()
    assert window._menu.marks_item.IsChecked()


def _options(window: MainWindow, saved: list[bool]) -> DisplayOptions:
    return DisplayOptions(
        window._conversation, window._menu, window._settings, lambda: saved.append(True)
    )


def test_a_choice_of_the_menu_is_kept_in_the_settings_and_saved(window: MainWindow) -> None:
    saved: list[bool] = []
    options = _options(window, saved)
    options.set_tools_summary(False)
    assert not window._settings.show_tools_summary
    assert saved == [True]
    options.set_without_marks(False)
    assert not window._settings.remove_markdown_marks
    assert saved == [True, True]

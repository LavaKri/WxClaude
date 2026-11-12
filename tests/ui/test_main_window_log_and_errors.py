"""The way to the log from the application: the item of the Help menu that opens its folder, and
the button of the error boxes that copies the details."""

from pathlib import Path

import pytest
import wx
from main_window_support import _accepting

from wxclaude import __version__
from wxclaude.core.config.settings import Settings
from wxclaude.ui import desktop
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

LOG_ITEM = "Open the &log folder"


def _help_items(window: MainWindow) -> dict[str, wx.MenuItem]:
    help_menu = window.GetMenuBar().GetMenu(3)
    return {item.GetItemLabel(): item for item in help_menu.GetMenuItems()}


class Dialogs:
    """Replaces the modal display: keeps the message boxes shown and answers with ``answer``."""

    def __init__(self, window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
        self.answer = wx.ID_CANCEL
        self.shown: list[wx.MessageDialog] = []
        self.captions: list[str] = []
        self.texts: list[str] = []
        self.ok_labels: list[str] = []
        self.cancel_labels: list[str] = []
        monkeypatch.setattr(window._feedback, "modal", self._modal)

    def _modal(self, dialog: wx.Dialog) -> int:
        if isinstance(dialog, wx.MessageDialog):
            self.captions.append(dialog.GetTitle())
            self.texts.append(dialog.GetMessage())
            self.ok_labels.append(dialog.GetOKLabel())
            self.cancel_labels.append(dialog.GetCancelLabel())
        return int(self.answer)


def test_the_help_menu_has_the_log_folder_item_with_no_shortcut(window: MainWindow) -> None:
    items = _help_items(window)
    assert LOG_ITEM in items
    assert items[LOG_ITEM].IsEnabled()  # it needs neither a workspace nor a conversation


def test_the_help_menu_keys_are_unique(window: MainWindow) -> None:
    keys = [label.split("&", 1)[1][0].casefold() for label in _help_items(window) if "&" in label]
    assert len(keys) == len(set(keys))


def test_the_item_opens_the_folder_of_the_log(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window._settings.store = tmp_path / "settings.json"
    opened: list[Path] = []
    monkeypatch.setattr(desktop, "launch_folder", _accepting(opened))
    item = _help_items(window)[LOG_ITEM]
    window.ProcessEvent(wx.CommandEvent(wx.wxEVT_MENU, item.GetId()))
    assert opened == [tmp_path]


def test_the_log_folder_is_the_one_of_the_settings(tmp_path: Path) -> None:
    assert Settings.load(tmp_path / "settings.json").log_dir == tmp_path
    assert Settings().log_dir is None  # settings kept in memory: no folder


def test_an_error_box_closes_with_enter_and_escape_and_offers_to_copy(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialogs = Dialogs(window, monkeypatch)
    window._feedback.show_error("Cannot save the settings.")
    assert dialogs.texts == ["Cannot save the settings."]
    assert dialogs.ok_labels == ["Co&py the details"]  # not the default button
    assert dialogs.cancel_labels == ["&Close"]  # the default one: Enter and Escape


def test_closing_an_error_box_copies_nothing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    Dialogs(window, monkeypatch).answer = wx.ID_CANCEL
    copied: list[str] = []
    monkeypatch.setattr(desktop, "set_clipboard", _accepting(copied))
    window._feedback.show_error("Something failed.")
    assert copied == []


def test_copying_the_details_puts_the_error_and_the_version_on_the_clipboard(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    Dialogs(window, monkeypatch).answer = wx.ID_OK
    copied: list[str] = []
    monkeypatch.setattr(desktop, "set_clipboard", _accepting(copied))
    window._feedback.show_error("Cannot read the conversation.\nThe file is damaged.")
    assert copied == [
        f"Cannot read the conversation.\nThe file is damaged.\n\nWxClaude {__version__}"
    ]
    assert window._feedback.announcements.history.lines()[-1].endswith("Details copied.")


def test_a_clipboard_that_cannot_be_used_is_said_without_offering_to_copy_again(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialogs = Dialogs(window, monkeypatch)
    dialogs.answer = wx.ID_OK
    monkeypatch.setattr(desktop, "set_clipboard", lambda text: False)
    window._feedback.show_error("Something failed.")
    assert dialogs.texts == ["Something failed.", "The clipboard cannot be used."]
    assert dialogs.ok_labels[1] != "Co&py the details"  # the second box is a plain one


def test_the_text_of_an_error_is_kept_in_the_history_once(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    Dialogs(window, monkeypatch)
    window._feedback.show_error("Claude could not answer.")
    lines = [
        line
        for line in window._feedback.announcements.history.lines()
        if "Claude could not answer." in line
    ]
    assert len(lines) == 1

"""The menu bar of the main window: where the items are and that no access key is used twice."""

import re
from typing import ClassVar, Self

import pytest
import wx

from wxclaude.core.claude.auth import ClaudeLogin
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


def _sign_in_item(window: MainWindow) -> wx.MenuItem:
    return next(
        item
        for item in window.GetMenuBar().GetMenu(TOOLS).GetMenuItems()
        if item.GetItemLabel() == "Sign &in to Claude…"
    )


class _FakeLoginDialog:
    """Stands for the sign-in dialog: remembers it was made, closes at once."""

    made: ClassVar[list[tuple[object, ClaudeLogin]]] = []

    def __init__(self, parent: object, login: ClaudeLogin, _read_state: object) -> None:
        self.made.append((parent, login))

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def ShowModal(self) -> int:  # noqa: N802 (the wx name)
        return int(wx.ID_CLOSE)


def test_signing_in_is_in_the_tools_menu_without_a_workspace(window: MainWindow) -> None:
    assert _sign_in_item(window).IsEnabled()


def test_the_sign_in_item_opens_the_dialog_for_the_chosen_claude(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeLoginDialog.made = []
    monkeypatch.setattr("wxclaude.ui.main_window.LoginDialog", _FakeLoginDialog)
    window._run.runner.claude_path = "C:/tools/claude.exe"
    window.ProcessEvent(wx.CommandEvent(wx.wxEVT_MENU, _sign_in_item(window).GetId()))
    assert len(_FakeLoginDialog.made) == 1
    parent, login = _FakeLoginDialog.made[0]
    assert parent is window
    assert login.claude_path == "C:/tools/claude.exe"


def test_no_access_key_is_used_twice_in_a_menu(window: MainWindow) -> None:
    bar = window.GetMenuBar()
    for index in range(bar.GetMenuCount()):
        keys = [
            match.group(1).lower()
            for label in _labels(bar.GetMenu(index))
            if (match := _ACCESS_KEY.search(label.split("\t")[0]))
        ]
        assert len(keys) == len(set(keys)), (bar.GetMenuLabel(index), keys)

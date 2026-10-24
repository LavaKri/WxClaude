from collections.abc import Iterator

import pytest
import wx

from wxclaude.ui.prompt_field import PromptField

pytestmark = pytest.mark.ui


@pytest.fixture
def field(wx_app: wx.App) -> Iterator[PromptField]:
    frame = wx.Frame(None)
    field = PromptField(frame)
    yield field
    frame.Destroy()
    wx.SafeYield()


def _labels(menu: wx.Menu) -> list[str]:
    return [item.GetItemLabel() for item in menu.GetMenuItems() if not item.IsSeparator()]


def _item(menu: wx.Menu, label: str) -> wx.MenuItem:
    return next(item for item in menu.GetMenuItems() if item.GetItemLabel() == label)


def _record_popups(field: PromptField, monkeypatch: pytest.MonkeyPatch) -> list[wx.Menu]:
    """Replace the (blocking) pop-up of the menu by a record of the menus that would open."""
    popups: list[wx.Menu] = []

    def popup(menu: wx.Menu, *_args: object) -> bool:
        popups.append(menu)
        return True

    monkeypatch.setattr(field, "PopupMenu", popup)
    return popups


def _choose(menu: wx.Menu, item: wx.MenuItem) -> None:
    menu.ProcessEvent(wx.CommandEvent(wx.wxEVT_MENU, item.GetId()))


def test_the_field_is_named_multiline_and_plain(field: PromptField) -> None:
    assert field.GetName() == "Prompt"
    assert field.IsMultiLine()
    assert not field.HasFlag(wx.TE_RICH2)


def test_the_menu_has_the_editing_commands(field: PromptField) -> None:
    assert _labels(field.build_menu()) == ["Cu&t", "&Copy", "&Paste"]


def test_cut_and_copy_are_greyed_without_a_selection(field: PromptField) -> None:
    field.SetValue("hello world")
    menu = field.build_menu()
    assert not _item(menu, "Cu&t").IsEnabled()
    assert not _item(menu, "&Copy").IsEnabled()
    field.SetSelection(0, 5)
    menu = field.build_menu()
    assert _item(menu, "Cu&t").IsEnabled()
    assert _item(menu, "&Copy").IsEnabled()


def test_cut_copy_and_paste_work_on_the_text(field: PromptField) -> None:
    field.SetValue("hello world")
    field.SetSelection(0, 6)
    menu = field.build_menu()
    _choose(menu, _item(menu, "&Copy"))
    assert field.GetValue() == "hello world"
    _choose(menu, _item(menu, "Cu&t"))
    assert field.GetValue() == "world"
    field.SetInsertionPoint(field.GetLastPosition())
    menu = field.build_menu()
    assert _item(menu, "&Paste").IsEnabled()
    _choose(menu, _item(menu, "&Paste"))
    assert field.GetValue() == "worldhello "


def test_the_menu_opens_at_the_caret_for_the_keyboard_and_replaces_the_native_one(
    field: PromptField, monkeypatch: pytest.MonkeyPatch
) -> None:
    popups = _record_popups(field, monkeypatch)
    event = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, field.GetId(), wx.DefaultPosition)
    field._on_context_menu(event)
    assert len(popups) == 1
    shift_f10 = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
    shift_f10.SetKeyCode(wx.WXK_F10)
    shift_f10.SetShiftDown(True)
    field._on_key(shift_f10)
    assert len(popups) == 2


def test_other_keys_are_left_to_the_field_and_the_window(
    field: PromptField, monkeypatch: pytest.MonkeyPatch
) -> None:
    popups = _record_popups(field, monkeypatch)
    event = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
    event.SetKeyCode(ord("A"))
    field._on_key(event)
    assert popups == []
    assert event.GetSkipped()

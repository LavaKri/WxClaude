from collections.abc import Iterator

import pytest
import wx

from wxclaude.core.conversation.details import Table
from wxclaude.ui import message_view
from wxclaude.ui.table_dialog import TableCellsDialog

pytestmark = pytest.mark.ui


@pytest.fixture
def frame(wx_app: wx.App) -> Iterator[wx.Frame]:
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()
    wx.SafeYield()


def _close(dialog: wx.Dialog) -> None:
    dialog.Destroy()
    wx.SafeYield()


def _table(rows: tuple[tuple[str, ...], ...], headers: tuple[str, ...] = ("Name", "Size")) -> Table:
    return Table(headers, rows, 0, 3, "| Name | Size |")


def _key(dialog: TableCellsDialog, code: int, *, shift: bool = False) -> list[bool]:
    """Send a key to the list; return [True] if it was passed on to the native control."""
    event = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
    event.SetEventObject(dialog._list)
    event.SetKeyCode(code)
    event.SetShiftDown(shift)
    skipped: list[bool] = []
    event.Skip = lambda *_a: skipped.append(True)
    dialog._list.GetEventHandler().ProcessEvent(event)
    return skipped


def test_the_list_shows_the_header_row_then_the_rows_of_the_first_column(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a.txt", "3"), ("b.txt", "4"))))
    assert dialog.lines == ["Name", "a.txt", "b.txt"]
    assert dialog.column == 0
    assert dialog.selection == 0
    assert dialog.cell_text == "Name"
    assert dialog.FindFocus() is dialog._list
    assert dialog.FindWindowById(wx.ID_COPY) is not None
    _close(dialog)


def test_the_arrows_change_the_column_and_keep_the_row(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a.txt", "3"), ("b.txt", "4"))))
    dialog._list.SetSelection(2)
    dialog._on_select(wx.CommandEvent())
    assert _key(dialog, wx.WXK_RIGHT) == []
    assert dialog.lines == ["Size", "3", "4"]
    assert dialog.selection == 2
    assert dialog.cell_text == "4"
    assert _key(dialog, wx.WXK_LEFT) == []
    assert dialog.lines == ["Name", "a.txt", "b.txt"]
    assert dialog.cell_text == "b.txt"
    _close(dialog)


def test_the_first_and_the_last_column_are_the_limits(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a", "1"),)))
    assert dialog.move_column(-1) is False
    assert dialog.move_column(1) is True
    assert dialog.move_column(1) is False
    assert dialog.column == 1
    _close(dialog)


def test_the_label_of_the_list_says_which_column_it_shows(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a", "1"),), headers=("R&D", "Size")))
    assert dialog._list_label.GetLabel() == "&Rows, column 1 of 2: R&&D"
    _close(dialog)


def test_the_other_keys_are_left_to_the_list(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a", "1"),)))
    assert _key(dialog, wx.WXK_DOWN) == [True]
    assert _key(dialog, wx.WXK_RIGHT, shift=True) == [True]
    assert dialog.column == 0
    _close(dialog)


def test_an_empty_cell_is_named_in_the_list_and_empty_in_the_field(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a", ""),)))
    dialog.move_column(1)
    dialog._list.SetSelection(1)
    dialog._on_select(wx.CommandEvent())
    assert dialog.lines == ["Size", "Empty cell"]
    assert dialog.cell_text == ""
    _close(dialog)


def test_a_row_shorter_or_longer_than_the_headers_is_padded(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a",), ("b", "2", "extra"))))
    dialog.move_column(1)
    dialog.move_column(1)
    assert dialog.lines == ["Empty cell", "Empty cell", "extra"]
    _close(dialog)


def test_copy_ends_the_dialog_with_its_identifier(frame: wx.Frame) -> None:
    dialog = TableCellsDialog(frame, _table((("a", "1"),)))
    ended: list[int] = []
    dialog.EndModal = ended.append
    wx.PostEvent(dialog, wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_COPY))
    wx.SafeYield()
    assert ended == [wx.ID_COPY]
    _close(dialog)


def test_the_view_uses_the_cells_dialog() -> None:
    assert message_view.TABLE_DIALOG is TableCellsDialog

"""The dialog that shows a table of a message one column at a time.

It takes the place of ``details_dialogs.TableDialog`` (one sentence per row) through the one
line ``TABLE_DIALOG`` of ``ui/message_view.py``; both are built from a ``Table`` and end with
``wx.ID_COPY`` when the user asks to copy it.
"""

import wx

from wxclaude.core.conversation.details import Table
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _


class TableCellsDialog(wx.Dialog):
    """The rows of a table in a list, the header row first, showing one column.

    Left and Right arrows change the column the list shows; a read-only field below holds the text
    of the cell at the selected row and the current column. The list has the initial focus.
    *Copy the table* closes the dialog with ``wx.ID_COPY``.
    """

    def __init__(self, parent: wx.Window, table: Table) -> None:
        super().__init__(parent, title=_("Table"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._grid = self._cells(table)
        self._column = 0
        # Each label is created right before its control so that screen readers pair them.
        self._list_label = wx.StaticText(self, label=_("&Rows"))
        self._list = wx.ListBox(self, style=wx.LB_SINGLE, name=accessible_name(_("&Rows")))
        cell_label = wx.StaticText(self, label=_("&Cell"))
        self._cell = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=accessible_name(_("&Cell")),
        )
        width, height = self._list.GetCharWidth(), self._list.GetCharHeight()
        self._list.SetMinSize(wx.Size(width * 70, height * 10))
        self._cell.SetMinSize(wx.Size(width * 70, height * 4))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._list, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(cell_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._cell, 0, wx.EXPAND | wx.ALL, 8)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(wx.Button(self, wx.ID_COPY, _("Copy the &table")), 0, wx.RIGHT, 6)
        buttons.Add(wx.Button(self, wx.ID_CLOSE), 0)
        sizer.Add(buttons, 0, wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.SetEscapeId(wx.ID_CLOSE)
        self.Bind(wx.EVT_BUTTON, self._on_button)
        self._list.Bind(wx.EVT_LISTBOX, self._on_select)
        self._list.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self._show_column(0)
        self._list.SetFocus()

    @property
    def column(self) -> int:
        """The index of the column the list shows."""
        return self._column

    @property
    def lines(self) -> list[str]:
        """What the list shows: the cells of the current column, header first."""
        return list(self._list.GetStrings())

    @property
    def selection(self) -> int:
        """The index of the selected line (0 is the header row), -1 when there is none."""
        return int(self._list.GetSelection())

    @property
    def cell_text(self) -> str:
        """The text of the current cell."""
        return str(self._cell.GetValue())

    def move_column(self, step: int) -> bool:
        """Show the column ``step`` away (-1 or 1); False at the first and the last column."""
        target = self._column + step
        if not 0 <= target < self._column_count:
            return False
        self._show_column(target)
        return True

    @property
    def _column_count(self) -> int:
        return len(self._grid[0]) if self._grid else 0

    @staticmethod
    def _cells(table: Table) -> list[list[str]]:
        """The header row then the rows, every one with as many cells as the longest."""
        rows = [list(table.headers), *(list(row) for row in table.rows)]
        count = max(len(row) for row in rows)
        return [row + [""] * (count - len(row)) for row in rows]

    def _show_column(self, column: int) -> None:
        """Fill the list with ``column``, the selected row staying the same."""
        row = max(self.selection, 0)
        self._column = column
        self._list.Set([cells[column] or _("Empty cell") for cells in self._grid])
        self._list.SetSelection(row)
        header = self._grid[0][column].replace("&", "&&")
        self._list_label.SetLabel(
            _("&Rows, column {number} of {count}: {header}").format(
                number=column + 1, count=self._column_count, header=header
            )
        )
        self._show_cell()

    def _show_cell(self) -> None:
        row = self.selection
        self._cell.ChangeValue(self._grid[row][self._column] if row >= 0 else "")

    def _on_select(self, _event: wx.CommandEvent) -> None:
        self._show_cell()

    def _on_key(self, event: wx.KeyEvent) -> None:
        code = event.GetKeyCode()
        if code in (wx.WXK_LEFT, wx.WXK_RIGHT) and not (
            event.ControlDown() or event.AltDown() or event.ShiftDown()
        ):
            self.move_column(-1 if code == wx.WXK_LEFT else 1)
            return
        event.Skip()

    def _on_button(self, event: wx.CommandEvent) -> None:
        self.EndModal(event.GetId())

"""The dialogs that show what a message holds without displaying it: tools, a table, links."""

from collections.abc import Sequence

import wx

from wxclaude.core.details import Link, Table, tool_detail, tool_line
from wxclaude.core.list_spec import ListSpec
from wxclaude.core.messages import ToolUse
from wxclaude.i18n import _
from wxclaude.ui.list_dialog import ListDialog


class ToolsDialog(ListDialog):
    """The tools Claude used for an answer, one per line, and everything about the selected one."""

    def __init__(self, parent: wx.Window, tools: Sequence[ToolUse]) -> None:
        super().__init__(
            parent,
            ListSpec(
                _("Tools used"),
                list_label=_("&Tools used"),
                lines=[tool_line(tool) for tool in tools],
                details=[tool_detail(tool) for tool in tools],
                details_label=_("&Details"),
            ),
        )


class TableDialog(ListDialog):
    """The rows of a table, one per line (``Name: x, Size: 3``). *Copy the table* closes the dialog
    with ``wx.ID_COPY``."""

    def __init__(self, parent: wx.Window, table: Table) -> None:
        rows = [table.row_line(row) for row in table.rows]
        spec = ListSpec(
            _("Table"),
            list_label=_("&Rows"),
            lines=rows or [_("The table has no row.")],
        )
        super().__init__(parent, spec, [(wx.ID_COPY, _("Copy the &table"))])


class LinksDialog(ListDialog):
    """The links of a message, one per line. *Open in the browser* (only for a web or mail
    address) closes the dialog with ``wx.ID_OPEN``, *Copy the address* with ``wx.ID_COPY``;
    ``selection`` tells which link."""

    def __init__(self, parent: wx.Window, links: Sequence[Link], selected: int = 0) -> None:
        spec = ListSpec(
            _("Links"),
            list_label=_("&Links"),
            lines=[link.label() for link in links],
            selection=selected,
        )
        actions = [(wx.ID_OPEN, _("&Open in the browser")), (wx.ID_COPY, _("Copy the &address"))]
        super().__init__(parent, spec, actions)

"""A read-only dialog with a list of lines and, below it, the details of the selected line.

It is the shape of the dialogs that show what the conversation view does not: the tasks, the tools
used, the rows of a table, the links of a message. Information is in the text of each line,
separated by commas (no columns). The buttons given as ``actions`` close the dialog with their
identifier, the caller does the work.
"""

from collections.abc import Sequence

import wx

from wxclaude.core.list_spec import ListSpec


class ListDialog(wx.Dialog):
    """Lines to choose from, optional details of the chosen one, a Close button and actions.

    ``spec`` is what it shows (data only); ``actions`` are the buttons, each an identifier of the
    interface library and a label. The list has the initial focus; without ``spec.details`` there
    is no details field.
    """

    def __init__(
        self,
        parent: wx.Window,
        spec: ListSpec,
        actions: Sequence[tuple[int, str]] = (),
    ) -> None:
        super().__init__(parent, title=spec.title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._details = list(spec.details) if spec.details is not None else None
        # Each label is created right before its control so that screen readers pair them.
        label = wx.StaticText(self, label=spec.list_label)
        self._list = wx.ListBox(
            self, choices=list(spec.lines), style=wx.LB_SINGLE, name=spec.list_name
        )
        self._list.SetMinSize(
            wx.Size(self._list.GetCharWidth() * 70, self._list.GetCharHeight() * 8)
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._list, 1, wx.EXPAND | wx.ALL, 8)
        self._text: wx.TextCtrl | None = None
        if self._details is not None:
            details_text = wx.StaticText(self, label=spec.details_label)
            self._text = wx.TextCtrl(
                self, style=wx.TE_MULTILINE | wx.TE_READONLY, name=spec.details_name
            )
            self._text.SetMinSize(
                wx.Size(self._text.GetCharWidth() * 70, self._text.GetCharHeight() * 8)
            )
            sizer.Add(details_text, 0, wx.LEFT | wx.RIGHT, 8)
            sizer.Add(self._text, 1, wx.EXPAND | wx.ALL, 8)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for identifier, action_label in actions:
            buttons.Add(wx.Button(self, identifier, action_label), 0, wx.RIGHT, 6)
        buttons.Add(wx.Button(self, wx.ID_CLOSE), 0)
        sizer.Add(buttons, 0, wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.SetEscapeId(wx.ID_CLOSE)
        self.Bind(wx.EVT_BUTTON, self._on_button)
        self._list.Bind(wx.EVT_LISTBOX, self._on_select)
        if spec.lines:
            self._list.SetSelection(min(max(spec.selection, 0), len(spec.lines) - 1))
        self._show_details()
        self._list.SetFocus()

    @property
    def selection(self) -> int:
        """The index of the selected line, -1 when there is none."""
        return int(self._list.GetSelection())

    @property
    def details_text(self) -> str:
        """What the details field shows ('' without a details field)."""
        return str(self._text.GetValue()) if self._text is not None else ""

    def _show_details(self) -> None:
        if self._text is None or self._details is None:
            return
        index = self.selection
        self._text.ChangeValue(self._details[index] if 0 <= index < len(self._details) else "")

    def _on_select(self, _event: wx.CommandEvent) -> None:
        self._show_details()

    def _on_button(self, event: wx.CommandEvent) -> None:
        self.EndModal(event.GetId())

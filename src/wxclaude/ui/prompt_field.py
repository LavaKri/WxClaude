"""The field where the prompt is typed, with a context menu of its own."""

import wx

from wxclaude.i18n import _
from wxclaude.ui.menu_keys import is_menu_key, is_shift_f10


class PromptField(wx.TextCtrl):
    """A plain multi-line field. Its context menu (right click, Applications key, Shift+F10)
    offers Cut, Copy and Paste, greyed when they do not apply."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.TE_MULTILINE, name=_("Prompt"))
        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.Bind(wx.EVT_KEY_UP, self._on_key_up)

    def build_menu(self) -> wx.Menu:
        """The context menu; the items that do not apply are greyed."""
        menu = wx.Menu()
        commands = (
            (_("Cu&t"), self.CanCut(), self.Cut),
            (_("&Copy"), self.CanCopy(), self.Copy),
            (_("&Paste"), self.CanPaste(), self.Paste),
        )
        for label, enabled, command in commands:
            item = menu.Append(wx.ID_ANY, label)
            item.Enable(enabled)
            menu.Bind(wx.EVT_MENU, lambda _event, run=command: run(), item)
        return menu

    def _on_context_menu(self, event: wx.ContextMenuEvent) -> None:
        """The native menu of the field is replaced by ours."""
        if event.GetPosition() == wx.DefaultPosition:
            self._open_menu(self._caret_position())
        else:
            self._open_menu(self.ScreenToClient(event.GetPosition()))

    def _open_menu(self, position: wx.Point) -> None:
        menu = self.build_menu()
        self.PopupMenu(menu, position)
        menu.Destroy()

    def _caret_position(self) -> wx.Point:
        """Where the menu opens when the keyboard asks for it: at the caret."""
        position = self.PositionToCoords(self.GetInsertionPoint())
        return wx.Point(0, 0) if position == wx.DefaultPosition else position

    def _on_key(self, event: wx.KeyEvent) -> None:
        if is_shift_f10(event):
            self._open_menu(self._caret_position())  # the field would open its own menu
            return
        event.Skip()

    def _on_key_up(self, event: wx.KeyEvent) -> None:
        if not is_menu_key(event):  # the field would open its own menu when the key goes up
            event.Skip()

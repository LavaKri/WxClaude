"""The conversation view: a read-only text field holding the conversation as Markdown."""

from collections.abc import Callable

import wx

from wxclaude.core.conversation.blocks import (
    BlockKind,
)
from wxclaude.core.conversation.caret_anchor import CaretAnchor
from wxclaude.core.conversation.conversation_document import ConversationDocument, MessageSpan
from wxclaude.core.conversation.details import DetailAction, message_details
from wxclaude.core.conversation.headings import (
    from_utf16,
    to_utf16,
)
from wxclaude.core.conversation.messages import Message, Role
from wxclaude.i18n import _
from wxclaude.presenters.conversation_navigator import ConversationNavigator
from wxclaude.ui.menu_keys import is_menu_key, is_shift_f10

_LEVEL_KEYS = {ord(str(level)): level for level in range(1, 7)}
_HEADING_KEY = ord("H")
_BLOCK_KEYS = {
    ord("T"): BlockKind.TABLE,
    ord("L"): BlockKind.LIST,
    ord("I"): BlockKind.ITEM,
    ord("K"): BlockKind.LINK,
}
#: The labels of the context menu (translated when the menu opens, not at import).
_MENU_LABELS: dict[DetailAction, Callable[[], str]] = {
    DetailAction.TOOLS: lambda: _("Show the &tools used…"),
    DetailAction.TABLE: lambda: _("Show the t&able…\tSpace"),  # the shortcut shown is the key
    DetailAction.LINKS: lambda: _("Show the &links…"),
    DetailAction.COPY_MESSAGE: lambda: _("&Copy the message"),
    DetailAction.COPY_EXCHANGE: lambda: _("Copy the &exchange"),
}


class ConversationView(wx.TextCtrl):
    """Shows the messages. With Shift the keys go backwards: ``H`` and ``1`` to ``6`` jump between
    headings, ``T`` between tables, ``L`` between lists and ``I`` between the items of lists (the
    lists and items of level 1 only).

    The screen reader does not read the line when the application moves the caret, so every jump
    is announced through ``say``. The view never takes the focus by itself.

    The context menu (Applications key, Shift+F10) offers what the message at the caret holds
    (its tools, the table or the links in it) and to copy it; the choice is handed to ``on_action``
    with the message and the line of its text that holds the caret (-1 on its title).
    """

    def __init__(
        self,
        parent: wx.Window,
        say: Callable[..., None],
        on_action: Callable[[DetailAction, Message, int], None] | None = None,
        on_position: Callable[[int, int], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name=_("Conversation"),
        )
        self._say = say
        self._on_action = on_action
        self._on_position = on_position
        self._position: tuple[int, int] | None = None  # the last one reported
        self._navigator = ConversationNavigator(
            lambda: self._document.text, self._caret_index, self._move, say
        )
        self._document = ConversationDocument()
        self._messages: list[Message] = []  # all of them, the hidden ones too
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.Bind(wx.EVT_KEY_UP, self._on_key_up)
        self.Bind(wx.EVT_LEFT_UP, self._on_mouse)
        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

    @property
    def document(self) -> ConversationDocument:
        return self._document

    @property
    def messages(self) -> list[Message]:
        """A copy of all the messages, the hidden ones too."""
        return list(self._messages)

    def set_messages(self, messages: list[Message]) -> None:
        """Replace everything (new conversation, history loaded, field rebuilt)."""
        self._messages = list(messages)
        self.ChangeValue(self._document.rebuild(self._messages))
        self.SetInsertionPoint(0)
        self.report_position()

    def clear_messages(self) -> None:
        self._messages = []
        self._document.clear()
        self.ChangeValue("")
        self.report_position()

    def set_show_hidden(self, show: bool) -> None:
        """Show or hide the system messages (noise); the caret stays on its message."""
        if show == self._document.show_hidden:
            return
        self._document.show_hidden = show
        self.replace_messages(self._messages)

    def set_show_tools_summary(self, show: bool) -> None:
        """Show or hide the line under each answer that sums up its tools; the caret stays."""
        if show == self._document.tools_summary:
            return
        self._document.tools_summary = show
        self.replace_messages(self._messages)

    def set_without_marks(self, without: bool) -> None:
        """Remove (or show) the marks of bold and italic in the text; the caret stays."""
        if without == self._document.without_marks:
            return
        self._document.without_marks = without
        self.replace_messages(self._messages)

    def replace_messages(self, messages: list[Message]) -> None:
        """Show ``messages`` again; the caret stays on its message, at the same place in it (or at
        the end when it was at the end), and the focus is not touched."""
        anchor = CaretAnchor.take(self._document, self._caret_index())
        self._messages = list(messages)
        self.ChangeValue(self._document.rebuild(self._messages))
        position = anchor.position(self._document)
        self.SetInsertionPoint(to_utf16(self._document.text, position))
        self.report_position()

    def append_message(self, message: Message) -> None:
        """Add a complete message at the end; the caret stays where the user left it."""
        self._messages.append(message)
        added = self._document.append(message)
        if not added:
            return
        caret = self.GetInsertionPoint()
        self.AppendText(added)
        self.SetInsertionPoint(caret)
        self.report_position()

    def markdown_text(self) -> str:
        """The text of the view as Markdown, with the marks of bold and italic (for the export)."""
        document = ConversationDocument(
            show_hidden=self._document.show_hidden,
            tools_summary=self._document.tools_summary,
        )
        return document.rebuild(self._messages)

    @property
    def text(self) -> str:
        """The text of the view."""
        return self._document.text

    def exchange_of(self, message: Message) -> str:
        """The prompt of the exchange ``message`` belongs to and all the answers to it."""
        return self._document.exchange_of(message.id)

    def selection_indexes(self) -> tuple[int, int]:
        """The selection as Python string indexes (both the caret when nothing is selected)."""
        start, end = self.GetSelection()
        text = self._document.text
        return from_utf16(text, start), from_utf16(text, end)

    def select_range(self, start: int, end: int) -> None:
        """Select the characters ``start`` to ``end`` (Python indexes) and give them the focus."""
        text = self._document.text
        self.SetFocus()
        self.SetSelection(to_utf16(text, start), to_utf16(text, end))
        self.ShowPosition(to_utf16(text, start))
        self.report_position()

    def focus_last_prompt(self) -> None:
        """Give the focus to the view, the caret at the start of the last prompt of the user."""
        position = 0
        for span in reversed(self._document.spans):
            if span.message.role is Role.USER:
                position = to_utf16(self._document.text, span.start)
                break
        self.SetFocus()
        self.SetInsertionPoint(position)
        self.ShowPosition(position)
        self.report_position()

    def shows(self, messages: list[Message]) -> bool:
        """Would the view show exactly ``messages``? (Compared on the text it would hold.)"""
        document = ConversationDocument(
            show_hidden=self._document.show_hidden,
            tools_summary=self._document.tools_summary,
            without_marks=self._document.without_marks,
        )
        return document.rebuild(messages) == self._document.text

    def adopt_details(self, messages: list[Message]) -> None:
        """Take ``messages`` as the data when they give the text the view already shows.

        The field is not touched (the caret and the focus stay): only what the messages hold
        without displaying it (tools, usage) is new. Messages shown live have none.
        """
        if not self.shows(messages):
            return
        self._messages = list(messages)
        self._document.rebuild(self._messages)

    def message_at_caret(self) -> MessageSpan | None:
        """The span of the message that holds the caret."""
        return self._document.span_at(self._caret_index())

    def report_position(self) -> None:
        """Tell ``on_position`` which prompt the caret is in, (number, total), when it changed."""
        if self._on_position is None or not self:
            return
        position = self._document.prompt_position(self._caret_index())
        if position != self._position:
            self._position = position
            self._on_position(*position)

    def _on_mouse(self, event: wx.MouseEvent) -> None:
        event.Skip()
        wx.CallAfter(self.report_position)  # once the control has moved the caret

    def _caret_index(self) -> int:
        return from_utf16(self._document.text, self.GetInsertionPoint())

    def _on_context_menu(self, event: wx.ContextMenuEvent) -> None:
        """Right click or Applications key. The native menu of the field (undo, redo, cut,
        paste...) is never shown: it has nothing to do in a read-only view."""
        if event.GetPosition() == wx.DefaultPosition:
            self._open_menu(self._caret_position())
        else:
            self._open_menu(self.ScreenToClient(event.GetPosition()))

    def _open_menu(self, position: wx.Point) -> None:
        """Pop up the menu of the message at the caret at ``position`` (client coordinates);
        nothing opens when no message holds the caret."""
        span = self.message_at_caret()
        if span is None or self._on_action is None:
            return
        line = self._document.body_line(span, self._caret_index())
        menu = wx.Menu()
        for action in message_details(span.message).actions(line):
            item = menu.Append(wx.ID_ANY, _MENU_LABELS[action]())
            menu.Bind(wx.EVT_MENU, self._menu_handler(action, span.message, line), item)
        self.PopupMenu(menu, position)
        menu.Destroy()

    def _menu_handler(
        self, action: DetailAction, message: Message, line: int
    ) -> Callable[[wx.CommandEvent], None]:
        def handle(_event: wx.CommandEvent) -> None:
            if self._on_action is not None:
                wx.CallAfter(self._on_action, action, message, line)  # once the menu is closed

        return handle

    def _caret_position(self) -> wx.Point:
        """Where the menu opens when the keyboard asks for it: at the caret."""
        position = self.PositionToCoords(self.GetInsertionPoint())
        return wx.Point(0, 0) if position == wx.DefaultPosition else position

    def _on_key_up(self, event: wx.KeyEvent) -> None:
        # The rich text field would open its own menu when the key goes up. Shift+F10 opened ours
        # when it went down; the Applications key asks for it through EVT_CONTEXT_MENU.
        if not is_menu_key(event):
            event.Skip()

    def _on_key(self, event: wx.KeyEvent) -> None:
        wx.CallAfter(self.report_position)  # once the control has moved the caret
        if is_shift_f10(event):
            # The rich text field opens its own menu for this key without telling anyone.
            self._open_menu(self._caret_position())
            return
        if event.ControlDown() or event.AltDown() or event.MetaDown():
            event.Skip()
            return
        code = event.GetKeyCode()
        if code == wx.WXK_SPACE and not event.ShiftDown():
            if not self._open_details_at_caret():
                event.Skip()
        elif code in _BLOCK_KEYS:
            self._navigator.jump_block(_BLOCK_KEYS[code], backwards=event.ShiftDown())
        elif code == _HEADING_KEY:
            self._navigator.jump_heading(None, backwards=event.ShiftDown())
        elif code in _LEVEL_KEYS:
            self._navigator.jump_heading(_LEVEL_KEYS[code], backwards=event.ShiftDown())
        else:
            event.Skip()

    def _open_details_at_caret(self) -> bool:
        """Space: show what the caret is on (for now the table it is in); False if it is on
        nothing that has a display of its own."""
        span = self.message_at_caret()
        if span is None or self._on_action is None:
            return False
        line = self._document.body_line(span, self._caret_index())
        if message_details(span.message).table_at(line) is None:
            return False
        wx.CallAfter(self._on_action, DetailAction.TABLE, span.message, line)
        return True

    def _move(self, index: int) -> None:
        """Put the caret at the Python index ``index``."""
        position = to_utf16(self._document.text, index)
        self.SetInsertionPoint(position)
        self.ShowPosition(position)
        self.report_position()

"""The conversation view: a read-only text field holding the conversation as Markdown."""

from collections.abc import Callable

import wx

from wxclaude.core.announcements import Announce
from wxclaude.core.conversation_document import ConversationDocument, MessageSpan
from wxclaude.core.headings import (
    Heading,
    from_utf16,
    next_heading,
    parse_headings,
    previous_heading,
    to_utf16,
)
from wxclaude.core.messages import Message
from wxclaude.i18n import _

_LEVEL_KEYS = {ord(str(level)): level for level in range(1, 7)}
_HEADING_KEY = ord("T")


class ConversationView(wx.TextCtrl):
    """Shows the messages; ``T`` and ``1`` to ``6`` (with Shift: backwards) jump between headings.

    The screen reader does not read the line when the application moves the caret, so every jump
    is announced through ``say``. The view never takes the focus by itself.
    """

    def __init__(self, parent: wx.Window, say: Callable[..., None]) -> None:
        super().__init__(
            parent,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name=_("Conversation"),
        )
        self._say = say
        self._document = ConversationDocument()
        self._messages: list[Message] = []  # all of them, the hidden ones too
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    @property
    def document(self) -> ConversationDocument:
        return self._document

    def set_messages(self, messages: list[Message]) -> None:
        """Replace everything (new conversation, history loaded, field rebuilt)."""
        self._messages = list(messages)
        self.ChangeValue(self._document.rebuild(self._messages))
        self.SetInsertionPoint(0)

    def clear_messages(self) -> None:
        self._messages = []
        self._document.clear()
        self.ChangeValue("")

    def set_show_hidden(self, show: bool) -> None:
        """Show or hide the system messages (noise); the caret stays on its message."""
        if show == self._document.show_hidden:
            return
        span = self.message_at_caret()
        self._document.show_hidden = show
        self.ChangeValue(self._document.rebuild(self._messages))
        position = 0
        if span is not None:
            position = next(
                (
                    to_utf16(self._document.text, new.start)
                    for new in self._document.spans
                    if new.message.id == span.message.id
                ),
                0,
            )
        self.SetInsertionPoint(position)

    def append_message(self, message: Message) -> None:
        """Add a complete message at the end; the caret stays where the user left it."""
        self._messages.append(message)
        added = self._document.append(message)
        if not added:
            return
        caret = self.GetInsertionPoint()
        self.AppendText(added)
        self.SetInsertionPoint(caret)

    def shows(self, messages: list[Message]) -> bool:
        """Would the view show exactly ``messages``? (Compared on the text it would hold.)"""
        document = ConversationDocument(show_hidden=self._document.show_hidden)
        return document.rebuild(messages) == self._document.text

    def message_at_caret(self) -> MessageSpan | None:
        """The span of the message that holds the caret."""
        return self._document.span_at(self._caret_index())

    def _caret_index(self) -> int:
        return from_utf16(self._document.text, self.GetInsertionPoint())

    def _on_key(self, event: wx.KeyEvent) -> None:
        if event.ControlDown() or event.AltDown() or event.MetaDown():
            event.Skip()
            return
        code = event.GetKeyCode()
        level: int | None
        if code == _HEADING_KEY:
            level = None
        elif code in _LEVEL_KEYS:
            level = _LEVEL_KEYS[code]
        else:
            event.Skip()
            return
        self._jump(level, backwards=event.ShiftDown())

    def _jump(self, level: int | None, *, backwards: bool) -> None:
        headings = parse_headings(self._document.text)
        position = self._caret_index()
        if backwards:
            target = previous_heading(headings, position, level)
        else:
            target = next_heading(headings, position, level)
        if target is None:
            self._say(self._missing(level, backwards=backwards), level=level)
            return
        self._go_to(target)

    @staticmethod
    def _missing(level: int | None, *, backwards: bool) -> Announce:
        if level is None:
            return Announce.NO_PREVIOUS_HEADING if backwards else Announce.NO_NEXT_HEADING
        if backwards:
            return Announce.NO_PREVIOUS_HEADING_OF_LEVEL
        return Announce.NO_NEXT_HEADING_OF_LEVEL

    def _go_to(self, heading: Heading) -> None:
        position = to_utf16(self._document.text, heading.start)
        self.SetInsertionPoint(position)
        self.ShowPosition(position)
        self._say(Announce.HEADING, title=heading.title, level=heading.level)

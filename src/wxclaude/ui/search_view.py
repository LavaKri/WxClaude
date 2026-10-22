"""The wx side of the search: the view of ``presenters/search_presenter.py``."""

import wx

from wxclaude.core.conversation.search import SearchOptions
from wxclaude.core.speech.announcements import Announce
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.search_dialog import SearchDialog


class WxSearchView:
    """The Find dialog, the conversation view and the messages of the search."""

    def __init__(self, view: ConversationView, feedback: Feedback) -> None:
        self._view = view
        self._feedback = feedback

    def ask_search(self, last: SearchOptions | None) -> SearchOptions | None:
        with SearchDialog(self._view.GetTopLevelParent(), last) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return None
            options: SearchOptions = dialog.options
        return options

    def text(self) -> str:
        return self._view.text

    def selection(self) -> tuple[int, int]:
        return self._view.selection_indexes()

    def select(self, start: int, end: int) -> None:
        self._view.select_range(start, end)

    def say(self, announce: Announce, **values: object) -> None:
        self._feedback.say(announce, **values)

    def show_info(self, message: str) -> None:
        self._feedback.show_info(message)

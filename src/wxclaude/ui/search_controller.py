"""Search in the conversation: Find…, Find next and Find previous (see ``docs/interface.md``)."""

from collections.abc import Callable

import wx

from wxclaude.core.announcements import Announce
from wxclaude.core.search import SearchOptions, find_next, find_previous, line_at
from wxclaude.i18n import _
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.search_dialog import SearchDialog


class SearchController:
    """Keeps the last search and walks through its occurrences in the conversation view.

    ``show_modal`` shows a dialog and returns its result, ``say`` announces, ``show_info`` tells
    the user that there is no more occurrence.
    """

    def __init__(
        self,
        view: ConversationView,
        show_modal: Callable[[wx.Dialog], int],
        say: Callable[..., None],
        show_info: Callable[[str], None],
    ) -> None:
        self._view = view
        self._show_modal = show_modal
        self._say = say
        self._show_info = show_info
        self.options: SearchOptions | None = None  # the last search

    def find(self) -> None:
        """Ask what to look for, then go to the next occurrence."""
        with SearchDialog(self._view.GetTopLevelParent(), self.options) as dialog:
            if self._show_modal(dialog) != wx.ID_OK:
                return
            self.options = dialog.options
        self.search(backwards=False)

    def find_next(self) -> None:
        """Repeat the last search forward; without one, ask what to look for."""
        if self.options is None:
            self.find()
        else:
            self.search(backwards=False)

    def find_previous(self) -> None:
        """Repeat the last search backwards; without one, ask what to look for."""
        if self.options is None:
            self.find()
        else:
            self.search(backwards=True)

    def search(self, *, backwards: bool) -> None:
        """Go to the next or previous occurrence of the last search term.

        The search starts after the selection (before it when going backwards), so repeating it
        walks through the occurrences. The occurrence is selected, gets the focus and its whole
        line is announced; at the end a dialog says there is no more.
        """
        options = self.options
        if options is None:
            return
        view = self._view
        text = view.text
        start, end = view.selection_indexes()
        match = find_previous(text, options, start) if backwards else find_next(text, options, end)
        if match is None:
            message = (
                _('No previous occurrence of "{term}".')
                if backwards
                else _('No next occurrence of "{term}".')
            )
            self._show_info(message.format(term=options.term))
            return
        view.select_range(match.start, match.end)
        self._say(Announce.SEARCH_FOUND, line=line_at(text, match.start))

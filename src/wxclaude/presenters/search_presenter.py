"""Search in the conversation: Find…, Find next and Find previous (see ``docs/interface.md``)."""

from typing import Protocol

from wxclaude.core.announcements import Announce
from wxclaude.core.search import SearchOptions, find_next, find_previous, line_at
from wxclaude.i18n import _


class SearchView(Protocol):
    """What the presenter asks of the interface to search the conversation."""

    def ask_search(self, last: SearchOptions | None) -> SearchOptions | None:
        """Ask what to look for (``last`` proposed); None if cancelled."""
        ...

    def text(self) -> str:
        """The text of the conversation, as displayed."""
        ...

    def selection(self) -> tuple[int, int]:
        """The selection of the conversation (Python indexes; the caret twice without one)."""
        ...

    def select(self, start: int, end: int) -> None:
        """Select ``start`` to ``end`` in the conversation and give it the focus."""
        ...

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, where the category of ``announce`` says."""
        ...

    def show_info(self, message: str) -> None:
        """Tell the user that there is no more occurrence."""
        ...


class SearchPresenter:
    """Keeps the last search and walks through its occurrences in the conversation."""

    def __init__(self, view: SearchView) -> None:
        self._view = view
        self.options: SearchOptions | None = None  # the last search

    def find(self) -> None:
        """Ask what to look for, then go to the next occurrence."""
        options = self._view.ask_search(self.options)
        if options is None:
            return
        self.options = options
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
        line is announced; at the end the user is told there is no more.
        """
        options = self.options
        if options is None:
            return
        text = self._view.text()
        start, end = self._view.selection()
        match = find_previous(text, options, start) if backwards else find_next(text, options, end)
        if match is None:
            message = (
                _('No previous occurrence of "{term}".')
                if backwards
                else _('No next occurrence of "{term}".')
            )
            self._view.show_info(message.format(term=options.term))
            return
        self._view.select(match.start, match.end)
        self._view.say(Announce.SEARCH_FOUND, line=line_at(text, match.start))

"""The presenter of the search, with a fake view: no wx, no window."""

import pytest

from wxclaude.core.announcements import Announce
from wxclaude.core.search import SearchOptions
from wxclaude.presenters.search_presenter import SearchPresenter

pytestmark = pytest.mark.unit

TEXT = "# You say: fish\nfish\n\n## Answer\nA Fish here.\n"


class FakeView:
    """A text with a selection; answers the Find dialog with ``answer``."""

    def __init__(self, answer: SearchOptions | None = None) -> None:
        self.answer = answer
        self.asked: list[SearchOptions | None] = []
        self.selected = (0, 0)
        self.said: list[tuple[Announce, dict[str, object]]] = []
        self.infos: list[str] = []

    def ask_search(self, last: SearchOptions | None) -> SearchOptions | None:
        self.asked.append(last)
        return self.answer

    def text(self) -> str:
        return TEXT

    def selection(self) -> tuple[int, int]:
        return self.selected

    def select(self, start: int, end: int) -> None:
        self.selected = (start, end)

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append((announce, values))

    def show_info(self, message: str) -> None:
        self.infos.append(message)


def test_find_asks_then_selects_and_announces_the_line() -> None:
    view = FakeView(SearchOptions("here"))
    presenter = SearchPresenter(view)
    presenter.find()
    start = TEXT.index("here")
    assert view.selected == (start, start + 4)
    assert view.said == [(Announce.SEARCH_FOUND, {"line": "A Fish here."})]


def test_repeating_walks_through_the_occurrences_and_stops_at_the_end() -> None:
    view = FakeView()
    presenter = SearchPresenter(view)
    presenter.options = SearchOptions("fish")
    starts = []
    for _ in range(3):
        presenter.find_next()
        starts.append(view.selected[0])
    assert starts == [TEXT.index("fish"), TEXT.index("fish\n\n"), TEXT.index("Fish")]
    presenter.find_next()
    assert view.infos == ['No next occurrence of "fish".']
    presenter.find_previous()
    assert view.selected[0] == TEXT.index("fish\n\n")


def test_without_a_last_search_next_and_previous_ask_and_the_last_one_is_proposed() -> None:
    view = FakeView(None)
    presenter = SearchPresenter(view)
    presenter.find_next()
    presenter.find_previous()
    assert view.asked == [None, None]
    assert presenter.options is None  # cancelled: nothing is kept
    view.answer = SearchOptions("fish")
    presenter.find()
    presenter.options = SearchOptions("zebra")
    presenter.find_next()
    assert view.infos == ['No next occurrence of "zebra".']

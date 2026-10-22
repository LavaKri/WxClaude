"""The presenter of the announcement categories, with a fake page: no wx, no window."""

import pytest

from wxclaude.core.config.settings import Settings
from wxclaude.core.speech.announcements import CATEGORIES, END_OF_ANSWER, PROGRESS, Destination
from wxclaude.presenters.announcements_presenter import AnnouncementsPresenter

pytestmark = pytest.mark.unit

END = CATEGORIES.index(END_OF_ANSWER)


class FakePage:
    def __init__(self) -> None:
        self.destinations: list[str] = []
        self.choices: list[str] = []
        self.selected = -1

    def show_destinations(self, labels: list[str]) -> None:
        self.destinations = labels

    def show_choices(self, labels: list[str], selected: int) -> None:
        self.choices = labels
        self.selected = selected


def test_the_page_shows_every_category_with_its_destination() -> None:
    page = FakePage()
    AnnouncementsPresenter(page, Settings.load(None))
    assert len(page.destinations) == len(CATEGORIES)
    assert page.destinations[END] == "Message.wav"


def test_selecting_a_category_shows_what_it_accepts() -> None:
    page = FakePage()
    presenter = AnnouncementsPresenter(page, Settings.load(None))
    presenter.select(END)
    assert page.choices == ["No announcement", "Message", "Message.wav"]
    assert page.selected == 2


def test_a_choice_is_kept_until_apply_and_the_default_can_be_restored() -> None:
    settings = Settings.load(None)
    page = FakePage()
    presenter = AnnouncementsPresenter(page, settings)
    presenter.select(END)
    presenter.choose(1)
    assert page.destinations[END] == "Message"
    assert settings.destination_for(END_OF_ANSWER) is Destination.SOUND_1
    presenter.apply(settings)
    assert settings.destination_for(END_OF_ANSWER) is Destination.MESSAGE
    presenter.restore_default()
    assert presenter.destination(END_OF_ANSWER) is Destination.SOUND_1


def test_without_a_selected_category_nothing_changes() -> None:
    page = FakePage()
    presenter = AnnouncementsPresenter(page, Settings.load(None))
    presenter.select(-1)
    presenter.choose(0)
    presenter.restore_default()
    assert presenter.destination(PROGRESS) is PROGRESS.default

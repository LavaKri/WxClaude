"""The categories of announcements of the Screen reader page of the Preferences: the destination
of each, edited until OK (see ``docs/accessibility.md``)."""

from typing import Protocol

from wxclaude.core.config.settings import Settings
from wxclaude.core.speech.announcements import CATEGORIES, Category, Destination
from wxclaude.i18n import _


class AnnouncementsView(Protocol):
    """What the presenter asks of the page."""

    def show_destinations(self, labels: list[str]) -> None:
        """The destination of every category, in the order of ``CATEGORIES``."""
        ...

    def show_choices(self, labels: list[str], selected: int) -> None:
        """The destinations the selected category accepts, ``selected`` being the current one."""
        ...


class AnnouncementsPresenter:
    """The destinations being edited; the settings only change with ``apply``."""

    def __init__(self, view: AnnouncementsView, settings: Settings) -> None:
        self._view = view
        self._destinations = {c.id: settings.destination_for(c) for c in CATEGORIES}
        self._selected: Category | None = None
        self._view.show_destinations(self._labels())

    def destination(self, category: Category) -> Destination:
        """The destination chosen for ``category`` so far."""
        return self._destinations[category.id]

    def select(self, index: int) -> None:
        """The category at ``index`` of the list is selected (-1: none)."""
        self._selected = CATEGORIES[index] if 0 <= index < len(CATEGORIES) else None
        self._show_choices()

    def choose(self, index: int) -> None:
        """The destination at ``index`` of the choices is chosen for the selected category."""
        category = self._selected
        if category is not None and 0 <= index < len(category.choices):
            self._set(category, category.choices[index])

    def restore_default(self) -> None:
        """The selected category goes back to its default destination."""
        if self._selected is not None:
            self._set(self._selected, self._selected.default)

    def apply(self, settings: Settings) -> None:
        """Store the destinations chosen into ``settings``."""
        for category in CATEGORIES:
            settings.set_destination(category, self._destinations[category.id])

    def _set(self, category: Category, destination: Destination) -> None:
        self._destinations[category.id] = destination
        self._view.show_destinations(self._labels())
        self._show_choices()

    def _labels(self) -> list[str]:
        return [_(self._destinations[category.id].label) for category in CATEGORIES]

    def _show_choices(self) -> None:
        category = self._selected
        if category is None:
            return
        labels = [_(destination.label) for destination in category.choices]
        self._view.show_choices(labels, category.choices.index(self._destinations[category.id]))

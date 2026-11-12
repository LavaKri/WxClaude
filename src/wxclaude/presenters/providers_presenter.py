"""The Providers page of the Preferences: the providers and their keys (``docs/providers.md``).

Every action is saved at once (the providers file is written after each). The key of a provider is
typed in the form of the provider (``provider_form_presenter.py``), saved encrypted when the form is
accepted, and never shown again: the list only says whether a key is saved.
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Protocol

from wxclaude.core.config.providers import (
    CLAUDE,
    KEY_NONE,
    Provider,
    ProviderStore,
    new_provider_id,
)
from wxclaude.core.errors import JsonStoreError, KeyVaultError, ProviderError
from wxclaude.i18n import _
from wxclaude.presenters.provider_form_presenter import ProviderEdit


class ProvidersView(Protocol):
    """What the presenter asks of the page."""

    def show_providers(self, lines: list[str], selected: int) -> None:
        """The providers, one line each, and the one selected (-1: none)."""
        ...

    def ask_provider(self, edit: ProviderEdit | None) -> ProviderEdit | None:
        """The form of a provider, empty for ``None`` (a new one), else filled with ``edit`` (a
        copy the view may change). None: cancelled."""
        ...

    def confirm_delete(self, name: str) -> bool:
        """Ask whether to delete the provider ``name`` and its key (No by default)."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class ProvidersPresenter:
    """The providers of the store, selected one at a time."""

    def __init__(self, view: ProvidersView, store: ProviderStore) -> None:
        self._view = view
        self._store = store
        self._selected = 0  # an index of ``store.providers()``
        self._refresh()

    @property
    def selected(self) -> Provider | None:
        """The selected provider (None if the list is empty, which it never is: Claude)."""
        providers = self._store.providers()
        return providers[self._selected] if 0 <= self._selected < len(providers) else None

    def select(self, index: int) -> None:
        """The line at ``index`` is selected."""
        self._selected = index

    def can_edit(self) -> bool:
        """Can the selected provider be changed or deleted? (Not Claude.)"""
        provider = self.selected
        return provider is not None and not provider.is_builtin

    def add(self) -> None:
        """Ask for a new provider and keep it, with its key if one was typed."""
        edit = self._ask_valid(None)
        if edit is None:
            return
        provider = edit.provider
        provider.id = new_provider_id(provider.name, {p.id for p in self._store.providers()})

        def action() -> None:
            self._store.add(provider)
            self._apply_key(edit)

        if self._run(action):
            self._selected = len(self._store.providers()) - 1
            self._refresh()

    def edit(self) -> None:
        """Ask for the changes of the selected provider and keep them, with its key."""
        current = self.selected
        if current is None or current.is_builtin:
            return
        edit = self._ask_valid(ProviderEdit(replace(current), self._store.has_key(current.id)))
        if edit is None:
            return
        edit.provider.id = current.id

        def action() -> None:
            self._store.update(edit.provider)
            self._apply_key(edit)

        if self._run(action):
            self._refresh()

    def delete(self) -> None:
        """Delete the selected provider and its key, after a confirmation."""
        current = self.selected
        if current is None or current.is_builtin or not self._view.confirm_delete(current.name):
            return
        if self._run(lambda: self._store.remove(current.id)):
            self._selected = 0
            self._refresh()

    # -- inside ---------------------------------------------------------------------------

    def _ask_valid(self, edit: ProviderEdit | None) -> ProviderEdit | None:
        """The form again, with what was typed, until the provider is valid or it is cancelled."""
        entered = self._view.ask_provider(edit)
        while entered is not None:
            problem = entered.provider.problem()
            if problem is None:
                return entered
            self._view.show_error(problem)
            entered = self._view.ask_provider(entered)
        return None

    def _apply_key(self, edit: ProviderEdit) -> None:
        """Keep the key typed in the form, or forget the saved one the user removed."""
        if edit.key and edit.provider.needs_key:
            self._store.set_key(edit.provider.id, edit.key)
        elif edit.remove_key:
            self._store.remove_key(edit.provider.id)

    def _run(self, action: Callable[[], None]) -> bool:
        """Do ``action`` and write the file; False (with the error shown) if either fails."""
        try:
            action()
            self._store.save()
        except (ProviderError, KeyVaultError, JsonStoreError) as error:
            self._view.show_error(str(error))
            return False
        return True

    def _refresh(self) -> None:
        providers = self._store.providers()
        self._selected = min(max(self._selected, 0), len(providers) - 1)
        self._view.show_providers([self._line(p) for p in providers], self._selected)

    def _line(self, provider: Provider) -> str:
        if provider is CLAUDE:
            return _("{name}, built in").format(name=provider.name)
        return _("{name}, {address}, {key}").format(
            name=provider.name, address=provider.base_url, key=self._key_text(provider)
        )

    def _key_text(self, provider: Provider) -> str:
        if provider.key_source == KEY_NONE:
            return _("no key needed")
        return _("key saved") if self._store.has_key(provider.id) else _("no key")

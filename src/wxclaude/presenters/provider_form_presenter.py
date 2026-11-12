"""The form of a provider: its key and the check of the data its server gives (``providers.md``).

The form edits a copy. A key typed in it, or the removal of the saved one, is only held here and is
kept by the page of the providers when the form is accepted (``ProviderEdit``): Cancel changes
nothing. The key is never shown again once typed.

The button *Check the data retrieved* asks the server with the two methods chosen in the form (the
models and the credit, ``core/config/provider_methods.py``) and shows what they give in one text,
so that the user sees whether the two choices work.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from wxclaude.core.config.provider_methods import (
    CreditMethod,
    ModelsMethod,
    credit_method,
    models_method,
)
from wxclaude.core.config.providers import KEY_STORED, Provider, ProviderStore
from wxclaude.core.errors import KeyVaultError, ModelListError, ProviderError
from wxclaude.i18n import _


@dataclass(slots=True)
class ProviderEdit:
    """A provider being edited, with what is to be done to its key when the form is accepted.

    ``had_key`` says that a key is saved for it, ``key`` is a new key typed in the form and
    ``remove_key`` that the saved key is to be removed. The key is not in the ``repr``.
    """

    provider: Provider
    had_key: bool = False
    key: str = field(default="", repr=False)
    remove_key: bool = False

    @property
    def has_key(self) -> bool:
        """Will the provider have a key once the form is accepted?"""
        return bool(self.key) or (self.had_key and not self.remove_key)


class ProviderFormView(Protocol):
    """What the presenter asks of the form."""

    def set_key_button(self, label: str, enabled: bool) -> None:
        """The label of the button for the key, and whether it can be used."""
        ...

    def set_check_button(self, enabled: bool) -> None:
        """Whether the data of the server can be asked for."""
        ...

    def ask_key(self, name: str) -> str | None:
        """Ask for the key of the provider ``name`` in a password field. None: cancelled."""
        ...

    def show_data(self, name: str, lines: list[str]) -> None:
        """Show what the server of the provider ``name`` gave, in a read-only text."""
        ...

    def start_check(
        self, task: Callable[[], list[str]], on_done: Callable[[list[str]], None]
    ) -> None:
        """Run ``task`` away from the window thread, then call ``on_done`` with its lines in the
        window thread. ``task`` never raises."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class ProviderFormPresenter:
    """The key button and the check button of the form of a provider."""

    def __init__(self, view: ProviderFormView, store: ProviderStore, edit: ProviderEdit) -> None:
        self._view = view
        self._store = store
        self.edit = edit
        self._needs_key = edit.provider.key_source == KEY_STORED
        self._models = models_method(edit.provider.models_method)
        self._credit = credit_method(edit.provider.credit_method)
        self._refresh()

    def key_source_changed(self, key_source: str) -> None:
        """The user chose where the key comes from: only ``stored`` takes a key from the form."""
        self._needs_key = key_source == KEY_STORED
        self._refresh()

    def methods_changed(self, models: str, credit: str) -> None:
        """The user chose the methods to ask the models and the credit (their identifiers)."""
        self._models = models_method(models)
        self._credit = credit_method(credit)
        self._refresh()

    def toggle_key(self, name: str) -> None:
        """Remove the key (it goes with OK), or ask for one (it is saved with OK)."""
        edit = self.edit
        if edit.has_key:
            edit.key = ""
            edit.remove_key = edit.had_key
        else:
            secret = self._view.ask_key(name)
            if secret is None:
                return
            if not secret.strip():
                self._view.show_error(_("The key is empty."))
                return
            edit.key = secret.strip()
            edit.remove_key = False
        self._refresh()

    def check_data(self, name: str, base_url: str) -> None:
        """Ask the server at ``base_url`` for the models and the credit, with the two methods
        chosen, away from the window thread, and show what they give. A failure of one is a line
        of the text, not an error."""
        try:
            key = self._key(name)
        except (ProviderError, KeyVaultError) as error:
            self._view.show_error(str(error))
            return
        models, credit = self._models, self._credit
        self._view.start_check(
            lambda: _data_lines(models, credit, name, base_url, key),
            lambda lines: self._view.show_data(name, lines),
        )

    # -- inside ---------------------------------------------------------------------------

    def _key(self, name: str) -> str:
        """The key to ask with: the one typed in the form, else the saved one; '' if none is
        needed. Raises ``ProviderError`` or ``KeyVaultError`` (with a message for the user)."""
        edit = self.edit
        if not self._needs_key:
            return ""
        if edit.key:
            return edit.key
        if edit.had_key and not edit.remove_key:
            return self._store.key(edit.provider.id)
        raise ProviderError(_("No key is saved for {name}.").format(name=name))

    def _refresh(self) -> None:
        has_key = self.edit.has_key
        label = _("Remove the ke&y") if has_key else _("Add a ke&y")
        self._view.set_key_button(label, self._needs_key)
        something_to_ask = self._models.available or self._credit.available
        self._view.set_check_button(something_to_ask and (not self._needs_key or has_key))


def _data_lines(
    models: ModelsMethod, credit: CreditMethod, name: str, base_url: str, key: str
) -> list[str]:
    """What the two methods give, as the lines of one text (run away from the window thread):
    the models, then a blank line and the credit. A method set to none is left out."""
    sections: list[list[str]] = []
    if models.available:
        try:
            names = models.fetch(base_url, key)
            sections.append([_("Models: {count}.").format(count=len(names)), *names])
        except ModelListError as error:
            sections.append([_("Models not available. {reason}").format(reason=error)])
    if credit.available:
        sections.append(credit.lines(name, base_url, key))
    lines: list[str] = []
    for section in sections:
        if lines:
            lines.append("")
        lines.extend(section)
    return lines

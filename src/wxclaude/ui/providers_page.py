"""The Providers page of the Preferences: the view of ``presenters/providers_presenter.py``.

What is done to the providers is saved at once (see the presenter). The way the key reaches the CLI
(*Masked* or *Shared*) is a setting like the others: OK stores it.
"""

from collections.abc import Callable

import wx

from wxclaude.core.config import key_transmission
from wxclaude.core.config.providers import ProviderStore
from wxclaude.core.config.settings import Settings
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _
from wxclaude.presenters.provider_form_presenter import ProviderEdit
from wxclaude.presenters.providers_presenter import ProvidersPresenter
from wxclaude.ui.fields import read_only_field
from wxclaude.ui.preferences_pages import PreferencesPage
from wxclaude.ui.provider_dialogs import ProviderDialog


class ProvidersPage(PreferencesPage):
    """The providers, one line each, the buttons to add, change and delete them, and the choice of
    the way the key reaches the CLI with its explanation. The controls are created in the order
    the Tab key visits them, each label right before its control so that screen readers pair
    them."""

    def __init__(self, parent: wx.Window, store: ProviderStore, settings: Settings) -> None:
        super().__init__(parent)
        self._store = store
        self.presenter: ProvidersPresenter  # made once the controls exist
        self._ready = False
        sizer = wx.BoxSizer(wx.VERTICAL)
        list_text = _("&Providers")
        sizer.Add(wx.StaticText(self, label=list_text), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self._list = wx.ListBox(self, name=accessible_name(list_text))
        self._list.SetMinSize(wx.Size(-1, self._list.GetCharHeight() * 8 + 12))
        self._list.Bind(wx.EVT_LISTBOX, self._on_select)
        sizer.Add(self._list, 1, wx.EXPAND | wx.ALL, 8)

        self._add = wx.Button(self, label=_("&Add..."))
        self._edit = wx.Button(self, label=_("&Edit..."))
        self._delete = wx.Button(self, label=_("&Delete..."))
        actions = (
            (self._add, lambda: self.presenter.add()),
            (self._edit, lambda: self.presenter.edit()),
            (self._delete, lambda: self.presenter.delete()),
        )
        row = wx.BoxSizer(wx.HORIZONTAL)
        for button, action in actions:
            button.Bind(wx.EVT_BUTTON, lambda _event, run=action: self._act(run))
            row.Add(button, 0, wx.RIGHT, 6)
        sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        transmission_text = _("API key &transmission")
        sizer.Add(wx.StaticText(self, label=transmission_text), 0, wx.LEFT | wx.RIGHT, 8)
        self._transmission = wx.Choice(
            self,
            choices=[_(key_transmission.LABELS[choice]) for choice in key_transmission.CHOICES],
            name=accessible_name(transmission_text),
        )
        self._transmission.SetSelection(key_transmission.CHOICES.index(settings.key_transmission))
        self._transmission.Bind(wx.EVT_CHOICE, lambda _event: self._show_explanation())
        sizer.Add(self._transmission, 0, wx.ALL, 8)
        explanation_text = _("E&xplanation")
        sizer.Add(wx.StaticText(self, label=explanation_text), 0, wx.LEFT | wx.RIGHT, 8)
        self._explanation = read_only_field(self, 6, name=accessible_name(explanation_text))
        sizer.Add(self._explanation, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.presenter = ProvidersPresenter(self, store)
        self._ready = True
        self._update_buttons()
        self._show_explanation()

    @property
    def transmission(self) -> str:
        """The way the key reaches the CLI that is chosen (``key_transmission``)."""
        return key_transmission.CHOICES[self._transmission.GetSelection()]

    def apply(self, settings: Settings) -> None:
        """Store the way the key reaches the CLI; the providers were saved when they changed."""
        settings.key_transmission = self.transmission

    def _show_explanation(self) -> None:
        self._explanation.ChangeValue(_(key_transmission.EXPLANATIONS[self.transmission]))

    # The buttons ------------------------------------------------------------------------------

    def _act(self, run: Callable[[], None]) -> None:
        run()
        self._update_buttons()

    def _on_select(self, _event: wx.CommandEvent) -> None:
        self.presenter.select(self._list.GetSelection())
        self._update_buttons()

    def _update_buttons(self) -> None:
        self._edit.Enable(self.presenter.can_edit())
        self._delete.Enable(self.presenter.can_edit())

    # The view of the presenter ---------------------------------------------------------------

    def show_providers(self, lines: list[str], selected: int) -> None:
        self._list.Set(lines)
        if selected >= 0:
            self._list.SetSelection(selected)
        if self._ready:
            self._update_buttons()

    def ask_provider(self, edit: ProviderEdit | None) -> ProviderEdit | None:
        with ProviderDialog(self, self._store, edit) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            result: ProviderEdit = dialog.result
        return result

    def confirm_delete(self, name: str) -> bool:
        message = _("Delete the provider {name} and its key?").format(name=name)
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        with wx.MessageDialog(self, message, _("Providers"), style) as dialog:
            return bool(dialog.ShowModal() == wx.ID_YES)

    def show_error(self, message: str) -> None:
        with wx.MessageDialog(self, message, _("Providers"), wx.OK | wx.ICON_ERROR) as dialog:
            dialog.ShowModal()

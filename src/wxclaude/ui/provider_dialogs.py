"""The dialogs of the Providers page: the form of a provider and the entry of its key."""

from collections.abc import Callable

import wx

from wxclaude.core.config.provider_methods import (
    CREDIT_METHODS,
    MODELS_METHODS,
    CreditMethod,
    ModelsMethod,
)
from wxclaude.core.config.providers import (
    KEY_NONE,
    KEY_SOURCES,
    KEY_STORED,
    NAME_MAX,
    Provider,
    ProviderStore,
)
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import N_, _
from wxclaude.presenters.provider_form_presenter import ProviderEdit, ProviderFormPresenter
from wxclaude.presenters.provider_variables_editor import ProviderVariablesEditor
from wxclaude.ui.fields import read_only_field
from wxclaude.ui.text_dialog import TextDialog
from wxclaude.ui.worker import run_in_background

_KEY_SOURCE_LABELS = {
    KEY_STORED: N_("Saved by WxClaude"),
    KEY_NONE: N_("No key (a local server)"),
}


class ProviderDialog(wx.Dialog):
    """The form of a provider: its fields, its key and the models its server offers.

    ``edit`` fills it (None: a new provider); ``result`` is what the form holds, with the id of the
    provider (empty for a new one, the presenter gives it) and what is to be done to its key. The
    list *Variable* holds the four models, from the smallest to the largest (an empty one takes the
    weakest model given), and the variables of the CLI the provider sets; the field *Value* edits
    the selected one (``ProviderVariablesEditor``). The buttons are driven by
    ``ProviderFormPresenter``.

    Each label is created right before its control so that screen readers pair them; the initial
    focus is on the name.
    """

    def __init__(self, parent: wx.Window, store: ProviderStore, edit: ProviderEdit | None) -> None:
        super().__init__(
            parent,
            title=_("Provider"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        edit = edit or ProviderEdit(Provider(id="", name=""))
        provider = edit.provider
        self._id = provider.id
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._name = self._text(sizer, _("&Name"), provider.name, NAME_MAX)
        self._address = self._text(sizer, _("&Address"), provider.base_url)
        key_text = _("&Key")
        sizer.Add(wx.StaticText(self, label=key_text), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self._key_source = wx.Choice(
            self,
            choices=[_(_KEY_SOURCE_LABELS[source]) for source in KEY_SOURCES],
            name=accessible_name(key_text),
        )
        self._key_source.SetSelection(KEY_SOURCES.index(provider.key_source))
        sizer.Add(self._key_source, 0, wx.EXPAND | wx.ALL, 8)
        self._key_button = wx.Button(self, label=_("Add a ke&y"))
        sizer.Add(self._key_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self._variables = ProviderVariablesEditor(provider)
        self._build_variables(sizer)
        self._effort = wx.CheckBox(self, label=_("Send the &effort"))
        self._effort.SetValue(provider.send_effort)
        sizer.Add(self._effort, 0, wx.ALL, 8)
        self._models_method = self._choice(
            sizer, _("Models re&trieval"), MODELS_METHODS, provider.models_method
        )
        self._credit_method = self._choice(
            sizer, _("Gauge retrie&val"), CREDIT_METHODS, provider.credit_method
        )
        self._check_button = wx.Button(self, label=_("&Check the data retrieved"))
        sizer.Add(self._check_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.SetMinSize(wx.Size(520, -1))
        self.presenter = ProviderFormPresenter(self, store, edit)
        self._key_source.Bind(
            wx.EVT_CHOICE,
            lambda _event: self.presenter.key_source_changed(
                KEY_SOURCES[self._key_source.GetSelection()]
            ),
        )
        self._key_button.Bind(
            wx.EVT_BUTTON, lambda _event: self.presenter.toggle_key(self._name_text)
        )
        for choice in (self._models_method, self._credit_method):
            choice.Bind(
                wx.EVT_CHOICE,
                lambda _event: self.presenter.methods_changed(self._models_id, self._credit_id),
            )
        self._check_button.Bind(
            wx.EVT_BUTTON,
            lambda _event: self.presenter.check_data(self._name_text, self._address_text),
        )
        self._name.SetFocus()

    def _text(self, sizer: wx.BoxSizer, label: str, value: str, max_length: int = 0) -> wx.TextCtrl:
        sizer.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        field = wx.TextCtrl(self, value=value, name=accessible_name(label))
        if max_length:
            field.SetMaxLength(max_length)
        sizer.Add(field, 0, wx.EXPAND | wx.ALL, 8)
        return field

    def _build_variables(self, sizer: wx.BoxSizer) -> None:
        """The list *Variable*, the field *Value* of the selected line and what it does. Each label
        is right before its control."""
        variable_text = _("Va&riable")
        sizer.Add(wx.StaticText(self, label=variable_text), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self._variable = wx.ListBox(
            self,
            choices=self._variables.lines,
            style=wx.LB_SINGLE,
            name=accessible_name(variable_text),
        )
        self._variable.SetMinSize(
            wx.Size(-1, self._variable.GetCharHeight() * len(self._variables) + 12)
        )
        self._variable.SetSelection(0)
        sizer.Add(self._variable, 0, wx.EXPAND | wx.ALL, 8)
        value_text = _("Val&ue")
        sizer.Add(wx.StaticText(self, label=value_text), 0, wx.LEFT | wx.RIGHT, 8)
        self._value = wx.TextCtrl(self, name=accessible_name(value_text))
        sizer.Add(self._value, 0, wx.EXPAND | wx.ALL, 8)
        explanation_text = _("E&xplanation")
        sizer.Add(wx.StaticText(self, label=explanation_text), 0, wx.LEFT | wx.RIGHT, 8)
        self._explanation = read_only_field(self, 3, name=accessible_name(explanation_text))
        sizer.Add(self._explanation, 0, wx.EXPAND | wx.ALL, 8)
        self._variable.Bind(wx.EVT_LISTBOX, lambda _event: self._show_variable())
        self._value.Bind(wx.EVT_TEXT, self._on_value)
        self._value.Bind(wx.EVT_KILL_FOCUS, self._on_value_left)
        self._show_variable()

    def _show_variable(self) -> None:
        """The value, the length limit and the explanation of the selected line."""
        index = self._variable.GetSelection()
        variables = self._variables
        self._value.SetMaxLength(variables.max_length(index))
        self._value.ChangeValue(variables.value(index))  # no EVT_TEXT: nothing was typed
        self._value.SetName(_("Value of {name}").format(name=variables.label(index)))
        self._explanation.ChangeValue(variables.explanation(index))

    def _on_value(self, _event: wx.CommandEvent) -> None:
        self._variables.set_value(self._variable.GetSelection(), str(self._value.GetValue()))

    def _on_value_left(self, event: wx.FocusEvent) -> None:
        """The line shows the new value once the field is left, not at each key (a screen reader
        would read the list again at each one)."""
        event.Skip()
        index = self._variable.GetSelection()
        self._variable.SetString(index, self._variables.line(index))
        self._variable.SetSelection(index)

    def _choice(
        self,
        sizer: wx.BoxSizer,
        label: str,
        methods: tuple[ModelsMethod, ...] | tuple[CreditMethod, ...],
        chosen: str,
    ) -> wx.Choice:
        """A list of methods; one that is not known shows as "no method", the first."""
        sizer.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.RIGHT, 8)
        choice = wx.Choice(
            self, choices=[_(method.label) for method in methods], name=accessible_name(label)
        )
        choice.SetSelection(next((i for i, m in enumerate(methods) if m.id == chosen), 0))
        sizer.Add(choice, 0, wx.ALL, 8)
        return choice

    @property
    def _models_id(self) -> str:
        return str(MODELS_METHODS[self._models_method.GetSelection()].id)

    @property
    def _credit_id(self) -> str:
        return str(CREDIT_METHODS[self._credit_method.GetSelection()].id)

    @property
    def _name_text(self) -> str:
        return str(self._name.GetValue()).strip()

    @property
    def _address_text(self) -> str:
        return str(self._address.GetValue()).strip()

    @property
    def result(self) -> ProviderEdit:
        """The provider the fields describe (not checked: ``Provider.problem`` does that), and
        what is to be done to its key."""
        key_source = KEY_SOURCES[self._key_source.GetSelection()]
        kept = self.presenter.edit
        return ProviderEdit(
            Provider(
                id=self._id,
                name=self._name_text,
                base_url=self._address_text,
                key_source=key_source,
                tiers=self._variables.tiers,
                send_effort=self._effort.GetValue(),
                models_method=self._models_id,
                credit_method=self._credit_id,
                env=self._variables.env,
            ),
            had_key=kept.had_key,
            key=kept.key if key_source == KEY_STORED else "",
            remove_key=kept.remove_key,
        )

    # The view of the presenter ---------------------------------------------------------------

    def set_key_button(self, label: str, enabled: bool) -> None:
        self._key_button.SetLabel(label)
        self._key_button.Enable(enabled)

    def set_check_button(self, enabled: bool) -> None:
        self._check_button.Enable(enabled)

    def ask_key(self, name: str) -> str | None:
        with KeyDialog(self, name) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            key: str = dialog.key
        return key

    def show_data(self, name: str, lines: list[str]) -> None:
        title = _("Data of {name}").format(name=name)
        with TextDialog(self, title, _("&Data"), lines) as dialog:
            dialog.ShowModal()

    def start_check(
        self, task: Callable[[], list[str]], on_done: Callable[[list[str]], None]
    ) -> None:
        self._check_button.Enable(False)  # one request at a time

        def finish(lines: list[str]) -> None:
            # The button is enabled again as the presenter decides from the key and the methods.
            self.presenter.key_source_changed(KEY_SOURCES[self._key_source.GetSelection()])
            on_done(lines)

        run_in_background(
            task,
            finish,
            lambda message: finish([message]),
            name="provider-check",
            alive=lambda: bool(self),  # False once the form was closed
        )

    def show_error(self, message: str) -> None:
        with wx.MessageDialog(self, message, _("Provider"), wx.OK | wx.ICON_ERROR) as dialog:
            dialog.ShowModal()


class KeyDialog(wx.Dialog):
    """The key of a provider, typed in a password field. The check box *Show the key* swaps it for
    a plain field holding the same text. The key is never shown again once saved."""

    def __init__(self, parent: wx.Window, name: str) -> None:
        super().__init__(parent, title=_("Key of {name}").format(name=name))
        key_text = _("&Key")
        label = wx.StaticText(self, label=key_text)
        self._hidden = wx.TextCtrl(self, style=wx.TE_PASSWORD, name=accessible_name(key_text))
        self._shown = wx.TextCtrl(self, name=accessible_name(key_text))
        self._shown.Hide()
        self._show = wx.CheckBox(self, label=_("&Show the key"))
        self._show.Bind(wx.EVT_CHECKBOX, lambda _event: self._swap())
        self._hidden.SetMinSize(wx.Size(self._hidden.GetCharWidth() * 50, -1))
        self._shown.SetMinSize(wx.Size(self._hidden.GetCharWidth() * 50, -1))
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.ALL, 8)
        sizer.Add(self._hidden, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._shown, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._show, 0, wx.ALL, 8)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self._hidden.SetFocus()

    def _swap(self) -> None:
        showing = self._show.GetValue()
        source, target = (self._hidden, self._shown) if showing else (self._shown, self._hidden)
        target.SetValue(source.GetValue())
        source.Hide()
        target.Show()
        target.SetInsertionPointEnd()
        target.SetFocus()
        self.Layout()

    @property
    def key(self) -> str:
        """The key as typed."""
        field = self._shown if self._show.GetValue() else self._hidden
        return str(field.GetValue())

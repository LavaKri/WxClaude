"""Controls to edit an agent (provider, model, effort, permission mode), shared by dialogs."""

import wx

from wxclaude.core.config.agent_choices import models_for, with_provider
from wxclaude.core.config.agents import EFFORTS, PERMISSION_MODES, Agent
from wxclaude.core.config.providers import CLAUDE, CLAUDE_ID, ProviderStore
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import N_, _

_EFFORT_LABELS = {
    "low": N_("Low"),
    "medium": N_("Medium"),
    "high": N_("High"),
    "xhigh": N_("Very high"),
    "max": N_("Maximum"),
}
_PERMISSION_LABELS = {
    "manual": N_("Ask before acting (manual)"),
    "acceptEdits": N_("Accept file edits (acceptEdits)"),
    "plan": N_("Plan only (plan)"),
    "auto": N_("Automatic (auto)"),
    "dontAsk": N_("Do not ask (dontAsk)"),
}
_PERMISSION_IMPLICATIONS = {
    "manual": N_("only reads run without asking."),
    "acceptEdits": N_(
        "reads, file edits and common file commands (mkdir, touch, mv, cp...) run without asking."
    ),
    "plan": N_(
        "reads, plus the commands approved by the classifier when auto mode is available; "
        "to explore before changing anything."
    ),
    "auto": N_("everything runs, with background safety checks by a classifier."),
    "dontAsk": N_(
        "reads in the working folders and pre-approved tools; anything that would ask is denied."
    ),
}


def permission_levels_lines() -> list[str]:
    """One line per permission level: its name, then what runs without asking."""
    return [
        _("{level}: {implication}").format(
            level=_(_PERMISSION_LABELS[mode]), implication=_(_PERMISSION_IMPLICATIONS[mode])
        )
        for mode in PERMISSION_MODES
    ]


class AgentPanel(wx.Panel):
    """Four labelled fields: the provider, then the model (the models of that provider), the effort
    and the permission mode.

    With ``unset_label`` each field starts with that entry, meaning "not specified" (the
    alternative agent takes it from the conversation). Without it every field holds a value: the
    agent of a conversation is always complete. A model is offered for the provider that is
    chosen; with no provider specified those of Claude are offered. Without ``providers`` Claude is
    the only provider.
    """

    def __init__(
        self,
        parent: wx.Window,
        agent: Agent,
        unset_label: str | None,
        *,
        mnemonics: bool = True,
        providers: ProviderStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = providers
        known = providers.providers() if providers is not None else [CLAUDE]
        self._provider_values = [provider.id for provider in known]
        self._provider_labels = [provider.name for provider in known]
        provider_text = _("Pro&vider") if mnemonics else _("Provider")
        model_text = _("&Model") if mnemonics else _("Model")
        effort_text = _("&Effort") if mnemonics else _("Effort")
        permission_text = _("&Permission mode") if mnemonics else _("Permission mode")

        # Each label is created right before its control so that screen readers pair them.
        grid = wx.FlexGridSizer(2, 6, 6)
        grid.AddGrowableCol(1)
        grid.Add(wx.StaticText(self, label=provider_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._provider = wx.Choice(self, name=accessible_name(provider_text))
        self._provider.Bind(wx.EVT_CHOICE, self._on_provider)
        grid.Add(self._provider, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label=model_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._model = wx.Choice(self, name=accessible_name(model_text))
        grid.Add(self._model, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label=effort_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._effort = wx.Choice(self, name=accessible_name(effort_text))
        grid.Add(self._effort, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label=permission_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._permission = wx.Choice(self, name=accessible_name(permission_text))
        grid.Add(self._permission, 1, wx.EXPAND)
        self._unset = unset_label is not None
        self._model_values: list[str] = []
        self.set_agent(agent, unset_label)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(grid, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(outer)

    def set_agent(self, agent: Agent, unset_label: str | None) -> None:
        """Show ``agent`` in the fields; ``unset_label`` is the entry meaning "not specified"."""
        self._unset = unset_label is not None
        self._provider.Clear()
        if unset_label is not None:
            self._provider.Append(unset_label)
        self._provider.Append(self._provider_labels)
        self._provider.SetSelection(self._index(tuple(self._provider_values), agent.provider))
        self._fill_models(agent.model, unset_label)
        for choice, values, labels, value in (
            (
                self._effort,
                EFFORTS,
                tuple(_(_EFFORT_LABELS[name]) for name in EFFORTS),
                agent.effort,
            ),
            (
                self._permission,
                PERMISSION_MODES,
                tuple(_(_PERMISSION_LABELS[name]) for name in PERMISSION_MODES),
                agent.permission_mode,
            ),
        ):
            choice.Clear()
            if unset_label is not None:
                choice.Append(unset_label)
            choice.Append(list(labels))
            choice.SetSelection(self._index(values, value))

    def _fill_models(self, model: str | None, unset_label: str | None) -> None:
        """The models of the provider that is chosen, with ``model`` selected if it is one."""
        provider = self._pick(self._provider, tuple(self._provider_values)) or CLAUDE_ID
        known = self._store.get(provider) if self._store is not None else CLAUDE
        self._model_values = models_for(known)
        self._model.Clear()
        if unset_label is not None:
            self._model.Append(unset_label)
        self._model.Append(self._model_values)
        self._model.SetSelection(self._index(tuple(self._model_values), model))

    def _on_provider(self, _event: wx.CommandEvent) -> None:
        """Another provider: its models are offered, and the model stays if it also has it."""
        if self._store is None:
            return
        moved = with_provider(
            self.agent,
            self._pick(self._provider, tuple(self._provider_values)) or CLAUDE_ID,
            self._store,
        )
        self._fill_models(moved.model, self._unset_label())

    def _unset_label(self) -> str | None:
        """The entry meaning "not specified", None when the panel has none."""
        return str(self._effort.GetString(0)) if self._unset else None

    def _index(self, values: tuple[str, ...], value: str | None) -> int:
        offset = 1 if self._unset else 0
        return values.index(value) + offset if value in values else 0

    def _pick(self, choice: wx.Choice, values: tuple[str, ...]) -> str | None:
        index = choice.GetSelection() - (1 if self._unset else 0)
        return values[index] if 0 <= index < len(values) else None

    def focus_first(self) -> None:
        """Give the focus to the first field."""
        self._provider.SetFocus()

    @property
    def agent(self) -> Agent:
        """The agent described by the current state of the fields."""
        return Agent(
            model=self._pick(self._model, tuple(self._model_values)),
            effort=self._pick(self._effort, EFFORTS),
            permission_mode=self._pick(self._permission, PERMISSION_MODES),
            provider=self._pick(self._provider, tuple(self._provider_values)),
        )

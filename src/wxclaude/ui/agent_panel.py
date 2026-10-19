"""Controls to edit an agent (model, effort, permission mode), shared by several dialogs."""

import wx

from wxclaude.core.agents import EFFORTS, MODELS, PERMISSION_MODES, Agent
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
    """Three labelled fields.

    With ``unset_label`` each field starts with that entry, meaning "not specified" (the
    alternative agent takes it from the conversation). Without it every field holds a value: the
    agent of a conversation is always complete.
    """

    def __init__(
        self, parent: wx.Window, agent: Agent, unset_label: str | None, *, mnemonics: bool = True
    ) -> None:
        super().__init__(parent)
        model_text = _("&Model") if mnemonics else _("Model")
        effort_text = _("&Effort") if mnemonics else _("Effort")
        permission_text = _("&Permission mode") if mnemonics else _("Permission mode")

        # Each label is created right before its control so that screen readers pair them.
        grid = wx.FlexGridSizer(2, 6, 6)
        grid.AddGrowableCol(1)
        grid.Add(wx.StaticText(self, label=model_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._model = wx.Choice(self, name=_("Model"))
        grid.Add(self._model, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label=effort_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._effort = wx.Choice(self, name=_("Effort"))
        grid.Add(self._effort, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label=permission_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._permission = wx.Choice(self, name=_("Permission mode"))
        grid.Add(self._permission, 1, wx.EXPAND)
        self._unset = unset_label is not None
        self.set_agent(agent, unset_label)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(grid, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(outer)

    def set_agent(self, agent: Agent, unset_label: str | None) -> None:
        """Show ``agent`` in the fields; ``unset_label`` is the entry meaning "not specified"."""
        self._unset = unset_label is not None
        for choice, values, labels, value in (
            (self._model, MODELS, MODELS, agent.model),
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

    def _index(self, values: tuple[str, ...], value: str | None) -> int:
        offset = 1 if self._unset else 0
        return values.index(value) + offset if value in values else 0

    def _pick(self, choice: wx.Choice, values: tuple[str, ...]) -> str | None:
        index = choice.GetSelection() - (1 if self._unset else 0)
        return values[index] if index >= 0 else None

    def focus_first(self) -> None:
        """Give the focus to the first field."""
        self._model.SetFocus()

    @property
    def agent(self) -> Agent:
        """The agent described by the current state of the fields."""
        return Agent(
            model=self._pick(self._model, MODELS),
            effort=self._pick(self._effort, EFFORTS),
            permission_mode=self._pick(self._permission, PERMISSION_MODES),
        )

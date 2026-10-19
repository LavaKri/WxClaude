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
    """Three labelled fields. A field left on its "unset" entry means "not specified"."""

    def __init__(
        self, parent: wx.Window, agent: Agent, unset_label: str, *, mnemonics: bool = True
    ) -> None:
        super().__init__(parent)
        model_text = _("&Model") if mnemonics else _("Model")
        effort_text = _("&Effort") if mnemonics else _("Effort")
        permission_text = _("&Permission mode") if mnemonics else _("Permission mode")

        # Each label is created right before its control so that screen readers pair them.
        grid = wx.FlexGridSizer(2, 6, 6)
        grid.AddGrowableCol(1)
        grid.Add(wx.StaticText(self, label=model_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._model = wx.Choice(self, choices=[unset_label, *MODELS], name=_("Model"))
        self._model.SetSelection(self._index(MODELS, agent.model))
        grid.Add(self._model, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label=effort_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._effort = wx.Choice(
            self,
            choices=[unset_label, *(_(_EFFORT_LABELS[value]) for value in EFFORTS)],
            name=_("Effort"),
        )
        self._effort.SetSelection(self._index(EFFORTS, agent.effort))
        grid.Add(self._effort, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label=permission_text), 0, wx.ALIGN_CENTER_VERTICAL)
        self._permission = wx.Choice(
            self,
            choices=[unset_label, *(_(_PERMISSION_LABELS[value]) for value in PERMISSION_MODES)],
            name=_("Permission mode"),
        )
        self._permission.SetSelection(self._index(PERMISSION_MODES, agent.permission_mode))
        grid.Add(self._permission, 1, wx.EXPAND)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(grid, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(outer)

    def set_agent(self, agent: Agent, unset_label: str) -> None:
        """Show ``agent`` in the fields; ``unset_label`` is the entry meaning "not specified"."""
        for choice, values, value in (
            (self._model, MODELS, agent.model),
            (self._effort, EFFORTS, agent.effort),
            (self._permission, PERMISSION_MODES, agent.permission_mode),
        ):
            choice.SetString(0, unset_label)
            choice.SetSelection(self._index(values, value))

    @staticmethod
    def _index(values: tuple[str, ...], value: str | None) -> int:
        return values.index(value) + 1 if value in values else 0

    @staticmethod
    def _pick(choice: wx.Choice, values: tuple[str, ...]) -> str | None:
        index = choice.GetSelection()
        return values[index - 1] if index > 0 else None

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

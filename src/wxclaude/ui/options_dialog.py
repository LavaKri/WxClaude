"""Options dialog: the agent of a new conversation and the alternative agent."""

import wx

from wxclaude.core.settings import Settings
from wxclaude.i18n import _
from wxclaude.ui.agent_panel import AgentPanel


class OptionsDialog(wx.Dialog):
    """Edit the options. ``apply`` copies the chosen values into the settings."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent, title=_("Options"))
        new_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Agent of a new conversation"))
        self._new = AgentPanel(
            new_box.GetStaticBox(),
            settings.default_agent,
            _("(not set: Claude Code setting)"),
            mnemonics=False,
        )
        new_box.Add(self._new, 1, wx.EXPAND)
        alternative_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Alternative agent"))
        self._alternative = AgentPanel(
            alternative_box.GetStaticBox(),
            settings.alternative_agent,
            _("(same as the conversation)"),
            mnemonics=False,
        )
        alternative_box.Add(self._alternative, 1, wx.EXPAND)
        cache_warning = wx.StaticText(
            alternative_box.GetStaticBox(),
            label=_(
                "Changing the model loses the cache of the conversation: "
                "the next message is slower and costs more."
            ),
        )
        cache_warning.Wrap(420)
        alternative_box.Add(cache_warning, 0, wx.ALL, 6)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(new_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(alternative_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizerAndFit(sizer)
        self._new.focus_first()

    def apply(self, settings: Settings) -> None:
        """Store the values chosen in the dialog into ``settings``."""
        settings.default_agent = self._new.agent
        settings.alternative_agent = self._alternative.agent

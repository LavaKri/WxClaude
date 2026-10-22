"""Dialog to choose the agent of the current conversation."""

import wx

from wxclaude.core.config.agents import Agent
from wxclaude.i18n import _
from wxclaude.ui.agent_panel import AgentPanel


class AgentDialog(wx.Dialog):
    """Edit one agent. The initial focus is on the model field."""

    def __init__(self, parent: wx.Window, agent: Agent) -> None:
        super().__init__(parent, title=_("Modify the agent"))
        self._panel = AgentPanel(self, agent, None)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._panel, 1, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizerAndFit(sizer)
        self._panel.focus_first()

    @property
    def agent(self) -> Agent:
        """The agent chosen by the user."""
        return self._panel.agent

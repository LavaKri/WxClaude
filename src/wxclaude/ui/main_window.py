"""Main window: conversation view, prompt field and status bar."""

import wx

from wxclaude import __version__
from wxclaude.core.settings import Settings
from wxclaude.i18n import _


class MainWindow(wx.Frame):
    """Top-level window. Skeleton: read-only conversation view above a prompt field."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(None, title=_("WxClaude"), size=wx.Size(900, 650))
        self._settings = settings
        panel = wx.Panel(self)

        conversation_label = wx.StaticText(panel, label=_("&Conversation"))
        self._conversation = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name=_("Conversation"),
        )
        prompt_label = wx.StaticText(panel, label=_("&Message"))
        self._prompt = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER, name=_("Message")
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(conversation_label, 0, wx.LEFT | wx.TOP, 6)
        sizer.Add(self._conversation, 3, wx.EXPAND | wx.ALL, 6)
        sizer.Add(prompt_label, 0, wx.LEFT, 6)
        sizer.Add(self._prompt, 1, wx.EXPAND | wx.ALL, 6)
        panel.SetSizer(sizer)

        self._build_menu_bar()
        self.CreateStatusBar()
        self.SetStatusText(_("Ready"))
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._prompt.SetFocus)

    def _build_menu_bar(self) -> None:
        file_menu = wx.Menu()
        quit_item = file_menu.Append(wx.ID_EXIT, _("&Quit\tCtrl+Q"))
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, _("&About"))
        menu_bar = wx.MenuBar()
        menu_bar.Append(file_menu, _("&File"))
        menu_bar.Append(help_menu, _("&Help"))
        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, lambda _event: self.Close(), quit_item)
        self.Bind(wx.EVT_MENU, self._on_about, about_item)

    def _on_about(self, _event: wx.CommandEvent) -> None:
        message = _("WxClaude {version}").format(version=__version__)
        wx.MessageBox(message, _("About"), wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._settings.save()
        event.Skip()

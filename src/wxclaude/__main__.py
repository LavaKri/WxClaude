"""Application entry point: ``python -m wxclaude``."""

import wx

from wxclaude.core.settings import Settings, default_settings_path
from wxclaude.i18n import _, install
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.single_instance import acquire_single_instance
from wxclaude.ui.wx_locale import init_wx_locale


def main() -> int:
    """Create the wx application and run the event loop."""
    settings = Settings.load(default_settings_path())
    install(settings.language)
    app = wx.App()
    instance = acquire_single_instance()  # must stay referenced while the app runs
    if instance is None:
        wx.MessageBox(_("WxClaude is already running."), _("WxClaude"), wx.OK | wx.ICON_INFORMATION)
        return 1
    wx_locale = init_wx_locale(settings.language)  # must stay referenced while the app runs
    window = MainWindow(settings)
    window.Show()
    app.SetTopWindow(window)
    app.MainLoop()
    del wx_locale, instance
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

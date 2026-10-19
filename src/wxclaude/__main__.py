"""Application entry point: ``python -m wxclaude``."""

import wx

from wxclaude.core.settings import Settings, default_settings_path
from wxclaude.i18n import install
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.wx_locale import init_wx_locale


def main() -> int:
    """Create the wx application and run the event loop."""
    settings = Settings.load(default_settings_path())
    install(settings.language)
    app = wx.App()
    wx_locale = init_wx_locale(settings.language)  # must stay referenced while the app runs
    window = MainWindow(settings)
    window.Show()
    app.SetTopWindow(window)
    app.MainLoop()
    del wx_locale
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Application entry point: ``python -m wxclaude``."""

import wx

from wxclaude.core.errors import JsonStoreError
from wxclaude.core.settings import Settings, default_settings_path
from wxclaude.i18n import _, install
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.single_instance import (
    acquire_single_instance,
    instance_file,
    publish_window,
    raise_running_window,
)
from wxclaude.ui.wx_locale import init_wx_locale


def main() -> int:
    """Create the wx application and run the event loop."""
    settings_file = default_settings_path()
    settings = Settings.load(settings_file)
    install(settings.language)
    app = wx.App()
    instance = acquire_single_instance()  # must stay referenced while the app runs
    if instance is None:
        if not raise_running_window(instance_file(settings_file)):
            wx.MessageBox(
                _("WxClaude is already running."), _("WxClaude"), wx.OK | wx.ICON_INFORMATION
            )
        return 1
    wx_locale = init_wx_locale(settings.language)  # must stay referenced while the app runs
    window = MainWindow(settings)
    window.Show()
    try:
        publish_window(instance_file(settings_file), window.GetHandle())
    except JsonStoreError as error:
        wx.MessageBox(
            _(
                "A second launch will not be able to bring this window to the front.\n{error}"
            ).format(error=error),
            _("Warning"),
            wx.OK | wx.ICON_WARNING,
            window,
        )
    app.SetTopWindow(window)
    app.MainLoop()
    del wx_locale, instance
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

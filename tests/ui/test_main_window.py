import pytest
import wx

from wxclaude.core.settings import Settings
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def test_main_window_can_be_created() -> None:
    app = wx.App()
    window = MainWindow(Settings.load(None))
    assert window.GetTitle() == "WxClaude"
    window.Destroy()
    del app

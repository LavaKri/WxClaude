import pytest
import wx

from wxclaude.ui.single_instance import acquire_single_instance

pytestmark = pytest.mark.ui


def test_a_second_instance_is_refused(wx_app: wx.App) -> None:
    first = acquire_single_instance("WxClaude-test-single-instance")
    assert first is not None
    assert acquire_single_instance("WxClaude-test-single-instance") is None
    del first
    again = acquire_single_instance("WxClaude-test-single-instance")
    assert again is not None

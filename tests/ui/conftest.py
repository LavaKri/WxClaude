import pytest
import wx


@pytest.fixture(scope="session")
def wx_app():
    """One wx application for the whole session: wx cannot cleanly recreate it per test."""
    return wx.App()

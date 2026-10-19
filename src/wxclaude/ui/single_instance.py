"""Only one WxClaude per user: two instances would overwrite each other's files."""

import wx


def acquire_single_instance(name: str | None = None) -> wx.SingleInstanceChecker | None:
    """The checker to keep referenced while the application runs, None if another one runs.

    Needs the wx application to exist. ``name`` is only given by the tests.
    """
    checker = wx.SingleInstanceChecker(name or f"WxClaude-{wx.GetUserId()}")
    return None if checker.IsAnotherRunning() else checker

import os
import sys
from pathlib import Path

import pytest
import wx

from wxclaude.core.config.jsonstore import write_json
from wxclaude.ui.single_instance import (
    acquire_single_instance,
    instance_file,
    publish_window,
    raise_running_window,
)

pytestmark = pytest.mark.ui


def test_a_second_instance_is_refused(wx_app: wx.App) -> None:
    first = acquire_single_instance("WxClaude-test-single-instance")
    assert first is not None
    assert acquire_single_instance("WxClaude-test-single-instance") is None
    del first
    again = acquire_single_instance("WxClaude-test-single-instance")
    assert again is not None


def test_the_file_is_next_to_the_settings(tmp_path: Path) -> None:
    assert instance_file(tmp_path / "settings.json") == tmp_path / "instance.json"


@pytest.mark.skipif(sys.platform != "win32", reason="the window is raised with the Win32 API")
def test_the_published_window_is_brought_to_the_front(wx_app: wx.App, tmp_path: Path) -> None:
    frame = wx.Frame(None)
    frame.Show()
    try:
        path = tmp_path / "instance.json"
        publish_window(path, frame.GetHandle())
        frame.Iconize(True)
        wx.SafeYield()
        assert raise_running_window(path)
        wx.SafeYield()
        assert not frame.IsIconized()
    finally:
        frame.Destroy()
        wx.SafeYield()


@pytest.mark.skipif(sys.platform != "win32", reason="the window is raised with the Win32 API")
def test_a_stale_or_foreign_handle_is_refused(wx_app: wx.App, tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    assert not raise_running_window(path)  # no file
    write_json(path, {"pid": os.getpid(), "handle": 0})
    assert not raise_running_window(path)  # not a window
    frame = wx.Frame(None)
    try:
        write_json(path, {"pid": os.getpid() + 1, "handle": frame.GetHandle()})
        assert not raise_running_window(path)  # the window belongs to another process
        write_json(path, {"pid": "x", "handle": "y"})
        assert not raise_running_window(path)
    finally:
        frame.Destroy()
        wx.SafeYield()

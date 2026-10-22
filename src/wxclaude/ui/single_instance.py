"""Only one WxClaude per user: two instances would overwrite each other's files.

A second launch brings the window of the first one to the front. For that the first instance
writes the handle of its window (and its process id) in ``instance.json``, next to
``settings.json``; the second one checks that the handle still belongs to that process before
using it, so a file left by a crash is harmless.
"""

import ctypes
import os
import sys
from pathlib import Path

import wx

from wxclaude.core.config.jsonstore import read_json, write_json

INSTANCE_FILE_NAME = "instance.json"
_SW_RESTORE = 9


def acquire_single_instance(name: str | None = None) -> wx.SingleInstanceChecker | None:
    """The checker to keep referenced while the application runs, None if another one runs.

    Needs the wx application to exist. ``name`` is only given by the tests.
    """
    checker = wx.SingleInstanceChecker(name or f"WxClaude-{wx.GetUserId()}")
    return None if checker.IsAnotherRunning() else checker


def instance_file(settings_file: Path) -> Path:
    """The file where the running instance publishes its window, next to ``settings_file``."""
    return settings_file.with_name(INSTANCE_FILE_NAME)


def publish_window(path: Path, handle: int) -> None:
    """Tell a later launch where the window of this instance is (``JsonStoreError`` on failure)."""
    write_json(path, {"pid": os.getpid(), "handle": handle})


def raise_running_window(path: Path) -> bool:
    """Bring the window published in ``path`` to the front; False if there is no such window."""
    if sys.platform != "win32":
        return False
    data = read_json(path).data
    if data is None:
        return False
    pid, handle = data.get("pid"), data.get("handle")
    if not isinstance(pid, int) or not isinstance(handle, int):
        return False
    user32 = ctypes.windll.user32
    if not user32.IsWindow(handle):
        return False
    owner = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
    if owner.value != pid:
        return False  # the handle was reused by another program
    if user32.IsIconic(handle):
        user32.ShowWindow(handle, _SW_RESTORE)
    user32.BringWindowToTop(handle)
    user32.SetForegroundWindow(handle)
    return True

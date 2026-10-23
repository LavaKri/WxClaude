"""What the application asks of the desktop: the clipboard, the browser, the file explorer and the
Recycle Bin.

Each function returns False when the desktop refuses, so that the caller can tell the user.
"""

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

import wx

# SHFileOperationW (shellapi.h): delete, allowing undo (the Recycle Bin), without any window of its
# own (no confirmation, no progress, no error dialog: the application tells the user itself).
_FO_DELETE = 0x3
_FOF_SILENT = 0x4
_FOF_NOCONFIRMATION = 0x10
_FOF_ALLOWUNDO = 0x40
_FOF_NOERRORUI = 0x400


class _FileOperation(ctypes.Structure):
    """SHFILEOPSTRUCTW."""

    _fields_ = (
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", ctypes.c_void_p),
        ("pTo", ctypes.c_void_p),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    )


def set_clipboard(text: str) -> bool:
    """Put ``text`` on the clipboard; False if the clipboard cannot be opened."""
    if not wx.TheClipboard.Open():
        return False
    try:
        return bool(wx.TheClipboard.SetData(wx.TextDataObject(text)))
    finally:
        wx.TheClipboard.Close()


def launch_url(url: str) -> bool:
    """Open ``url`` with the default browser (or mail program); False if refused."""
    return bool(wx.LaunchDefaultBrowser(url))


def launch_file(path: Path) -> bool:
    """Open ``path`` with the application the desktop associates with it (the browser for HTML)."""
    return bool(wx.LaunchDefaultApplication(str(path)))


def launch_folder(folder: Path) -> bool:
    """Open ``folder`` with the default application (the file explorer); False if refused."""
    return bool(wx.LaunchDefaultApplication(str(folder)))


def move_to_recycle_bin(paths: list[Path]) -> bool:
    """Move the files and folders ``paths`` to the Recycle Bin of Windows; False if one of them
    could not be moved, or on another system (there is no Recycle Bin to go to)."""
    if sys.platform != "win32":
        return False
    if not paths:
        return True
    # A list of absolute paths, each ended by a null character, the whole ended by another one.
    names = ctypes.create_unicode_buffer("".join(f"{path.resolve()}\0" for path in paths) + "\0")
    operation = _FileOperation(
        hwnd=None,
        wFunc=_FO_DELETE,
        pFrom=ctypes.addressof(names),
        pTo=None,
        fFlags=_FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI,
    )
    failed = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    return (
        failed == 0
        and not operation.fAnyOperationsAborted
        and not any(path.exists() for path in paths)
    )

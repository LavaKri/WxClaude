"""What the application asks of the desktop: the clipboard, the browser, the file explorer.

Each function returns False when the desktop refuses, so that the caller can tell the user.
"""

from pathlib import Path

import wx


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

"""Work done away from the window thread: the result comes back to the window thread."""

import threading
from collections.abc import Callable

import wx

from wxclaude.core.errors import WxClaudeError


def run_in_background[T](
    work: Callable[[], T],
    on_done: Callable[[T], None],
    on_error: Callable[[str], None],
    *,
    name: str,
    alive: Callable[[], bool] = lambda: True,
) -> None:
    """Run ``work`` in a thread. Back in the window thread, call ``on_done`` with its result, or
    ``on_error`` with the message of the ``WxClaudeError`` it raised. Nothing is called once
    ``alive()`` is False (the window that asked is gone). Only the window thread touches wx."""

    def run() -> None:
        try:
            result = work()
        except WxClaudeError as error:
            wx.CallAfter(_deliver, alive, on_error, str(error))
        else:
            wx.CallAfter(_deliver, alive, on_done, result)

    threading.Thread(target=run, name=name, daemon=True).start()


def _deliver[T](alive: Callable[[], bool], callback: Callable[[T], None], value: T) -> None:
    if alive():
        callback(value)

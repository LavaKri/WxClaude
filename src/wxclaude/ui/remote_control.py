"""The remote control of the window (option ``--remote``, ``docs/remote.md``): the named pipe, and
the hand-over of its requests to the interface thread."""

import wx

from wxclaude.core.remote.endpoint import RemoteEndpoint
from wxclaude.core.remote.pipe_server import PipeServer
from wxclaude.presenters.remote_presenter import RemoteLinks, RemotePresenter


class RemoteControl:
    """Listens on the pipe ``name``; what a request does is told by ``links``."""

    def __init__(self, name: str, links: RemoteLinks) -> None:
        endpoint = RemoteEndpoint(RemotePresenter(links).execute, wx.CallAfter)
        self._server = PipeServer(name, endpoint.handle)

    def start(self) -> None:
        """Create the pipe (``RemoteError`` if that is not possible)."""
        self._server.start()

    def stop(self) -> None:
        self._server.stop()

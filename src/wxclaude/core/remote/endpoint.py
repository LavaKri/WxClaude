"""From the thread of the pipe to the interface thread and back.

``RemoteEndpoint.handle`` is the handler of the ``PipeServer``: it checks the request in the thread
of the pipe, has ``execute`` run on the interface thread (``run_in_ui`` is ``wx.CallAfter``, given
by the window so that this module never imports wx) and waits for its answer. Only ``version`` is
answered at once, in the thread of the pipe, so that it works when the window is blocked. A request
whose turn never comes is answered with ``timeout`` and is not run when the interface finally gets
to it, so that a client that tries again does not do the same thing twice.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from wxclaude.core.errors import RemoteRequestError
from wxclaude.core.remote.protocol import (
    Command,
    ErrorCode,
    RemoteRequest,
    encode,
    failure,
    parse_request,
    version_response,
)

DEFAULT_WAIT_SECONDS = 5.0


@dataclass(slots=True)
class _Call:
    """One request waiting for the interface thread."""

    done: threading.Event = field(default_factory=threading.Event)
    response: dict[str, object] | None = None
    cancelled: bool = False


class RemoteEndpoint:
    """Turns the bytes of a request into the bytes of its response."""

    def __init__(
        self,
        execute: Callable[[RemoteRequest], dict[str, object]],
        run_in_ui: Callable[[Callable[[], None]], None],
        wait_seconds: float = DEFAULT_WAIT_SECONDS,
    ) -> None:
        self._execute = execute
        self._run_in_ui = run_in_ui
        self._wait_seconds = wait_seconds

    def handle(self, raw: bytes) -> bytes:
        try:
            request = parse_request(raw)
        except RemoteRequestError as error:
            return encode(failure(error.code))
        if request.command is Command.VERSION:
            return encode(version_response())  # needs nothing of the window
        return encode(self._on_interface_thread(request))

    def _on_interface_thread(self, request: RemoteRequest) -> dict[str, object]:
        call = _Call()

        def run() -> None:
            if call.cancelled:
                return
            try:
                call.response = self._execute(request)
            finally:
                call.done.set()  # also when execute failed: the client is not left waiting

        self._run_in_ui(run)
        if not call.done.wait(self._wait_seconds):
            call.cancelled = True
            return failure(ErrorCode.TIMEOUT)
        return call.response if call.response is not None else failure(ErrorCode.INTERNAL)

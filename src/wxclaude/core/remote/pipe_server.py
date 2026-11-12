"""The named pipe of the remote control: one request and one response per connection.

The pipe has a fixed name per user (``pipe_name``) so that any program can find it. Nothing is
asked of the client but a write of the request in one piece and a read of the response: no
handshake and no key, which is what lets a script in any language use it (``docs/remote.md``).
The rights of the pipe are the default ones of Windows: another user of the computer cannot write
to it. The thread that listens only accepts the clients, each is served in a thread of its own (at
most ``_MAX_CLIENTS`` at once) so that the pipe is free again at once for the next one and a client
that says nothing blocks nobody. No thread touches the interface: ``handler`` does what is needed.
"""

import threading
from collections.abc import Callable
from contextlib import closing
from multiprocessing.connection import Client, Listener
from typing import Protocol

from wxclaude.core.diagnostics import logger
from wxclaude.core.errors import RemoteError
from wxclaude.core.remote.protocol import MAX_REQUEST_BYTES

_READ_TIMEOUT_SECONDS = 2.0  # a client that connects and says nothing is dropped after this
_STOP_TIMEOUT_SECONDS = 2.0
_MAX_CLIENTS = 8  # served at the same time; the others wait to be accepted
_FAMILY = "AF_PIPE"
_PIPE_PREFIX = "\\\\.\\pipe\\"


class _Client(Protocol):
    """The connection of one client (``PipeConnection`` of ``multiprocessing``)."""

    def poll(self, timeout: float | None = ...) -> bool: ...

    def recv_bytes(self, maxlength: int | None = ...) -> bytes: ...

    def send_bytes(self, buf: bytes) -> None: ...

    def close(self) -> None: ...


def pipe_name(user: str) -> str:
    """The address of the pipe of ``user``: ``\\\\.\\pipe\\WxClaude-<user>``."""
    safe = "".join("_" if character in "\\/" else character for character in user)
    return f"{_PIPE_PREFIX}WxClaude-{safe}"


class PipeServer:
    """Listens on a named pipe in a thread and answers each request with ``handler(request)``."""

    def __init__(self, name: str, handler: Callable[[bytes], bytes]) -> None:
        self._name = name
        self._handler = handler
        self._listener: Listener | None = None
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()
        self._places = threading.BoundedSemaphore(_MAX_CLIENTS)

    @property
    def name(self) -> str:
        return self._name

    def start(self) -> None:
        """Create the pipe and start listening (``RemoteError`` if that is not possible: no pipes
        on this system, or the name is already taken)."""
        try:
            self._listener = Listener(self._name, family=_FAMILY)
        except (OSError, ValueError) as error:
            raise RemoteError(f"The pipe {self._name} cannot be created: {error}") from error
        self._thread = threading.Thread(target=self._serve, name="remote-pipe", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop listening and free the name of the pipe (nothing happens if it never started)."""
        listener, thread = self._listener, self._thread
        if listener is None or thread is None:
            return
        self._stopped.set()
        try:
            Client(self._name, family=_FAMILY).close()  # wakes the thread that waits for a client
        except OSError:
            logger.debug("The remote pipe was not reachable to stop it", exc_info=True)
        thread.join(_STOP_TIMEOUT_SECONDS)
        listener.close()
        self._listener = None
        self._thread = None

    def _serve(self) -> None:
        listener = self._listener
        if listener is None:
            return
        while not self._stopped.is_set():
            self._places.acquire()
            try:
                connection = listener.accept()
            except OSError, EOFError:
                self._places.release()
                if not self._stopped.is_set():
                    logger.error("The remote pipe stopped listening", exc_info=True)
                return
            if self._stopped.is_set():
                connection.close()
                self._places.release()
                return
            threading.Thread(
                target=self._serve_client, args=(connection,), name="remote-client", daemon=True
            ).start()

    def _serve_client(self, connection: _Client) -> None:
        try:
            self._answer(connection)
        finally:
            self._places.release()

    def _answer(self, connection: _Client) -> None:
        """Read the request of a client and write the response; a client that goes away, says
        nothing or sends too much is dropped."""
        with closing(connection):
            try:
                if not connection.poll(_READ_TIMEOUT_SECONDS):
                    return
                request = connection.recv_bytes(MAX_REQUEST_BYTES)
                connection.send_bytes(self._handler(request))
            except OSError, EOFError:
                logger.debug("A client of the remote pipe went away", exc_info=True)

"""The named pipe with a real pipe, as a script that is not Python would use it: the request
written in one piece, then the response read."""

import errno
import os
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from typing import BinaryIO

import pytest

from wxclaude.core.errors import RemoteError
from wxclaude.core.remote import pipe_server
from wxclaude.core.remote.pipe_server import PipeServer, pipe_name
from wxclaude.core.remote.protocol import MAX_REQUEST_BYTES

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(sys.platform != "win32", reason="named pipes of Windows"),
]


def _unique_name() -> str:
    return pipe_name(f"test-{os.getpid()}-{uuid.uuid4().hex[:8]}")


def _connect(name: str) -> BinaryIO:
    """Open the pipe; a client that finds it busy (clients that arrive at the same moment take
    all its instances) waits and tries again, as ``NamedPipeClientStream.Connect(timeout)`` does:
    Python's ``open`` does not wait by itself."""
    deadline = time.monotonic() + 5
    while True:
        try:
            return open(name, "r+b", buffering=0)  # noqa: PTH123 (a pipe is not a path to a file)
        except OSError as error:
            if error.errno != errno.EINVAL or time.monotonic() > deadline:
                raise  # not "busy": the C library of Python reports ERROR_PIPE_BUSY as EINVAL
            time.sleep(0.005)


def _ask(name: str, request: bytes) -> bytes:
    with _connect(name) as pipe:
        pipe.write(request)
        return pipe.read(4096)


@pytest.fixture
def server() -> Iterator[PipeServer]:
    server = PipeServer(_unique_name(), lambda request: b"echo:" + request)
    server.start()
    yield server
    server.stop()


def test_the_name_is_fixed_per_user_and_safe() -> None:
    assert pipe_name("Alice") == "\\\\.\\pipe\\WxClaude-Alice"
    assert pipe_name("a\\b/c") == "\\\\.\\pipe\\WxClaude-a_b_c"


def test_a_client_gets_the_response_to_its_request(server: PipeServer) -> None:
    assert _ask(server.name, b'{"command": "last"}') == b'echo:{"command": "last"}'


def test_clients_are_answered_one_after_the_other(server: PipeServer) -> None:
    answers = [_ask(server.name, f"request {number}".encode()) for number in range(20)]
    assert answers == [f"echo:request {number}".encode() for number in range(20)]


def _ask_all_at_once(name: str, count: int) -> dict[str, bytes]:
    answers: dict[str, bytes] = {}

    def ask(text: str) -> None:
        answers[text] = _ask(name, text.encode())

    threads = [threading.Thread(target=ask, args=(f"client {n}",)) for n in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)
    return answers


def test_the_requests_of_clients_at_once_are_all_answered(server: PipeServer) -> None:
    answers = _ask_all_at_once(server.name, 5)
    assert answers == {f"client {n}": f"echo:client {n}".encode() for n in range(5)}


def test_more_clients_than_places_are_all_answered_in_turn() -> None:
    def slow(request: bytes) -> bytes:
        time.sleep(0.05)
        return b"echo:" + request

    server = PipeServer(_unique_name(), slow)
    server.start()
    try:
        count = 3 * pipe_server._MAX_CLIENTS
        answers = _ask_all_at_once(server.name, count)
        assert answers == {f"client {n}": f"echo:client {n}".encode() for n in range(count)}
    finally:
        server.stop()


def test_a_client_that_says_nothing_does_not_block_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipe_server, "_READ_TIMEOUT_SECONDS", 5)
    server = PipeServer(_unique_name(), lambda request: b"echo:" + request)
    server.start()
    try:
        with _connect(server.name):  # connected, never writes
            started = time.monotonic()
            assert _ask(server.name, b"hello") == b"echo:hello"
            assert time.monotonic() - started < 2  # not after the time-out of the silent one
    finally:
        server.stop()


def test_a_request_that_is_too_large_is_dropped_and_the_pipe_goes_on(server: PipeServer) -> None:
    with pytest.raises(OSError):  # noqa: PT011 (the exact error depends on the pipe)
        _ask(server.name, b"x" * (MAX_REQUEST_BYTES + 1000))
    assert _ask(server.name, b"hello") == b"echo:hello"


def test_a_second_server_cannot_take_the_name() -> None:
    name = _unique_name()
    first = PipeServer(name, lambda request: request)
    first.start()
    try:
        with pytest.raises(RemoteError):
            PipeServer(name, lambda request: request).start()
    finally:
        first.stop()


def test_stopping_frees_the_name() -> None:
    name = _unique_name()
    first = PipeServer(name, lambda request: b"first")
    first.start()
    first.stop()
    second = PipeServer(name, lambda request: b"second")
    second.start()
    try:
        assert _ask(name, b"?") == b"second"
    finally:
        second.stop()


def test_stopping_a_server_that_never_started_is_harmless() -> None:
    PipeServer(_unique_name(), lambda request: request).stop()

"""The local relay that holds the key of a provider, tried against a fake provider."""

import http.client
import http.server
import json
import socket
import struct
import threading
import time
from collections.abc import Iterator

import pytest

from wxclaude.core.config.providers import Provider
from wxclaude.core.security.key_relay import KeyRelay, RelayAccess, _Handler, _Server

pytestmark = pytest.mark.unit

KEY = "sk-real-key"


class FakeProvider:
    """A provider that records what it receives and answers as ``mode`` says."""

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.mode = "json"
        self.release = threading.Event()
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                owner.requests.append(
                    {
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                        "body": self.rfile.read(length),
                    }
                )
                getattr(self, f"_{owner.mode}")()

            do_GET = do_POST  # noqa: N815

            def _json(self) -> None:
                body = b'{"ok": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _error(self) -> None:
                body = b'{"error": "bad key"}'
                self.send_response(401)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _stream(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for index, wait in ((1, False), (2, True)):
                    if wait:
                        owner.release.wait(5)
                    piece = f"event: part{index}\n\n".encode()
                    self.wfile.write(f"{len(piece):X}\r\n".encode() + piece + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()
        self.port = self.server.server_address[1]

    def provider(self, identifier: str = "deepseek") -> Provider:
        return Provider(
            id=identifier,
            name="Fake",
            base_url=f"http://127.0.0.1:{self.port}/anthropic",
            tiers=["m"],
        )

    def close(self) -> None:
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def upstream() -> Iterator[FakeProvider]:
    fake = FakeProvider()
    yield fake
    fake.close()


@pytest.fixture
def relay() -> Iterator[KeyRelay]:
    relay = KeyRelay(check_seconds=3600)
    yield relay
    relay.stop()


def call(
    access: RelayAccess,
    path: str = "/v1/messages",
    body: bytes = b'{"model": "m"}',
    headers: dict[str, str] | None = None,
    *,
    method: str = "POST",
    chunked: bool = False,
) -> tuple[int, bytes]:
    host, port = access.base_url.removeprefix("http://").split(":")
    connection = http.client.HTTPConnection(host, int(port), timeout=10)
    try:
        sent = {"Authorization": f"Bearer {access.token}", **(headers or {})}
        connection.request(method, path, body=body, headers=sent, encode_chunked=chunked)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


# -- what is forwarded ------------------------------------------------------------------------


def test_the_request_goes_to_the_provider_with_the_real_key_and_not_the_token(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    access = relay.access(upstream.provider(), KEY)
    status, body = call(access, headers={"x-api-key": access.token, "anthropic-version": "2023"})
    assert (status, json.loads(body)) == (200, {"ok": True})
    (seen,) = upstream.requests
    assert seen["path"] == "/anthropic/v1/messages"  # the address of the provider, then the path
    assert seen["body"] == b'{"model": "m"}'
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == f"Bearer {KEY}"
    assert "x-api-key" not in headers
    assert headers["anthropic-version"] == "2023"  # the other headers are kept
    assert access.token not in json.dumps(headers)


def test_a_big_body_and_a_chunked_body_arrive_whole(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    access = relay.access(upstream.provider(), KEY)
    big = b"x" * 3_000_000
    call(access, body=big)
    assert upstream.requests[0]["body"] == big
    # A chunked request is read by the relay and forwarded with its length.
    call(access, body=b"in pieces", chunked=True)
    assert upstream.requests[1]["body"] == b"in pieces"


def test_the_answer_of_the_provider_comes_back_as_it_is_even_an_error(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    upstream.mode = "error"
    status, body = call(relay.access(upstream.provider(), KEY))
    assert (status, body) == (401, b'{"error": "bad key"}')


def test_a_stream_arrives_piece_by_piece_and_not_when_it_ends(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    upstream.mode = "stream"
    access = relay.access(upstream.provider(), KEY)
    host, port = access.base_url.removeprefix("http://").split(":")
    connection = http.client.HTTPConnection(host, int(port), timeout=10)
    try:
        connection.request(
            "POST", "/v1/messages", body=b"{}", headers={"Authorization": f"Bearer {access.token}"}
        )
        response = connection.getresponse()
        assert response.getheader("Content-Type") == "text/event-stream"
        assert response.read1(100) == b"event: part1\n\n"  # before the provider finished
        assert not upstream.release.is_set()
        upstream.release.set()
        assert response.read() == b"event: part2\n\n"
    finally:
        connection.close()


def test_a_provider_that_cannot_be_reached_is_a_502_in_the_shape_of_the_api(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    provider = upstream.provider()
    upstream.close()
    status, body = call(relay.access(provider, KEY))
    assert status == 502
    error = json.loads(body)
    assert error["type"] == "error"
    assert KEY not in body.decode()


# -- who may ask ------------------------------------------------------------------------------


@pytest.mark.parametrize("header", ["Bearer wrong", "", "Basic abc"])
def test_a_request_without_the_token_is_refused_and_never_reaches_the_provider(
    relay: KeyRelay, upstream: FakeProvider, header: str
) -> None:
    access = relay.access(upstream.provider(), KEY)
    host, port = access.base_url.removeprefix("http://").split(":")
    connection = http.client.HTTPConnection(host, int(port), timeout=10)
    try:
        headers = {"Authorization": header} if header else {}
        connection.request("POST", "/v1/messages", body=b"{}", headers=headers)
        response = connection.getresponse()
        assert response.status == 401
        assert json.loads(response.read())["error"]["type"] == "authentication_error"
    finally:
        connection.close()
    assert upstream.requests == []


def test_the_token_can_be_shown_as_an_api_key(relay: KeyRelay, upstream: FakeProvider) -> None:
    access = relay.access(upstream.provider(), KEY)
    status, _body = call(access, headers={"Authorization": "", "x-api-key": access.token})
    assert status == 200


def test_only_the_paths_of_the_api_are_relayed(relay: KeyRelay, upstream: FakeProvider) -> None:
    access = relay.access(upstream.provider(), KEY)
    for path in ("/", "/admin", "/v1", "/other/v1/messages"):
        assert call(access, path)[0] == 404
    assert upstream.requests == []
    assert call(access, "/v1/messages/count_tokens")[0] == 200


def test_the_relay_listens_on_the_loopback_address_only(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    access = relay.access(upstream.provider(), KEY)
    assert access.base_url.startswith("http://127.0.0.1:")
    server = relay._server
    assert server is not None
    assert server.server_address[0] == "127.0.0.1"


def test_a_connection_the_cli_drops_is_not_reported_as_an_error(
    relay: KeyRelay, upstream: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end: the reset really reaches the server as a connection error. The rule itself is
    tested without the wait just below (``test_a_connection_error_is_not_written...``): this one
    can only wait a little and look for what did not happen."""
    access = relay.access(upstream.provider(), KEY)
    host, port = access.base_url.removeprefix("http://").split(":")
    for _ in range(3):
        connection = socket.create_connection((host, int(port)), timeout=5)
        # A close with a reset, as the CLI does when it ends: the server was waiting for a request.
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        connection.close()
    time.sleep(0.3)
    assert call(access)[0] == 200  # and the relay goes on
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Exception occurred" not in captured.err


def _raise(error: Exception) -> None:
    raise error


def _handle_error(error: Exception) -> None:
    """Give ``error`` to the server as if a connection had raised it (it is read from the
    exception being handled)."""
    server = _Server(("127.0.0.1", 0), _Handler, bind_and_activate=False)
    try:
        try:
            _raise(error)
        except type(error):
            server.handle_error(None, ("127.0.0.1", 1))
    finally:
        server.server_close()


@pytest.mark.parametrize(
    "error", [ConnectionResetError(), ConnectionAbortedError(), BrokenPipeError()]
)
def test_a_connection_error_is_not_written_to_the_error_output(
    error: ConnectionError, capsys: pytest.CaptureFixture[str]
) -> None:
    _handle_error(error)
    assert capsys.readouterr().err == ""


def test_another_error_is_still_written_to_the_error_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The check of the test above: the silence is the rule, not a broken way of looking."""
    _handle_error(ValueError("a real bug"))
    assert "ValueError: a real bug" in capsys.readouterr().err


def test_the_nagle_algorithm_is_off_so_that_an_answer_is_not_delayed() -> None:
    # Not measurable here (the client of the tests acknowledges at once): with the real CLI the
    # delay was about 0.2 s for each request (a message with a tool took 3.6 s instead of 3.1 s).
    assert _Handler.disable_nagle_algorithm


# -- the tokens and the life of the relay -----------------------------------------------------


def test_a_provider_keeps_its_token_while_the_relay_runs_and_has_its_own(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    first = relay.access(upstream.provider("one"), KEY)
    again = relay.access(upstream.provider("one"), KEY)
    other = relay.access(upstream.provider("two"), "sk-other")
    assert again == first
    assert other.token != first.token
    assert other.base_url == first.base_url  # one relay for all the providers
    call(other)
    assert upstream.requests[-1]["headers"]["authorization"] == "Bearer sk-other"  # type: ignore[index]


def test_a_changed_key_is_used_with_the_same_token(relay: KeyRelay, upstream: FakeProvider) -> None:
    first = relay.access(upstream.provider(), KEY)
    second = relay.access(upstream.provider(), "sk-new")
    assert second.token == first.token
    call(second)
    assert upstream.requests[-1]["headers"]["authorization"] == "Bearer sk-new"  # type: ignore[index]


def test_stopping_forgets_the_tokens_and_the_next_use_starts_again(
    relay: KeyRelay, upstream: FakeProvider
) -> None:
    first = relay.access(upstream.provider(), KEY)
    assert relay.running
    relay.stop()
    assert not relay.running
    relay.stop()  # nothing happens
    second = relay.access(upstream.provider(), KEY)
    assert relay.running
    assert second.token != first.token
    assert call(RelayAccess(second.base_url, first.token))[0] == 401  # the old token is gone


def test_the_relay_stops_after_a_time_without_requests() -> None:
    now = [0.0]
    relay = KeyRelay(idle_seconds=600, check_seconds=3600, clock=lambda: now[0])
    try:
        relay.access(FakeProviderless(), KEY)
        now[0] = 599
        assert not relay.expire_if_idle()
        assert relay.running
        now[0] = 601
        assert relay.expire_if_idle()
        assert not relay.running
        assert not relay.expire_if_idle()  # already stopped
    finally:
        relay.stop()


def test_a_request_under_way_keeps_the_relay_alive() -> None:
    now = [0.0]
    relay = KeyRelay(idle_seconds=600, check_seconds=3600, clock=lambda: now[0])
    try:
        relay.access(FakeProviderless(), KEY)
        relay.begin()
        now[0] = 5000
        assert not relay.expire_if_idle()  # a long answer is not cut
        relay.end()  # its end counts as a use
        assert not relay.expire_if_idle()
        now[0] = 5000 + 601
        assert relay.expire_if_idle()
    finally:
        relay.stop()


def test_using_the_relay_again_postpones_its_stop() -> None:
    now = [0.0]
    relay = KeyRelay(idle_seconds=600, check_seconds=3600, clock=lambda: now[0])
    try:
        provider = FakeProviderless()
        relay.access(provider, KEY)
        now[0] = 500
        relay.access(provider, KEY)
        now[0] = 1000
        assert not relay.expire_if_idle()
        now[0] = 1101
        assert relay.expire_if_idle()
    finally:
        relay.stop()


def test_the_token_is_not_in_the_repr() -> None:
    access = RelayAccess("http://127.0.0.1:1", "secret-token")
    assert "secret-token" not in repr(access)


def FakeProviderless() -> Provider:  # noqa: N802 (a provider no request is sent to)
    return Provider(id="p", name="P", base_url="http://127.0.0.1:9/anthropic", tiers=["m"])

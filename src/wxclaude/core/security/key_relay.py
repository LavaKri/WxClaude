"""A local relay that holds the key of a provider so that the CLI never gets it (``providers.md``).

The CLI is given the address of the relay (``http://127.0.0.1:<port>``) and a throw-away token as
its key. For each request the relay checks the token, puts the real key in place of it and forwards
the request to the provider, copying the answer back as it arrives (the answers are streamed). The
real key therefore is neither in the environment of the CLI nor in what its commands can read.

The relay listens on the loopback address only, on a port the system chooses, and starts when the
first request for a provider is prepared. It stops after a time without any request, and forgets
its tokens then: the next message starts it again with new ones. There is one token per provider
for as long as the relay runs. Nothing of the traffic is logged or kept.
"""

import http.client
import http.server
import json
import secrets
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from wxclaude.core.config.providers import Provider

LOOPBACK = "127.0.0.1"
IDLE_SECONDS = 600.0  # a relay without any request for that long stops
CHECK_SECONDS = 30.0  # how often the idle time is looked at
UPSTREAM_TIMEOUT = 600.0  # the wait for the provider: a model can think for a long time
ALLOWED_PREFIX = "/v1/"  # the only paths relayed (the API of the provider)
MAX_BODY = 64 * 1024 * 1024
_CHUNK = 64 * 1024
# Headers that belong to one connection and are not passed on (RFC 9110), and the credentials,
# which are replaced.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
_CREDENTIALS = frozenset({"authorization", "x-api-key"})
_NO_BODY_STATUS = frozenset({204, 304})


@dataclass(frozen=True, slots=True)
class RelayAccess:
    """What the CLI is given instead of the provider: an address and a token. Not the key."""

    base_url: str
    token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class _Route:
    upstream: str  # the address of the API of the provider (``Provider.base_url``)
    key: str = field(repr=False)


class KeyRelay:
    """The relay. ``access`` prepares a provider (and starts the relay); ``stop`` ends it."""

    def __init__(
        self,
        idle_seconds: float = IDLE_SECONDS,
        *,
        check_seconds: float = CHECK_SECONDS,
        timeout: float = UPSTREAM_TIMEOUT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._idle_seconds = idle_seconds
        self._check_seconds = check_seconds
        self._timeout = timeout
        self._clock = clock
        self._lock = threading.RLock()
        self._server: _Server | None = None
        self._stopped = threading.Event()
        self._routes: dict[str, _Route] = {}  # by token
        self._tokens: dict[str, str] = {}  # the token of each provider (by id)
        self._last_used = clock()
        self._active = 0  # the requests being relayed

    @property
    def running(self) -> bool:
        """Is the relay listening?"""
        with self._lock:
            return self._server is not None

    def access(self, provider: Provider, key: str) -> RelayAccess:
        """The address and the token to give the CLI for ``provider``, whose key is ``key``.

        Starts the relay if it is not running. The token of a provider stays the same as long as
        the relay runs; the key and the address of the provider are kept up to date.
        """
        with self._lock:
            server = self._server or self._start()
            token = self._tokens.get(provider.id)
            if token is None:
                token = secrets.token_urlsafe(32)
                self._tokens[provider.id] = token
            self._routes[token] = _Route(provider.base_url.strip().rstrip("/"), key)
            self._last_used = self._clock()
            port = server.server_address[1]
        return RelayAccess(f"http://{LOOPBACK}:{port}", token)

    def stop(self) -> None:
        """Stop the relay and forget the tokens (nothing happens if it is not running)."""
        with self._lock:
            self._stop_locked()

    def expire_if_idle(self) -> bool:
        """Stop the relay if nothing was asked of it for the idle time; True if it stopped."""
        with self._lock:
            if (
                self._server is None
                or self._active
                or self._clock() - self._last_used < self._idle_seconds
            ):
                return False
            self._stop_locked()
            return True

    # -- what the handler asks ------------------------------------------------------------

    def route_for(self, presented: list[str]) -> _Route | None:
        """The route of the token among the ``presented`` ones (compared in constant time)."""
        with self._lock:
            found: _Route | None = None
            for token, route in self._routes.items():
                for candidate in presented:
                    if secrets.compare_digest(candidate.encode(), token.encode()):
                        found = route
            return found

    def begin(self) -> None:
        """A request starts: the relay is in use."""
        with self._lock:
            self._active += 1
            self._last_used = self._clock()

    def end(self) -> None:
        """A request is over."""
        with self._lock:
            self._active -= 1
            self._last_used = self._clock()

    @property
    def timeout(self) -> float:
        """How long to wait for the provider."""
        return self._timeout

    # -- inside ---------------------------------------------------------------------------

    def _start(self) -> _Server:
        server = _Server((LOOPBACK, 0), _Handler)
        server.daemon_threads = True
        server.relay = self  # type: ignore[attr-defined]
        self._server = server
        self._stopped.clear()
        for target, name, options in (
            (server.serve_forever, "key-relay", {"poll_interval": 0.2}),
            (self._watch, "key-relay-idle", {}),
        ):
            threading.Thread(target=target, kwargs=options, daemon=True, name=name).start()
        return server

    def _watch(self) -> None:
        while not self._stopped.wait(self._check_seconds):
            self.expire_if_idle()

    def _stop_locked(self) -> None:
        server, self._server = self._server, None
        self._routes.clear()
        self._tokens.clear()
        self._stopped.set()
        if server is None:
            return
        server.shutdown()  # waits for the loop that serves to end; the requests under way go on
        server.server_close()


class _Server(http.server.ThreadingHTTPServer):
    """The server. The CLI closes its connections without a word, which is not an error."""

    def handle_error(self, request: object, client_address: object) -> None:
        if not isinstance(sys.exception(), ConnectionError):
            super().handle_error(request, client_address)  # type: ignore[arg-type]


class _Handler(http.server.BaseHTTPRequestHandler):
    """One request of the CLI: check the token, forward to the provider, stream the answer back."""

    protocol_version = "HTTP/1.1"
    # The headers and the first piece of an answer are two small sends in a row: with the Nagle
    # algorithm the second waits for the acknowledgement of the first, which Windows delays (about
    # 0.2 s more for each request of the CLI, measured).
    disable_nagle_algorithm = True

    def log_message(self, format: str, *args: object) -> None:
        """Nothing of the traffic is logged."""

    def do_GET(self) -> None:
        self._relay()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_GET  # noqa: N815

    @property
    def _owner(self) -> KeyRelay:
        owner: KeyRelay = self.server.relay  # type: ignore[attr-defined]
        return owner

    def _relay(self) -> None:
        owner = self._owner
        owner.begin()
        try:
            self._forward(owner)
        except BrokenPipeError, ConnectionResetError, TimeoutError:
            self.close_connection = True  # the CLI went away: nothing more to say
        finally:
            owner.end()

    def _forward(self, owner: KeyRelay) -> None:
        route = owner.route_for(self._presented_tokens())
        if route is None:
            self._fail(401, "authentication_error", "The token is not valid.")
            return
        if not self.path.startswith(ALLOWED_PREFIX):
            self._fail(404, "not_found_error", "This path is not relayed.")
            return
        body = self._read_body()
        if body is None:
            return
        upstream = urlsplit(route.upstream)
        secure = upstream.scheme == "https"
        connection = (
            http.client.HTTPSConnection(upstream.netloc, timeout=owner.timeout)
            if secure
            else http.client.HTTPConnection(upstream.netloc, timeout=owner.timeout)
        )
        try:
            connection.request(
                self.command,
                upstream.path.rstrip("/") + self.path,
                body=body or None,
                headers=self._upstream_headers(route),
            )
            response = connection.getresponse()
        except (OSError, http.client.HTTPException) as error:
            connection.close()
            self._fail(502, "api_error", f"The provider cannot be reached: {error}")
            return
        try:
            self._copy(response)
        finally:
            connection.close()

    def _presented_tokens(self) -> list[str]:
        """The tokens the CLI shows: as a bearer token or as an API key."""
        tokens = []
        bearer = self.headers.get("Authorization", "")
        if bearer.lower().startswith("bearer "):
            tokens.append(bearer[7:].strip())
        api_key = self.headers.get("x-api-key", "").strip()
        if api_key:
            tokens.append(api_key)
        return tokens

    def _upstream_headers(self, route: _Route) -> dict[str, str]:
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in _HOP_BY_HOP | _CREDENTIALS | {"host", "content-length"}
        }
        headers["Authorization"] = f"Bearer {route.key}"
        headers["Connection"] = "close"
        return headers

    def _read_body(self) -> bytes | None:
        """The body of the request; None (the answer is sent) if it cannot be read or is too big."""
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            return self._read_chunked()
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self._fail(413 if length > MAX_BODY else 400, "invalid_request_error", "Bad length.")
            return None
        return self.rfile.read(length) if length else b""

    def _read_chunked(self) -> bytes | None:
        parts: list[bytes] = []
        total = 0
        while True:
            try:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
            except ValueError:
                self._fail(400, "invalid_request_error", "Bad chunk.")
                return None
            if size == 0:
                while self.rfile.readline().strip():  # the trailers, if any
                    pass
                return b"".join(parts)
            total += size
            if total > MAX_BODY:
                self._fail(413, "invalid_request_error", "The request is too big.")
                return None
            parts.append(self.rfile.read(size))
            self.rfile.readline()  # the end of the chunk

    def _copy(self, response: http.client.HTTPResponse) -> None:
        """Send the answer of the provider to the CLI, piece by piece as it arrives."""
        has_body = self.command != "HEAD" and response.status not in _NO_BODY_STATUS
        length = response.getheader("Content-Length")
        chunked = has_body and length is None
        self.send_response_only(response.status, response.reason)
        for name, value in response.getheaders():
            if name.lower() not in _HOP_BY_HOP:
                self.send_header(name, value)
        if chunked:
            self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        if not has_body:
            return
        while piece := response.read1(_CHUNK):
            self.wfile.write(f"{len(piece):X}\r\n".encode() + piece + b"\r\n" if chunked else piece)
            self.wfile.flush()
        if chunked:
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()

    def _fail(self, status: int, kind: str, message: str) -> None:
        """Answer with an error in the shape of the API (the key is never in it)."""
        body = json.dumps({"type": "error", "error": {"type": kind, "message": message}}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

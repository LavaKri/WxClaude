"""The permission channel of the HTTP hook (see ``docs/claude-cli.md``, "Permission channels").

The CLI is given a ``PermissionRequest`` hook of type ``http`` (``--settings``) that points at a
small server on ``127.0.0.1``, one per message. When it needs a permission it POSTs the request and
waits for the response. The thread of the server that holds the request hands it to the interface
as a ``PermissionRequest`` event and waits; ``answer`` (called by the interface thread) only stores
the decision and wakes that thread, which writes the response. The interface thread never does
input or output here. This module never imports ``wx``.

The URL holds a random token: only the CLI that was given it can ask. Anything else gets a 404.
"""

import json
import secrets
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from wxclaude.core.claude.events import PermissionExpired, PermissionRequest, RunEvent
from wxclaude.core.claude.process_input import ProcessInput
from wxclaude.core.claude.stream import suggested_rule
from wxclaude.core.errors import RunnerError

MAX_BODY_BYTES = 8 * 1024 * 1024  # a request holds the whole input of the tool (a file to write)
_SOCKET_TIMEOUT_SECONDS = 30  # reading a request; waiting for the user is not a socket operation
_EXPIRY_MARGIN_SECONDS = 5  # the CLI gives up at the timeout; the thread waits a little longer
_POLL_INTERVAL_SECONDS = 0.1


@dataclass(slots=True)
class _Pending:
    """A request that waits for the answer of the user."""

    request: PermissionRequest
    answered: threading.Event = field(default_factory=threading.Event)
    decision: dict[str, object] | None = None


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _reply(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, object]) -> None:
    data = json.dumps(payload).encode("utf-8")
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    except OSError:
        return  # the CLI closed the connection (its waiting time ran out): nobody to tell


def _read_body(handler: BaseHTTPRequestHandler) -> dict[str, object] | None:
    """The JSON object of the request; else the error is already answered and this is None."""
    try:
        length = int(handler.headers.get("Content-Length", ""))
    except ValueError:
        _reply(handler, 400, {})
        return None
    if length < 0 or length > MAX_BODY_BYTES:
        _reply(handler, 413, {})
        return None
    try:
        body = json.loads(handler.rfile.read(length))
    except ValueError:
        _reply(handler, 400, {})
        return None
    if not isinstance(body, dict):
        _reply(handler, 400, {})
        return None
    return body


def _without_unchanged_input(
    decision: dict[str, object], request: PermissionRequest
) -> dict[str, object]:
    """The decision of the hook: ``updatedInput`` is only sent when it differs from the request."""
    if decision.get("updatedInput") != request.input:
        return decision
    return {key: value for key, value in decision.items() if key != "updatedInput"}


class HookChannel:
    """Receives the permission questions of the CLI through its hook, one server per message."""

    def __init__(self, on_event: Callable[[RunEvent], None], timeout_seconds: int) -> None:
        self._on_event = on_event
        self._timeout_seconds = timeout_seconds
        self._token = secrets.token_urlsafe(16)
        self._lock = threading.RLock()  # on_event may answer at once, from the same thread
        self._closed = False
        self._pending: dict[str, _Pending] = {}
        try:
            self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        except OSError as error:
            raise RunnerError(f"The permission server cannot start: {error}") from error
        threading.Thread(
            target=self._server.serve_forever, args=(_POLL_INTERVAL_SECONDS,), daemon=True
        ).start()

    def arguments(self) -> list[str]:
        url = f"http://127.0.0.1:{self._server.server_address[1]}/hook/{self._token}"
        hook = {"type": "http", "url": url, "timeout": self._timeout_seconds}
        settings = {"hooks": {"PermissionRequest": [{"hooks": [hook]}]}}
        return ["--settings", json.dumps(settings)]

    def bind(self, process_input: ProcessInput) -> None:
        """The hook does not use the standard input."""

    def answer(self, request_id: str, decision: dict[str, object]) -> None:
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None or pending.answered.is_set():
                raise RunnerError("Claude is no longer waiting for this answer.")
            pending.decision = _without_unchanged_input(decision, pending.request)
            pending.answered.set()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for pending in self._pending.values():
                pending.answered.set()  # wakes the threads: the CLI is gone
        self._server.shutdown()
        self._server.server_close()

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        channel = self

        class Handler(BaseHTTPRequestHandler):
            timeout = _SOCKET_TIMEOUT_SECONDS

            def do_POST(self) -> None:  # the name is imposed by BaseHTTPRequestHandler
                channel._handle(self)

            def log_message(self, format: str, *args: Any) -> None:
                return  # nothing is written to the console

        return Handler

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        """One POST of the CLI: ask the interface, wait for the answer, write the response."""
        if handler.path != f"/hook/{self._token}":
            _reply(handler, 404, {})
            return
        body = _read_body(handler)
        if body is None:
            return
        pending = self._ask(body)
        if pending is None:
            _reply(handler, 503, {})
            return
        answered = pending.answered.wait(self._timeout_seconds + _EXPIRY_MARGIN_SECONDS)
        with self._lock:
            self._pending.pop(pending.request.request_id, None)
            if not answered and not self._closed:
                self._on_event(
                    PermissionExpired(pending.request.request_id, pending.request.tool_name)
                )
        if pending.decision is None:
            _reply(handler, 200, {})  # no decision: the CLI denies the tool by itself
            return
        _reply(
            handler,
            200,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": pending.decision,
                }
            },
        )

    def _ask(self, body: dict[str, object]) -> _Pending | None:
        """Register the request and hand it to the interface; None if the channel is closed."""
        tool_input = body.get("tool_input")
        request = PermissionRequest(
            request_id=uuid.uuid4().hex,
            tool_name=_text(body.get("tool_name")),
            tool_use_id="",  # not sent by the hook
            input=tool_input if isinstance(tool_input, dict) else {},
            description="",
            blocked_path="",
            suggested_rule=suggested_rule(body.get("permission_suggestions")),
        )
        with self._lock:
            if self._closed:
                return None
            pending = _Pending(request)
            self._pending[request.request_id] = pending
            self._on_event(request)
        return pending

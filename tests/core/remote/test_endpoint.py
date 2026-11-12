import json
import threading
from collections.abc import Callable

import pytest

from wxclaude.core.remote.endpoint import RemoteEndpoint
from wxclaude.core.remote.protocol import PROTOCOL_VERSION, Command, RemoteRequest, success

pytestmark = pytest.mark.unit


def _answer(endpoint: RemoteEndpoint, body: str) -> dict[str, object]:
    return json.loads(endpoint.handle(body.encode("utf-8")))  # type: ignore[no-any-return]


def _at_once(task: Callable[[], None]) -> None:
    task()


def test_a_request_is_run_by_the_interface_and_its_response_comes_back() -> None:
    seen: list[RemoteRequest] = []

    def execute(request: RemoteRequest) -> dict[str, object]:
        seen.append(request)
        return success(value=1)

    endpoint = RemoteEndpoint(execute, _at_once)
    assert _answer(endpoint, '{"command": "interrupt"}') == {"ok": True, "value": 1}
    assert [request.command for request in seen] == [Command.INTERRUPT]


def test_the_version_is_answered_without_the_interface() -> None:
    queue: list[Callable[[], None]] = []  # the interface never gets to run anything

    def execute(request: RemoteRequest) -> dict[str, object]:
        raise AssertionError("version does not need the window")

    endpoint = RemoteEndpoint(execute, queue.append, wait_seconds=0.05)
    response = _answer(endpoint, '{"command": "version"}')
    assert response["ok"] is True
    assert (response["application"], response["protocol"]) == ("WxClaude", PROTOCOL_VERSION)
    assert queue == []


def test_a_refused_request_never_reaches_the_interface() -> None:
    called: list[str] = []

    def execute(request: RemoteRequest) -> dict[str, object]:
        called.append("execute")
        return success()

    def run_in_ui(task: Callable[[], None]) -> None:
        called.append("interface")
        task()

    endpoint = RemoteEndpoint(execute, run_in_ui)
    assert _answer(endpoint, '{"command": "quit"}') == {"ok": False, "error": "unknown_command"}
    assert called == []


def test_a_request_the_interface_never_runs_times_out_and_is_not_run_later() -> None:
    queue: list[Callable[[], None]] = []
    executed: list[str] = []

    def execute(request: RemoteRequest) -> dict[str, object]:
        executed.append("run")
        return success()

    endpoint = RemoteEndpoint(execute, queue.append, wait_seconds=0.05)
    assert _answer(endpoint, '{"command": "interrupt"}') == {"ok": False, "error": "timeout"}
    queue[0]()  # the interface gets to it too late
    assert executed == []


def test_a_failing_command_is_answered_without_waiting_for_the_timeout() -> None:
    def execute(request: RemoteRequest) -> dict[str, object]:
        raise ZeroDivisionError

    def run(task: Callable[[], None]) -> None:
        with pytest.raises(ZeroDivisionError):  # the error goes on to the log of the application
            task()

    endpoint = RemoteEndpoint(execute, run, wait_seconds=30)
    assert _answer(endpoint, '{"command": "interrupt"}') == {
        "ok": False,
        "error": "internal_error",
    }


def test_the_command_runs_on_the_thread_the_interface_gives() -> None:
    interface_thread: list[threading.Thread] = []

    def execute(request: RemoteRequest) -> dict[str, object]:
        interface_thread.append(threading.current_thread())
        return success()

    def run(task: Callable[[], None]) -> None:
        worker = threading.Thread(target=task, name="interface")
        worker.start()
        worker.join()

    endpoint = RemoteEndpoint(execute, run)
    assert _answer(endpoint, '{"command": "interrupt"}') == {"ok": True}
    assert interface_thread[0].name == "interface"

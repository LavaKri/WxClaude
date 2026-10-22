import io
import json

import pytest

from wxclaude.core.errors import RunnerError
from wxclaude.core.hook_channel import HookChannel
from wxclaude.core.permission_channel import HOOK, STDIO, StdioChannel, make_channel
from wxclaude.core.process_input import ProcessInput

pytestmark = pytest.mark.unit


def test_the_stdio_channel_opens_with_the_stdio_permission_tool() -> None:
    assert StdioChannel().arguments() == ["--permission-prompt-tool", "stdio"]


def test_an_answer_is_a_control_response_line_on_the_input() -> None:
    stream = io.StringIO()
    channel = StdioChannel()
    channel.bind(ProcessInput(stream))
    channel.answer("req-7", {"behavior": "deny", "message": "no"})
    assert json.loads(stream.getvalue()) == {
        "type": "control_response",
        "response": {
            "subtype": "success",
            "request_id": "req-7",
            "response": {"behavior": "deny", "message": "no"},
        },
    }


def test_answering_before_the_process_runs_or_after_it_ended_is_an_error() -> None:
    channel = StdioChannel()
    with pytest.raises(RunnerError):
        channel.answer("r", {"behavior": "allow"})
    channel.bind(ProcessInput(io.StringIO()))
    channel.close()
    with pytest.raises(RunnerError):
        channel.answer("r", {"behavior": "allow"})


def test_answering_on_a_closed_input_is_an_error() -> None:
    process_input = ProcessInput(io.StringIO())
    channel = StdioChannel()
    channel.bind(process_input)
    process_input.close()
    process_input.close()  # harmless the second time
    with pytest.raises(RunnerError):
        channel.answer("r", {"behavior": "allow"})


def test_a_channel_is_made_from_its_name() -> None:
    assert isinstance(make_channel(STDIO, lambda _event: None, 600), StdioChannel)
    hook = make_channel(HOOK, lambda _event: None, 600)
    try:
        assert isinstance(hook, HookChannel)
    finally:
        hook.close()
    with pytest.raises(RunnerError):
        make_channel("carrier-pigeon", lambda _event: None, 600)

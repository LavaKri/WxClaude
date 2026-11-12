"""The standard input of the ``claude`` process: lines written once, closed once."""

import io
import json

import pytest

from wxclaude.core.claude.process_input import ProcessInput
from wxclaude.core.errors import RunnerError

pytestmark = pytest.mark.unit


class BrokenStream(io.StringIO):
    """A pipe whose process is gone: every operation on it fails."""

    def __init__(self, *, fails_on_write: bool = False) -> None:
        super().__init__()
        self._fails_on_write = fails_on_write

    def write(self, text: str, /) -> int:
        if self._fails_on_write:
            raise BrokenPipeError("the pipe is broken")
        return super().write(text)

    def flush(self) -> None:
        raise BrokenPipeError("the pipe is broken")

    def close(self) -> None:
        if not self.closed:
            super().close()
            raise BrokenPipeError("the pipe is broken")

    def __del__(self) -> None:
        """Do not close again when the object is collected: that call would fail as well."""


def test_an_entry_is_written_as_one_json_line() -> None:
    stream = io.StringIO()
    ProcessInput(stream).write({"type": "user", "text": "é"})
    ProcessInput(stream).write({"type": "second"})
    first, second = stream.getvalue().splitlines()
    assert json.loads(first) == {"type": "user", "text": "é"}
    assert json.loads(second) == {"type": "second"}


def test_without_a_stream_nothing_can_be_written() -> None:
    with pytest.raises(RunnerError, match="not waiting"):
        ProcessInput(None).write({"type": "user"})


def test_nothing_can_be_written_once_it_is_closed() -> None:
    stream = io.StringIO()
    process_input = ProcessInput(stream)
    process_input.close()
    assert stream.closed
    with pytest.raises(RunnerError, match="not waiting"):
        process_input.write({"type": "user"})


@pytest.mark.parametrize("fails_on_write", [True, False])
def test_a_broken_pipe_is_a_runner_error_and_not_an_os_error(fails_on_write: bool) -> None:
    process_input = ProcessInput(BrokenStream(fails_on_write=fails_on_write))
    with pytest.raises(RunnerError, match="cannot be reached: the pipe is broken"):
        process_input.write({"type": "user"})


def test_closing_twice_closes_the_stream_once() -> None:
    closed: list[bool] = []

    class Counting(io.StringIO):
        def close(self) -> None:
            closed.append(True)
            super().close()

    process_input = ProcessInput(Counting())
    process_input.close()
    process_input.close()
    assert closed == [True]


def test_closing_a_broken_pipe_is_harmless() -> None:
    process_input = ProcessInput(BrokenStream())
    process_input.close()
    process_input.close()  # and the second time as well


def test_closing_without_a_stream_is_harmless() -> None:
    ProcessInput(None).close()

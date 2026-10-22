import json

import pytest

from wxclaude.core.claude.events import (
    AssistantText,
    PermissionDenied,
    RateLimit,
    RateWindow,
    SessionInit,
    Thinking,
    ToolResult,
    ToolUsed,
    TurnResult,
)
from wxclaude.core.claude.stream import parse_stream_line
from wxclaude.core.errors import StreamParseError

pytestmark = pytest.mark.unit


def _parse(entry: object) -> list[object]:
    return list(parse_stream_line(json.dumps(entry)))


def test_init() -> None:
    entry = {"type": "system", "subtype": "init", "session_id": "s", "model": "m"}
    entry["permissionMode"] = "plan"
    assert _parse(entry) == [SessionInit("s", "m", "plan")]


def test_system_lines() -> None:
    assert _parse({"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 7}) == [
        Thinking(7)
    ]
    denied = {
        "type": "system",
        "subtype": "permission_denied",
        "tool_name": "Bash",
        "message": "no",
    }
    assert _parse(denied) == [PermissionDenied("Bash", "no")]
    assert _parse({"type": "system", "subtype": "something else"}) == []


def test_assistant_blocks() -> None:
    entry = {
        "type": "assistant",
        "message": {
            "model": "claude-x",
            "content": [
                {"type": "thinking", "thinking": ""},
                {"type": "tool_use", "id": "t", "name": "Read", "input": {"file_path": "f"}},
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "  "},
            ],
        },
    }
    assert _parse(entry) == [
        Thinking(),
        ToolUsed("t", "Read", {"file_path": "f"}),
        AssistantText("Hello", "claude-x"),
    ]


def test_a_synthetic_model_is_no_model() -> None:
    entry = {
        "type": "assistant",
        "message": {"model": "<synthetic>", "content": [{"type": "text", "text": "Limit"}]},
    }
    assert _parse(entry) == [AssistantText("Limit", None)]


def test_tool_results() -> None:
    entry = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": "t", "is_error": True},
                {"type": "text", "text": "ignored"},
            ]
        },
    }
    assert _parse(entry) == [ToolResult("t", True)]
    assert _parse({"type": "user", "message": {"content": "plain"}}) == []


def test_rate_limit() -> None:
    entry = {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "allowed",
            "rateLimitType": "five_hour",
            "resetsAt": 5,
            "unifiedWindows": {
                "five_hour": {"utilization": 0.25, "resetsAt": 5},
                "seven_day": {"utilization": 0.5, "resetsAt": 9},
            },
        },
    }
    assert _parse(entry) == [
        RateLimit(
            "allowed",
            "five_hour",
            (RateWindow("five_hour", 0.25, 5), RateWindow("seven_day", 0.5, 9)),
        )
    ]


def test_rate_limit_without_windows_keeps_the_window_that_was_used() -> None:
    entry = {
        "type": "rate_limit_event",
        "rate_limit_info": {"status": "rejected", "rateLimitType": "seven_day", "resetsAt": 7},
    }
    expected = RateLimit("rejected", "seven_day", (RateWindow("seven_day", None, 7),))
    assert _parse(entry) == [expected]


def test_result() -> None:
    entry = {
        "type": "result",
        "subtype": "success",
        "result": "done",
        "duration_ms": 12,
        "total_cost_usd": 0.5,
        "num_turns": 2,
        "usage": {"input_tokens": 1, "output_tokens": 2},
    }
    (result,) = _parse(entry)
    assert isinstance(result, TurnResult)
    assert (result.is_error, result.text, result.duration_ms, result.num_turns) == (
        False,
        "done",
        12,
        2,
    )
    assert result.usage is not None
    assert result.usage.output_tokens == 2
    assert result.cost_usd == 0.5


def test_a_result_with_an_error_subtype_is_an_error() -> None:
    (result,) = _parse({"type": "result", "subtype": "error_max_turns"})
    assert isinstance(result, TurnResult)
    assert result.is_error


def test_unknown_types_give_nothing() -> None:
    assert _parse({"type": "prompt_suggestion", "suggestion": "x"}) == []
    assert _parse({"no": "type"}) == []


def test_lines_that_are_not_json_objects_raise() -> None:
    with pytest.raises(StreamParseError):
        parse_stream_line("hello")
    with pytest.raises(StreamParseError):
        parse_stream_line("[1, 2]")

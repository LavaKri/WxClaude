import json

import pytest

from wxclaude.core.events import PermissionRequest
from wxclaude.core.stream import parse_stream_line

pytestmark = pytest.mark.unit


def _parse(entry: object) -> list[object]:
    return list(parse_stream_line(json.dumps(entry)))


def test_a_permission_request() -> None:
    entry = {
        "type": "control_request",
        "request_id": "r1",
        "request": {
            "subtype": "can_use_tool",
            "tool_name": "Bash",
            "tool_use_id": "t1",
            "input": {"command": "touch x"},
            "description": "Create x",
            "blocked_path": "x",
            "permission_suggestions": [
                {"type": "addDirectories", "directories": ["d"], "destination": "session"},
                {
                    "type": "addRules",
                    "rules": [{"toolName": "Bash", "ruleContent": "touch x"}],
                    "behavior": "allow",
                    "destination": "localSettings",
                },
            ],
        },
    }
    assert _parse(entry) == [
        PermissionRequest(
            "r1", "Bash", "t1", {"command": "touch x"}, "Create x", "x", "Bash(touch x)"
        )
    ]


def test_a_rule_without_content_is_the_name_of_the_tool() -> None:
    entry = {
        "type": "control_request",
        "request_id": "r2",
        "request": {
            "subtype": "can_use_tool",
            "tool_name": "Edit",
            "input": {},
            "permission_suggestions": [
                {"type": "addRules", "rules": [{"toolName": "Edit"}], "behavior": "allow"},
                {"type": "setMode", "mode": "acceptEdits"},
            ],
        },
    }
    (request,) = _parse(entry)
    assert isinstance(request, PermissionRequest)
    assert request.suggested_rule == "Edit"


def test_a_request_without_suggestions_has_no_rule() -> None:
    entry = {"type": "control_request", "request_id": "r3", "request": {"subtype": "can_use_tool"}}
    (request,) = _parse(entry)
    assert isinstance(request, PermissionRequest)
    assert request.suggested_rule == ""


def test_other_control_requests_give_nothing() -> None:
    assert _parse({"type": "control_request", "request": {"subtype": "hook_callback"}}) == []

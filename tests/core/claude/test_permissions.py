import pytest

from wxclaude.core.claude.events import PermissionRequest
from wxclaude.core.claude.permissions import DEFAULT_DENIAL, Choice, Decision, describe_request

pytestmark = pytest.mark.unit


def _request(
    *,
    description: str = "Create x",
    blocked_path: str = "C:\\work\\x",
    values: dict[str, object] | None = None,
) -> PermissionRequest:
    arguments = values or {"command": "touch x", "description": "Create x", "timeout": 5}
    return PermissionRequest(
        "r", "Bash", "t", arguments, description, blocked_path, "Bash(touch x)"
    )


def test_a_request_is_described_line_by_line() -> None:
    assert describe_request(_request()).splitlines() == [
        "Tool: Bash",
        "Description: Create x",
        "Path: C:\\work\\x",
        "command: touch x",
        "timeout: 5",
    ]


def test_a_request_without_description_or_path() -> None:
    text = describe_request(_request(description="", blocked_path="", values={"file_path": "a"}))
    assert text.splitlines() == ["Tool: Bash", "file_path: a"]


def test_values_that_are_not_text_are_written_as_json() -> None:
    text = describe_request(_request(description="", values={"edits": [{"a": "é"}]}))
    assert 'edits: [{"a": "é"}]' in text


def test_a_denial_has_a_message() -> None:
    assert Decision(Choice.DENY).denial_message() == DEFAULT_DENIAL
    assert Decision(Choice.DENY, "  Not here  ").denial_message() == "Not here"

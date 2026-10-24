import pytest

from wxclaude.core.claude.events import PermissionRequest
from wxclaude.core.claude.permissions import describe_request, is_plan_request

pytestmark = pytest.mark.unit

PLAN = "# Plan\n\n1. Read the file\n2. Change it\n\nDone."


def _request(tool: str = "ExitPlanMode", **input_: object) -> PermissionRequest:
    return PermissionRequest("r", tool, "t", dict(input_), "", "", "")


def test_the_proposal_of_a_plan_is_recognized() -> None:
    assert is_plan_request(_request(plan=PLAN))
    assert not is_plan_request(_request("Bash", command="ls"))
    assert not is_plan_request(_request("Bash", plan=PLAN))  # the tool decides
    assert not is_plan_request(_request())  # no text of plan: shown as an ordinary request
    assert not is_plan_request(_request(plan=3))


def test_a_plan_is_shown_as_its_own_text_after_the_way_to_answer() -> None:
    text = describe_request(_request(plan=PLAN))
    lines = text.split("\n")
    assert lines[0] == (
        "Claude proposes this plan. Allow approves it; Deny asks for changes (explain below)."
    )
    assert lines[1] == ""
    assert "\n".join(lines[2:]) == PLAN
    assert "Tool:" not in text
    assert "plan:" not in text


def test_the_other_fields_of_a_plan_request_follow_the_plan() -> None:
    text = describe_request(_request(plan="Do it", planFilePath="/plans/a.md"))
    assert text.endswith("Do it\nplanFilePath: /plans/a.md")


def test_an_ordinary_request_is_unchanged() -> None:
    assert describe_request(_request("Bash", command="ls")) == "Tool: Bash\ncommand: ls"

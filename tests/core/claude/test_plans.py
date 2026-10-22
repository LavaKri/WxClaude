import json
from pathlib import Path

import pytest

from wxclaude.core.claude import plans as plans_module
from wxclaude.core.claude.plans import Plan, load_plans, plans_of_session
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.conversation.messages import Message, Role, ToolUse
from wxclaude.core.errors import PlanReadError, SessionReadError

pytestmark = pytest.mark.unit

SESSION = "d278c1fc-1d73-4c16-a899-5bdb1831fe5c"


def _write_tool(path: Path, content: str = "# Plan\n1. Do it") -> ToolUse:
    return ToolUse("t", "Write", {"file_path": str(path), "content": content})


def _session(*tools: ToolUse) -> Session:
    return Session(messages=[Message("a", Role.ASSISTANT, "Plan written", tools=list(tools))])


def test_a_write_in_the_plans_folder_is_a_plan_whose_text_is_read_from_the_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "plans" / "calm-fox.md"
    path.parent.mkdir()
    path.write_text("# Plan\n1. Do it\n2. Then this (edited later)", encoding="utf-8")
    (plan,) = plans_of_session(_session(_write_tool(path)), tmp_path)
    assert plan == Plan(path, "# Plan\n1. Do it\n2. Then this (edited later)", in_file=True)
    assert plan.line == "calm-fox.md"


def test_a_plan_whose_file_is_gone_keeps_what_the_session_wrote(tmp_path: Path) -> None:
    path = tmp_path / "plans" / "gone.md"
    (plan,) = plans_of_session(_session(_write_tool(path, "# Old plan")), tmp_path)
    assert plan == Plan(path, "# Old plan", in_file=False)
    assert plan.line == "gone.md, file missing, text from the session"


def test_other_writes_and_other_tools_are_not_plans(tmp_path: Path) -> None:
    tools = (
        _write_tool(tmp_path / "notes.md"),
        _write_tool(tmp_path / "plans-elsewhere" / "x.md"),
        ToolUse("e", "Edit", {"file_path": str(tmp_path / "plans" / "e.md")}),
        ToolUse("w", "Write", {"content": "no path"}),
        ToolUse("w2", "Write", {"file_path": 3}),
    )
    assert plans_of_session(_session(*tools), tmp_path) == []


def test_plans_come_oldest_first_and_a_plan_written_again_keeps_its_place(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "plans" / "a.md", tmp_path / "plans" / "b.md"
    session = _session(
        _write_tool(first, "one"), _write_tool(second, "two"), _write_tool(first, "one again")
    )
    plans = plans_of_session(session, tmp_path)
    assert [(plan.path.name, plan.text) for plan in plans] == [
        ("a.md", "one again"),
        ("b.md", "two"),
    ]


def test_a_conversation_without_history_has_no_plan(tmp_path: Path) -> None:
    assert load_plans(SESSION, tmp_path, tmp_path / "projects") == []


def test_the_plans_of_a_session_file_are_found_through_the_conversation_id(
    tmp_path: Path,
) -> None:
    plan_file = tmp_path / "plans" / "calm-fox.md"
    plan_file.parent.mkdir()
    plan_file.write_text("# The plan", encoding="utf-8")
    folder = tmp_path / "projects" / "folder"
    folder.mkdir(parents=True)
    entries = [
        {"type": "user", "uuid": "u", "message": {"role": "user", "content": "Plan it"}},
        {
            "type": "assistant",
            "uuid": "a",
            "message": {
                "role": "assistant",
                "model": "claude-haiku-4-5",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Write",
                        "input": {"file_path": str(plan_file), "content": "# The plan"},
                    },
                    {"type": "text", "text": "I wrote the plan."},
                ],
            },
        },
    ]
    (folder / f"{SESSION}.jsonl").write_text(
        "\n".join(json.dumps(entry) for entry in entries), encoding="utf-8"
    )
    (plan,) = load_plans(SESSION, tmp_path, tmp_path / "projects")
    assert (plan.path, plan.text) == (plan_file, "# The plan")


def test_an_unreadable_session_file_is_a_plan_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "projects" / "folder"
    folder.mkdir(parents=True)
    (folder / f"{SESSION}.jsonl").write_text("{}", encoding="utf-8")

    def fail(_path: Path) -> Session:
        raise SessionReadError("broken")

    monkeypatch.setattr(plans_module, "read_session", fail)
    with pytest.raises(PlanReadError, match="Cannot read the plans"):
        load_plans(SESSION, tmp_path, tmp_path / "projects")

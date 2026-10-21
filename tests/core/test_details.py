import pytest

from wxclaude.core.details import Link, message_details, tool_detail, tool_line
from wxclaude.core.messages import Message, Role, ToolUse

pytestmark = pytest.mark.unit

TABLE = """Intro

| Name | Size |
|---|---|
| a.txt | 3 |
| b.txt |  |

After
"""


def _answer(text: str, tools: list[ToolUse] | None = None) -> Message:
    return Message("a", Role.ASSISTANT, text, model="m", tools=tools or [])


def test_a_table_is_found_with_its_lines() -> None:
    details = message_details(_answer(TABLE))
    (table,) = details.tables
    assert table.headers == ("Name", "Size")
    assert table.rows == (("a.txt", "3"), ("b.txt", ""))
    assert (table.first_line, table.end_line) == (2, 6)
    assert table.source.splitlines()[0] == "| Name | Size |"
    assert details.table_at(1) is None
    assert details.table_at(2) is table
    assert details.table_at(5) is table
    assert details.table_at(6) is None


def test_a_table_row_is_read_as_one_line_without_empty_cells() -> None:
    (table,) = message_details(_answer(TABLE)).tables
    assert [table.row_line(row) for row in table.rows] == [
        "Name: a.txt, Size: 3",
        "Name: b.txt",
    ]
    assert table.row_line(("", "")) == "Empty row"


def test_a_table_in_a_code_block_is_not_a_table() -> None:
    text = "```\n| a | b |\n|---|---|\n| 1 | 2 |\n```"
    assert message_details(_answer(text)).tables == []


def test_links_are_found_with_their_line() -> None:
    text = (
        "See [the docs](https://example.com/docs).\n"
        "Also <https://example.org> and\n"
        "[mail](mailto:a@b.c)"
    )
    details = message_details(_answer(text))
    assert details.links == [
        Link("the docs", "https://example.com/docs", 0),
        Link("https://example.org", "https://example.org", 1),
        Link("mail", "mailto:a@b.c", 2),
    ]
    assert details.link_index_at(2) == 2
    assert details.link_index_at(7) == 0  # no link there: the first one


def test_a_link_in_a_table_is_found() -> None:
    text = "| Site |\n|---|\n| [x](https://x.test) |"
    assert message_details(_answer(text)).links == [Link("x", "https://x.test", 2)]


def test_only_web_and_mail_links_can_be_opened() -> None:
    assert Link("a", "https://a.test", 0).can_open
    assert Link("a", "HTTP://a.test", 0).can_open
    assert Link("a", "mailto:a@b.c", 0).can_open
    assert not Link("a", "file:///c:/windows", 0).can_open
    assert not Link("a", "javascript:alert(1)", 0).can_open


def test_link_labels() -> None:
    assert Link("docs", "https://a.test", 0).label() == "docs, https://a.test"
    assert Link("https://a.test", "https://a.test", 0).label() == "https://a.test"
    assert Link("", "https://a.test", 0).label() == "https://a.test"


def test_a_message_without_details() -> None:
    details = message_details(_answer("Just text."))
    assert (details.tools, details.tables, details.links) == ([], [], [])


def test_tools_are_kept_from_the_message() -> None:
    tool = ToolUse("t", "Bash", {"command": "ls"}, "a\nb")
    assert message_details(_answer("x", [tool])).tools == [tool]


def test_a_tool_line_names_the_tool_and_what_it_worked_on() -> None:
    assert tool_line(ToolUse("t", "Bash", {"command": "git status"})) == "Bash, git status"
    assert tool_line(ToolUse("t", "Read", {"file_path": "a.py"}, is_error=True)) == (
        "Read, a.py, failed"
    )
    assert tool_line(ToolUse("t", "TodoWrite", {"todos": []})) == "TodoWrite"


def test_a_tool_line_is_one_short_line() -> None:
    line = tool_line(ToolUse("t", "Bash", {"command": "echo a\n" + "b" * 200}))
    assert "\n" not in line
    assert line.endswith("…")
    assert len(line) <= len("Bash, ") + 80


def test_a_tool_detail_gives_the_arguments_and_the_result() -> None:
    tool = ToolUse("t", "Edit", {"file_path": "a.py", "count": 2}, "done")
    assert tool_detail(tool).splitlines() == [
        "Tool: Edit",
        "file_path: a.py",
        "count: 2",
        "",
        "Result:",
        "done",
    ]


def test_a_tool_detail_says_when_it_failed_and_skips_an_empty_result() -> None:
    assert tool_detail(ToolUse("t", "Bash", {}, "", is_error=True)).splitlines() == [
        "Tool: Bash",
        "The tool failed.",
    ]

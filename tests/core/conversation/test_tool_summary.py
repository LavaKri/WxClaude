"""The line under an answer that sums up the tools Claude used."""

import pytest

from wxclaude.core.conversation.messages import ToolUse
from wxclaude.core.conversation.tool_summary import summarize_tools

pytestmark = pytest.mark.unit


def _tool(name: str, path: str | None = None, *, error: bool = False, **extra: object) -> ToolUse:
    arguments: dict[str, object] = dict(extra)
    if path is not None:
        arguments["file_path"] = path
    return ToolUse(f"{name}-{len(arguments)}", name, arguments, is_error=error)


def test_an_answer_without_tools_has_no_line() -> None:
    assert summarize_tools([]) == ""


def test_the_commands_the_files_and_the_other_tools_are_counted() -> None:
    tools = [
        *(_tool("Bash", command=f"echo {n}") for n in range(4)),
        _tool("PowerShell", command="dir"),
        _tool("Edit", "a.py"),
        _tool("Write", "b.py"),
        _tool("Read", "a.py"),
        _tool("Read", "c.py"),
        _tool("Read", "d.py"),
        _tool("Grep", pattern="x"),
        _tool("WebFetch", url="https://a.test"),
        _tool("Agent"),
    ]
    assert summarize_tools(tools) == (
        "5 commands run, 2 files modified, 3 files read, 3 other tools used"
    )


def test_a_file_changed_or_read_several_times_counts_once() -> None:
    tools = [
        _tool("Edit", "C:\\work\\a.py"),
        _tool("Edit", "c:/work/A.py"),  # the same file, written another way
        _tool("Write", "C:/work/A.py"),
        _tool("Read", "x.py"),
        _tool("Read", "x.py"),
    ]
    assert summarize_tools(tools) == "1 file modified, 1 file read"


def test_a_tool_without_a_path_counts_as_one_file() -> None:
    assert summarize_tools([_tool("Edit"), _tool("Edit"), _tool("Read")]) == (
        "2 files modified, 1 file read"
    )


def test_notebooks_are_files_modified() -> None:
    tool = ToolUse("n", "NotebookEdit", {"notebook_path": "a.ipynb"})
    assert summarize_tools([tool]) == "1 file modified"


def test_what_is_zero_is_left_out_and_one_is_singular() -> None:
    assert summarize_tools([_tool("Bash", command="ls")]) == "1 command run"
    assert summarize_tools([_tool("Glob", pattern="*")]) == "1 other tool used"


def test_the_failures_are_added_at_the_end() -> None:
    tools = [
        _tool("Bash", command="ls"),
        _tool("Bash", command="rm x", error=True),
        _tool("Read", "x.py", error=True),
    ]
    assert summarize_tools(tools) == "2 commands run, 1 file read, of which 2 failed"


def test_a_failure_alone_is_still_a_tool() -> None:
    assert summarize_tools([_tool("Skill", error=True)]) == "1 other tool used, of which 1 failed"

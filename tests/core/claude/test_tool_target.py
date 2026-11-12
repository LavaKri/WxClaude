import pytest

from wxclaude.core.claude.events import ToolUsed
from wxclaude.core.claude.progress import progress_for
from wxclaude.core.claude.tool_target import MAX_TARGET_LENGTH, tool_detail
from wxclaude.core.speech.announcements import Announce, AnnouncementCenter

pytestmark = pytest.mark.unit

ON = Announce.CLAUDE_USING_TOOL_ON
TO_RUN = Announce.CLAUDE_USING_TOOL_TO_RUN


@pytest.mark.parametrize(
    ("name", "tool_input", "expected"),
    [
        ("Edit", {"file_path": "C:\\Users\\Codeur\\Dev\\tools\\build.bat"}, (ON, "build.bat")),
        ("Write", {"file_path": "C:/work/notes.md"}, (ON, "notes.md")),
        ("Read", {"file_path": "relative.txt"}, (ON, "relative.txt")),
        ("NotebookEdit", {"notebook_path": "C:\\a\\b.ipynb"}, (ON, "b.ipynb")),
        ("Grep", {"pattern": "def main", "path": "C:\\src"}, (ON, "def main")),
        ("Glob", {"pattern": "**/*.py"}, (ON, "**/*.py")),
        (
            "WebFetch",
            {"url": "https://docs.example.org/page?token=secret"},
            (ON, "docs.example.org"),
        ),
        ("WebSearch", {"query": "named pipe windows"}, (ON, "named pipe windows")),
        ("Task", {"description": "Explore the code"}, (ON, "Explore the code")),
        ("Bash", {"command": "git status --short"}, (TO_RUN, "git")),
        ("Bash", {"command": '"C:\\Program\\x.exe" --key abc'}, (TO_RUN, "x.exe")),
        ("PowerShell", {"command": "Get-ChildItem -Recurse"}, (TO_RUN, "Get-ChildItem")),
    ],
)
def test_what_the_tool_works_on(
    name: str, tool_input: dict[str, object], expected: tuple[Announce, str]
) -> None:
    assert tool_detail(name, tool_input) == expected


@pytest.mark.parametrize(
    ("name", "tool_input"),
    [
        ("Edit", {}),
        ("Edit", {"file_path": ""}),
        ("Edit", {"file_path": 5}),
        ("Bash", {"command": "   "}),
        ("Bash", {}),
        ("WebFetch", {"url": "not a url"}),
        ("TodoWrite", {"todos": []}),
        ("mcp__server__tool", {"anything": "x"}),
    ],
)
def test_a_tool_without_a_target_adds_nothing(name: str, tool_input: dict[str, object]) -> None:
    assert tool_detail(name, tool_input) is None


def test_a_command_is_never_given_whole() -> None:
    detail = tool_detail("Bash", {"command": "curl -H 'Authorization: Bearer SECRET' https://x"})
    assert detail == (TO_RUN, "curl")


def test_a_long_target_is_shortened_on_one_line() -> None:
    detail = tool_detail("Grep", {"pattern": "word " * 40})
    assert detail is not None
    assert len(detail[1]) == MAX_TARGET_LENGTH
    assert detail[1].endswith("…")
    assert "\n" not in detail[1]


def test_the_progress_keeps_the_spoken_text_and_adds_the_detail_for_the_history() -> None:
    progress = progress_for(ToolUsed("t1", "Edit", {"file_path": "C:\\x\\build.bat"}))
    assert progress is not None
    assert progress.announce is Announce.CLAUDE_USING_TOOL
    assert progress.values == {"tool": "Edit", "history_as": ON, "target": "build.bat"}
    assert (
        AnnouncementCenter.text(progress.announce, name="Claude", **progress.values)
        == "Claude uses the tool Edit."
    )


def test_a_tool_without_a_target_has_the_same_progress_as_before() -> None:
    progress = progress_for(ToolUsed("t1", "TodoWrite", {"todos": []}))
    assert progress is not None
    assert progress.values == {"tool": "TodoWrite"}

import pytest

from wxclaude.core.claude.events import (
    AssistantText,
    PermissionDenied,
    SessionInit,
    Thinking,
    ToolResult,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.progress import Outcome, Progress, progress_for, turn_outcome
from wxclaude.core.speech.announcements import Announce

pytestmark = pytest.mark.unit


def _result(*, is_error: bool = False, text: str = "", subtype: str = "success") -> TurnResult:
    return TurnResult(is_error, subtype, text, None, None, None, None)


def test_events_that_stand_for_progress() -> None:
    assert progress_for(Thinking()) == Progress(Announce.CLAUDE_THINKING)
    assert progress_for(ToolUsed("t", "Read")) == Progress(
        Announce.CLAUDE_USING_TOOL, {"tool": "Read"}
    )
    assert progress_for(AssistantText("x", None)) == Progress(Announce.CLAUDE_ANSWERING)
    assert progress_for(PermissionDenied("Bash", "no")) == Progress(
        Announce.PERMISSION_DENIED, {"tool": "Bash"}
    )


def test_a_denial_we_decided_ourselves_is_not_announced_again() -> None:
    assert progress_for(PermissionDenied("Bash", "no", "hook")) is None
    assert progress_for(PermissionDenied("Bash", "no", "mode")) == Progress(
        Announce.PERMISSION_DENIED, {"tool": "Bash"}
    )


def test_events_that_say_nothing() -> None:
    assert progress_for(SessionInit("s", "m", "p")) is None
    assert progress_for(ToolResult("t", False)) is None
    assert progress_for(_result()) is None
    assert progress_for(TurnEnded(0, False, "")) is None


def test_a_clean_end_with_a_result_is_done() -> None:
    assert turn_outcome(_result(), TurnEnded(0, False, "")).outcome is Outcome.DONE


def test_an_interruption_wins_over_everything() -> None:
    outcome = turn_outcome(_result(is_error=True, text="x"), TurnEnded(1, True, "boom"))
    assert outcome.outcome is Outcome.INTERRUPTED


def test_an_error_result_fails_with_its_text_or_subtype() -> None:
    failed = turn_outcome(_result(is_error=True, text="Too many turns"), TurnEnded(1, False, ""))
    assert (failed.outcome, failed.details) == (Outcome.FAILED, "Too many turns")
    bare = turn_outcome(_result(is_error=True, subtype="error_max_turns"), TurnEnded(1, False, ""))
    assert bare.details == "error_max_turns"


def test_no_result_fails_with_stderr_then_diagnostics_then_the_exit_code() -> None:
    crashed = turn_outcome(None, TurnEnded(2, False, "not logged in", ["odd line"]))
    assert (crashed.outcome, crashed.details) == (Outcome.FAILED, "not logged in\nodd line")
    assert turn_outcome(None, TurnEnded(3, False, "")).details == "exit code 3"


def test_a_result_with_a_bad_exit_code_is_a_failure() -> None:
    assert turn_outcome(_result(), TurnEnded(1, False, "")).outcome is Outcome.FAILED

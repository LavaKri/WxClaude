import pytest

from wxclaude.core.claude.events import (
    ApiRetry,
    AssistantText,
    Compacted,
    McpServer,
    PermissionDenied,
    SessionInit,
    Thinking,
    ToolResult,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.progress import (
    Outcome,
    Progress,
    compaction_progress,
    mcp_progress,
    mode_progress,
    progress_for,
    retry_progress,
    turn_outcome,
)
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


def test_a_retry_says_the_error_and_the_attempt() -> None:
    assert retry_progress(ApiRetry(2, 10, 529, "overloaded")) == Progress(
        Announce.SERVER_RETRY, {"reason": "overloaded", "attempt": 2, "total": 10}
    )
    assert retry_progress(ApiRetry(1, 10, 502, "server_error")).values["reason"] == "server error"
    assert retry_progress(ApiRetry(1, 10, 502, "")).values["reason"] == "status 502"
    assert retry_progress(ApiRetry(1, 10, None, "")).values["reason"] == "unknown error"


def test_a_compaction_says_the_sizes_when_they_are_known() -> None:
    assert compaction_progress(Compacted("auto", 362766, 76351)) == Progress(
        Announce.CONVERSATION_COMPACTED,
        {"trigger": "automatic", "before": "362766", "after": "76351"},
    )
    assert compaction_progress(Compacted("manual", None, None)) == Progress(
        Announce.CONVERSATION_COMPACTED_UNKNOWN, {"trigger": "manual"}
    )


def test_a_mode_that_was_not_applied_is_told() -> None:
    assert mode_progress("manual", "default", masked=False) is None
    assert mode_progress("plan", "plan", masked=True) is None
    assert mode_progress("plan", "", masked=True) is None
    assert mode_progress("", "default", masked=True) is None
    assert mode_progress("plan", "default", masked=True) == Progress(
        Announce.MODE_FORCED_MANUAL, {"asked": "plan"}
    )
    assert mode_progress("auto", "default", masked=False) == Progress(
        Announce.MODE_DIFFERENT, {"actual": "manual", "asked": "auto"}
    )
    assert mode_progress("acceptEdits", "plan", masked=True) == Progress(
        Announce.MODE_DIFFERENT, {"actual": "plan", "asked": "acceptEdits"}
    )


def test_an_mcp_server_that_failed_or_is_slow_is_told_once_per_state() -> None:
    reported: dict[str, str] = {}
    servers = (McpServer("ollama", "connected"), McpServer("crash", "failed"))
    assert mcp_progress(servers, reported) == [
        Progress(Announce.MCP_SERVER_FAILED, {"server": "crash"})
    ]
    assert mcp_progress(servers, reported) == []  # not at each message
    slow = (McpServer("crash", "pending"),)
    assert mcp_progress(slow, reported) == [Progress(Announce.MCP_SERVER_SLOW, {"server": "crash"})]
    assert mcp_progress((McpServer("crash", "connected"),), reported) == []
    assert reported == {}  # it works now: a new failure is told again
    assert len(mcp_progress((McpServer("crash", "failed"),), reported)) == 1


def test_a_state_that_is_not_known_says_nothing() -> None:
    reported: dict[str, str] = {}
    assert mcp_progress((McpServer("docs", "needs-auth"),), reported) == []
    assert reported == {}


def test_a_clean_end_with_a_result_is_done() -> None:
    assert turn_outcome(_result(), TurnEnded(0, False, "")).outcome is Outcome.DONE


def test_an_interruption_wins_over_everything() -> None:
    outcome = turn_outcome(_result(is_error=True, text="x"), TurnEnded(1, True, "boom"))
    assert outcome.outcome is Outcome.INTERRUPTED


def test_an_error_result_fails_with_its_text_or_subtype() -> None:
    failed = turn_outcome(_result(is_error=True, text="Too many turns"), TurnEnded(1, False, ""))
    assert (failed.outcome, failed.details) == (Outcome.FAILED, "Too many turns")
    bare = turn_outcome(_result(is_error=True, subtype="error_other"), TurnEnded(1, False, ""))
    assert bare.details == "error_other"


def test_the_limit_of_turns_is_explained() -> None:
    result = TurnResult(True, "error_max_turns", "", None, None, None, 2)
    outcome = turn_outcome(result, TurnEnded(1, False, ""))
    assert outcome.outcome is Outcome.FAILED
    assert "limit of turns" in outcome.details


def test_no_result_fails_with_stderr_then_diagnostics_then_the_exit_code() -> None:
    crashed = turn_outcome(None, TurnEnded(2, False, "not logged in", ["odd line"]))
    assert (crashed.outcome, crashed.details) == (Outcome.FAILED, "not logged in\nodd line")
    assert turn_outcome(None, TurnEnded(3, False, "")).details == "exit code 3"


def test_a_result_with_a_bad_exit_code_is_a_failure() -> None:
    assert turn_outcome(_result(), TurnEnded(1, False, "")).outcome is Outcome.FAILED


def test_a_notice_of_the_cli_is_not_taken_for_the_cause_of_a_failure() -> None:
    notice = '[claude-code:unrecognized_model] {"model": "deepseek-chat"}'
    crashed = turn_outcome(None, TurnEnded(2, False, f"{notice}\nconnection refused"))
    assert crashed.details == "connection refused"
    assert turn_outcome(None, TurnEnded(2, False, notice)).details == "exit code 2"


def test_the_warning_about_the_claude_login_is_a_notice_too() -> None:
    warning = (
        "⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth source "
        "is set and takes precedence over your claude.ai login"
    )
    crashed = turn_outcome(None, TurnEnded(2, False, f"{warning}\nconnection refused"))
    assert crashed.details == "connection refused"

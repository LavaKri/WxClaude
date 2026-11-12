"""What the run presenter tells while a message goes: the retries of the CLI after an error of the
server, the compaction of the conversation, a permission mode that was not applied."""

from pathlib import Path

import pytest
from fake_vault import FakeVault
from test_run_presenter_security import presenter_for, security_for

from wxclaude.core.claude.events import ApiRetry, Compacted, McpServer, SessionInit, Thinking
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import Provider, ProviderStore
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.security_presenter import ApprovalChoice

pytestmark = pytest.mark.unit


def agent(mode: str, provider: str = "claude") -> Agent:
    return Agent(model="m", effort="low", permission_mode=mode, provider=provider)


def deepseek() -> ProviderStore:
    store = ProviderStore(FakeVault())
    store.add(Provider(id="deepseek", name="DeepSeek", base_url="http://x", tiers=["m"]))
    store.set_key("deepseek", "sk-1")
    return store


def test_a_retry_after_an_error_of_the_server_is_said_each_time(tmp_path: Path) -> None:
    presenter, runner, view = presenter_for(tmp_path, None)
    presenter.start("hello", agent("manual"))
    presenter.on_event(ApiRetry(1, 10, 529, "overloaded"))
    presenter.on_event(ApiRetry(2, 10, 529, "overloaded"))
    assert view.said[-2:] == [
        (
            Announce.SERVER_RETRY,
            {"name": "Claude", "reason": "overloaded", "attempt": 1, "total": 10},
        ),
        (
            Announce.SERVER_RETRY,
            {"name": "Claude", "reason": "overloaded", "attempt": 2, "total": 10},
        ),
    ]
    assert runner.interrupts == 0  # the user decides whether to interrupt


def test_the_progress_after_a_retry_is_said_again(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    presenter.start("hello", agent("manual"))  # says: thinking
    presenter.on_event(ApiRetry(1, 10, 529, "overloaded"))
    presenter.on_event(Thinking())
    assert view.announces()[-3:] == [
        Announce.CLAUDE_THINKING,
        Announce.SERVER_RETRY,
        Announce.CLAUDE_THINKING,
    ]


def test_a_refusal_of_the_credentials_is_not_a_retry_to_wait_for(tmp_path: Path) -> None:
    presenter, runner, view = presenter_for(tmp_path, None)
    presenter.start("hello", agent("manual"))
    presenter.on_event(ApiRetry(1, 10, 401, "authentication_failed"))
    assert Announce.SERVER_RETRY not in view.announces()
    assert runner.interrupts == 1


def test_the_compaction_of_the_conversation_is_said(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    presenter.start("hello", agent("manual"))
    presenter.on_event(Compacted("auto", 362766, 76351))
    assert view.said[-1] == (
        Announce.CONVERSATION_COMPACTED,
        {"name": "Claude", "trigger": "automatic", "before": "362766", "after": "76351"},
    )


def test_an_mcp_server_that_did_not_start_is_said_once_not_at_each_message(
    tmp_path: Path,
) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    init = SessionInit(
        "s", "m", "default", (McpServer("ollama", "failed"), McpServer("docs", "connected"))
    )
    presenter.start("one", agent("manual"))
    presenter.on_event(init)
    presenter.start("two", agent("manual"))
    presenter.on_event(init)
    assert view.announces().count(Announce.MCP_SERVER_FAILED) == 1
    assert (Announce.MCP_SERVER_FAILED, {"name": "Claude", "server": "ollama"}) in view.said


def test_a_slow_mcp_server_is_said_with_its_own_text(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    presenter.start("one", agent("manual"))
    presenter.on_event(SessionInit("s", "m", "default", (McpServer("slow", "pending"),)))
    assert view.said[-1] == (Announce.MCP_SERVER_SLOW, {"name": "Claude", "server": "slow"})


def test_a_mode_that_is_applied_says_nothing(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    presenter.start("hello", agent("plan"))
    presenter.on_event(SessionInit("s", "m", "plan"))
    presenter.start("hello", agent("manual"))
    presenter.on_event(SessionInit("s", "m", "default"))  # the CLI calls manual "default"
    assert Announce.MODE_DIFFERENT not in view.announces()
    assert Announce.MODE_FORCED_MANUAL not in view.announces()


def test_a_mode_forced_by_the_masked_key_is_explained(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None, providers=deepseek())
    assert presenter.start("hello", agent("plan", "deepseek"))
    presenter.on_event(SessionInit("s", "m", "default"))
    assert view.said[-1] == (Announce.MODE_FORCED_MANUAL, {"name": "DeepSeek", "asked": "plan"})


def test_another_mode_that_was_not_applied_is_told_with_both_names(tmp_path: Path) -> None:
    presenter, _runner, view = presenter_for(tmp_path, None)
    presenter.start("hello", agent("auto"))
    presenter.on_event(SessionInit("s", "m", "default"))
    assert view.said[-1] == (
        Announce.MODE_DIFFERENT,
        {"name": "Claude", "actual": "manual", "asked": "auto"},
    )


def test_a_folder_that_is_not_approved_is_no_surprise(tmp_path: Path) -> None:
    # The restricted launch makes the mode manual on purpose (the security says so already).
    security, workspace = security_for(tmp_path, ApprovalChoice.KEEP_RESTRICTED)
    presenter, _runner, view = presenter_for(workspace, security)
    presenter.start("hello", agent("acceptEdits"))
    presenter.on_event(SessionInit("s", "m", "default"))
    presenter.start("hello", agent("plan"))  # kept: it lets Claude read but not act
    presenter.on_event(SessionInit("s", "m", "plan"))
    assert Announce.MODE_DIFFERENT not in view.announces()
    assert Announce.MODE_FORCED_MANUAL not in view.announces()

"""The run presenter and the trust of the folder: a restricted launch, the guard of the files."""

from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles
from fake_security_view import FakeView as SecurityView
from fake_vault import FakeVault
from test_run_presenter import CONVERSATION, FakeRunner, FakeView

from wxclaude.core.claude.events import PermissionRequest
from wxclaude.core.claude.permissions import Choice, Decision
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import Provider, ProviderStore
from wxclaude.core.config.settings import Settings
from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.core.security.key_relay import KeyRelay
from wxclaude.core.security.watch import ExternalChangeError, FileState, FileStatus
from wxclaude.presenters.run_presenter import RunLinks, RunPresenter
from wxclaude.presenters.security_presenter import (
    AlertChoice,
    ApprovalChoice,
    SecurityPresenter,
)
from wxclaude.presenters.shared import Shared

pytestmark = pytest.mark.unit

AGENT = Agent(model="haiku", effort="low", permission_mode="manual")


def presenter_for(
    workspace: Path,
    security: SecurityPresenter | None,
    files: FakeClaudeFiles | None = None,
    view: FakeView | None = None,
    providers: ProviderStore | None = None,
    settings: Settings | None = None,
    relay: KeyRelay | None = None,
) -> tuple[RunPresenter, FakeRunner, FakeView]:
    view = view or FakeView()
    runner = FakeRunner()
    shared = Shared(
        settings or Settings.load(None),
        UsageTracker(),
        files or FakeClaudeFiles(),
        security,
        providers,
        relay,
    )
    links = RunLinks(
        workspace=lambda: workspace,
        conversation_id=lambda: CONVERSATION,
        conversation_name=lambda: "",
        fork_from=lambda: "",
        is_closing=lambda: False,
        state_changed=lambda: None,
    )
    return RunPresenter(view, runner, shared, links), runner, view


def security_for(
    tmp_path: Path, approval: ApprovalChoice, alert: AlertChoice | None = None
) -> tuple[SecurityPresenter, Path]:
    workspace = tmp_path / "work"
    (workspace / ".claude").mkdir(parents=True)
    security = SecurityPresenter(SecurityView(approval=approval, alert=alert))
    security.open(workspace, WorkspaceState.load(workspace, tmp_path / "data"))
    security.greet()
    return security, workspace


def test_without_a_trust_state_the_launch_is_not_restricted(tmp_path: Path) -> None:
    presenter, runner, _view = presenter_for(tmp_path, None)
    assert presenter.start("hello", AGENT)
    assert not runner.requests[0].restricted


def test_a_folder_that_is_not_approved_is_launched_restricted(tmp_path: Path) -> None:
    security, workspace = security_for(tmp_path, ApprovalChoice.KEEP_RESTRICTED)
    presenter, runner, _view = presenter_for(workspace, security)
    assert presenter.start("hello", AGENT)
    assert runner.requests[0].restricted


def test_an_approved_folder_is_launched_as_before(tmp_path: Path) -> None:
    security, workspace = security_for(tmp_path, ApprovalChoice.APPROVE)
    presenter, runner, _view = presenter_for(workspace, security)
    assert presenter.start("hello", AGENT)
    assert not runner.requests[0].restricted


def test_the_rule_is_written_through_the_guard_of_the_workspace(tmp_path: Path) -> None:
    security, workspace = security_for(tmp_path, ApprovalChoice.APPROVE)
    files = FakeClaudeFiles()
    presenter, _runner, view = presenter_for(
        workspace, security, files, FakeView(Decision(Choice.ALLOW_ALWAYS))
    )
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {}, "", "", "Bash(touch x)"))
    assert files.rules == [(workspace, "Bash(touch x)")]
    assert files.guards == [security.guard]
    assert files.guards[0] is not None
    assert view.errors == []


def test_a_rule_refused_for_a_change_from_outside_goes_to_the_user(tmp_path: Path) -> None:
    security, workspace = security_for(tmp_path, ApprovalChoice.APPROVE, AlertChoice.ACCEPT)
    error = ExternalChangeError(
        [FileStatus(".claude/settings.local.json", FileState.CHANGED, True)]
    )
    files = FakeClaudeFiles(allow_external_change=error)
    presenter, runner, view = presenter_for(
        workspace, security, files, FakeView(Decision(Choice.ALLOW_ALWAYS))
    )
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {}, "", "", "Bash(touch x)"))
    assert runner.answers == [("allow", "r1")]  # the tool itself is still allowed
    assert files.rules == []
    assert len(view.errors) == 1
    assert ".claude/settings.local.json" in view.errors[0]
    assert isinstance(security._view, SecurityView)
    assert [spec.lines for spec in security._view.alerts] == [
        [".claude/settings.local.json, changed"]
    ]


def providers_with_deepseek(key: str = "") -> ProviderStore:
    store = ProviderStore(FakeVault())
    store.add(
        Provider(
            id="deepseek",
            name="DeepSeek",
            base_url="https://api.deepseek.com/anthropic",
            tiers=["deepseek-chat"],
        )
    )
    if key:
        store.set_key("deepseek", key)
    return store


def test_a_message_to_a_provider_carries_the_provider_and_its_key(tmp_path: Path) -> None:
    presenter, runner, _view = presenter_for(
        tmp_path, None, providers=providers_with_deepseek("sk-1")
    )
    agent = Agent(
        model="deepseek-chat", effort="low", permission_mode="manual", provider="deepseek"
    )
    assert presenter.start("hello", agent)
    launch = runner.requests[0].provider
    assert launch is not None
    assert (launch.provider.id, launch.key, launch.scrub) == ("deepseek", "sk-1", True)


def test_a_message_with_the_transmission_relayed_carries_the_relay_and_not_the_key(
    tmp_path: Path,
) -> None:
    settings = Settings.load(None)
    settings.key_transmission = "relayed"
    relay = KeyRelay(check_seconds=3600)
    try:
        presenter, runner, _view = presenter_for(
            tmp_path,
            None,
            providers=providers_with_deepseek("sk-1"),
            settings=settings,
            relay=relay,
        )
        agent = Agent(
            model="deepseek-chat", effort="low", permission_mode="plan", provider="deepseek"
        )
        assert presenter.start("hello", agent)
        launch = runner.requests[0].provider
        assert launch is not None
        assert launch.key == ""
        assert launch.relay is not None
        assert not launch.scrub
    finally:
        relay.stop()


def test_a_message_to_claude_carries_no_provider(tmp_path: Path) -> None:
    presenter, runner, _view = presenter_for(
        tmp_path, None, providers=providers_with_deepseek("sk-1")
    )
    assert presenter.start("hello", Agent("haiku", "low", "manual", "claude"))
    assert runner.requests[0].provider is None


def test_a_provider_without_a_key_is_not_started_and_the_user_is_told(tmp_path: Path) -> None:
    presenter, runner, view = presenter_for(tmp_path, None, providers=providers_with_deepseek())
    agent = Agent(
        model="deepseek-chat", effort="low", permission_mode="manual", provider="deepseek"
    )
    assert not presenter.start("hello", agent)
    assert runner.requests == []
    assert view.errors == ["Claude cannot be started.\nNo key is saved for DeepSeek."]
    assert not presenter.busy


def test_a_key_that_cannot_be_decrypted_is_not_started_and_the_user_is_told(
    tmp_path: Path,
) -> None:
    store = providers_with_deepseek("sk-1")
    locked = ProviderStore(FakeVault(locked=True))
    locked.add(store.get("deepseek"))
    locked._keys["deepseek"] = "blob"
    presenter, runner, view = presenter_for(tmp_path, None, providers=locked)
    agent = Agent(
        model="deepseek-chat", effort="low", permission_mode="manual", provider="deepseek"
    )
    assert not presenter.start("hello", agent)
    assert runner.requests == []
    assert "enter it again" in view.errors[0]

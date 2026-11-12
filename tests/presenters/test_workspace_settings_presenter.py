"""The settings of a workspace, with a fake dialog: the order of what is done, what is written,
and what is said when the rules cannot be written."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from fake_security_view import FakeView as SecurityView

from wxclaude.core.claude.claude_settings import Approval, Source, ToolSettings
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.core.errors import ClaudeSettingsError
from wxclaude.presenters.security_presenter import (
    AlertChoice,
    ApprovalChoice,
    SecurityPresenter,
)
from wxclaude.presenters.workspace_settings_presenter import (
    WorkspaceEdit,
    WorkspaceSettingsLinks,
    WorkspaceSettingsPresenter,
)

pytestmark = pytest.mark.unit

ALTERNATIVE = Agent(model="haiku", effort="low", permission_mode="manual")
CHOSEN = Agent(model="sonnet", effort="medium", permission_mode="plan")
LOCAL = ".claude/settings.local.json"


class SpySecurity(SecurityPresenter):
    """The real presenter of the trust, that tells when it is asked to check the files."""

    def __init__(self, events: list[str], view: SecurityView) -> None:
        super().__init__(view)
        self._events = events

    def check(self) -> None:
        self._events.append("check")
        super().check()


class FakeView:
    """The dialog: ``act`` plays what the user does in it, then the dialog is validated (or not)."""

    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.result: WorkspaceEdit | None = WorkspaceEdit(None)
        self.act: Callable[[ToolSettings], None] = lambda tool_settings: None
        self.shown: list[tuple[ToolSettings, Path, Agent, bool]] = []
        self.errors: list[str] = []

    def edit(
        self,
        tool_settings: ToolSettings,
        workspace: Path,
        alternative_agent: Agent,
        *,
        local_only: bool,
    ) -> WorkspaceEdit | None:
        self._events.append("edit")
        self.shown.append((tool_settings, workspace, alternative_agent, local_only))
        self.act(tool_settings)
        return self.result

    def show_error(self, message: str) -> None:
        self.errors.append(message)


class Setup:
    """A presenter on a workspace (or on none), with its fake dialog and its trust state."""

    def __init__(self, tmp_path: Path, *, with_workspace: bool = True) -> None:
        self.workspace = tmp_path / "work"
        self.data = tmp_path / "data"  # what WxClaude remembers of the workspace
        (self.workspace / ".claude").mkdir(parents=True)
        self.events: list[str] = []
        self.chosen: list[Agent] = []
        self.settings = Settings.load(None)
        self.view = FakeView(self.events)
        self.security_view = SecurityView(approval=ApprovalChoice.APPROVE, alert=AlertChoice.ACCEPT)
        self.security = SpySecurity(self.events, self.security_view)
        self.presenter = WorkspaceSettingsPresenter(
            self.view,
            self.settings,
            self.security,
            WorkspaceSettingsLinks(
                workspace=lambda: self.workspace if with_workspace else None,
                alternative_agent=lambda: ALTERNATIVE,
                set_alternative_agent=self.chosen.append,
            ),
        )

    def approve_the_folder(self) -> None:
        """The folder is trusted, its settings files as they are now being the reference."""
        state = WorkspaceState.load(self.workspace, self.data)
        self.security.open(self.workspace, state)
        self.security.greet()


def test_without_a_workspace_nothing_is_opened(tmp_path: Path) -> None:
    setup = Setup(tmp_path, with_workspace=False)
    setup.presenter.edit()
    assert setup.events == []
    assert setup.view.shown == []


def test_the_files_are_checked_before_the_dialog_opens(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.presenter.edit()
    assert setup.events == ["check", "edit"]


@pytest.mark.parametrize("local_only", [False, True])
def test_the_dialog_gets_the_workspace_its_alternative_agent_and_the_local_only_setting(
    tmp_path: Path, local_only: bool
) -> None:
    setup = Setup(tmp_path)
    setup.settings.local_tools_only = local_only
    setup.presenter.edit()
    ((tool_settings, workspace, agent, shown_local_only),) = setup.view.shown
    assert isinstance(tool_settings, ToolSettings)
    assert (workspace, agent, shown_local_only) == (setup.workspace, ALTERNATIVE, local_only)


def test_the_rules_edited_in_the_dialog_are_written_when_it_is_validated(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.view.act = lambda tool_settings: tool_settings.set_approval(
        Source.SETTINGS, "PowerShell", Approval.DENY
    )
    setup.presenter.edit()
    shared = setup.workspace / ".claude" / "settings.json"
    assert json.loads(shared.read_text(encoding="utf-8")) == {
        "permissions": {"deny": ["PowerShell"]}
    }
    assert setup.view.errors == []


def test_a_cancelled_dialog_writes_nothing_and_changes_no_agent(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.view.result = None
    setup.view.act = lambda tool_settings: tool_settings.set_approval(
        Source.SETTINGS, "Bash", Approval.ASK
    )
    setup.presenter.edit()
    assert not (setup.workspace / ".claude" / "settings.json").exists()
    assert setup.chosen == []


def test_the_alternative_agent_of_the_dialog_is_kept(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.view.result = WorkspaceEdit(CHOSEN)
    setup.presenter.edit()
    assert setup.chosen == [CHOSEN]


def test_a_dialog_without_the_alternative_agent_leaves_it_as_it_is(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.presenter.edit()  # the default result has no agent
    assert setup.chosen == []


def test_rules_that_cannot_be_written_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(self: ToolSettings) -> list[Path]:
        raise ClaudeSettingsError("The disk is full")

    monkeypatch.setattr(ToolSettings, "save", fail)
    setup = Setup(tmp_path)
    setup.view.result = WorkspaceEdit(CHOSEN)
    setup.presenter.edit()
    assert setup.view.errors == ["The settings could not be saved.\nThe disk is full"]
    assert setup.chosen == [CHOSEN]  # the agent is the business of WxClaude, not of that file
    assert setup.security_view.alerts == []


def test_a_file_changed_from_outside_is_given_to_the_user_and_the_failure_is_said(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path)
    setup.approve_the_folder()

    def act(tool_settings: ToolSettings) -> None:
        tool_settings.set_approval(Source.LOCAL, "Bash", Approval.ALLOW)
        # another program writes the file while the dialog is open
        (setup.workspace / LOCAL).write_text('{"outside": 1}', encoding="utf-8")

    setup.view.act = act
    setup.presenter.edit()
    (alert,) = setup.security_view.alerts
    assert alert.lines == [f"{LOCAL}, added"]
    assert setup.view.errors == [
        f"The settings could not be saved.\n{LOCAL} changed since you approved it and was not "
        "modified."
    ]
    assert json.loads((setup.workspace / LOCAL).read_text(encoding="utf-8")) == {"outside": 1}

"""The tabs Environment variables and Security of the Workspace settings (real controls)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import wx
from fake_security_view import FakeView as SecurityView

from wxclaude.core.claude.claude_settings import Approval, Source, ToolSettings
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.presenters.security_presenter import ApprovalChoice, SecurityPresenter
from wxclaude.ui.agent_panel import AgentPanel
from wxclaude.ui.env_vars_page import EnvVarsPage
from wxclaude.ui.security_page import SecurityPage
from wxclaude.ui.workspace_settings_dialog import WorkspaceSettingsDialog

pytestmark = pytest.mark.ui


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    folder = tmp_path / "work"
    (folder / ".claude").mkdir(parents=True)
    (folder / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    return folder


def open_dialog(
    workspace: Path,
    *,
    with_security: bool,
    local_only: bool = False,
    alternative: Agent | None = None,
) -> WorkspaceSettingsDialog:
    settings = ToolSettings.load(workspace, workspace.parent / "config")
    security = None
    if with_security:
        security = SecurityPresenter(SecurityView(approval=ApprovalChoice.KEEP_RESTRICTED))
        security.open(workspace, WorkspaceState.load(workspace, workspace.parent / "data"))
        security.greet()
    return WorkspaceSettingsDialog(
        None,
        settings,
        local_only=local_only,
        security=security,
        workspace=workspace,
        alternative_agent=alternative,
    )


@pytest.fixture
def dialog(wx_app: wx.App, workspace: Path) -> Iterator[WorkspaceSettingsDialog]:
    window = open_dialog(workspace, with_security=True, alternative=Agent())
    yield window
    window.Destroy()
    wx.SafeYield()


def pages(window: WorkspaceSettingsDialog) -> list[str]:
    notebook = window._notebook
    return [notebook.GetPageText(i) for i in range(notebook.GetPageCount())]


def page(window: WorkspaceSettingsDialog, kind: type[wx.Panel]) -> wx.Panel:
    notebook = window._notebook
    return next(
        notebook.GetPage(i)
        for i in range(notebook.GetPageCount())
        if type(notebook.GetPage(i)) is kind
    )


def test_the_dialog_has_the_four_tabs(dialog: WorkspaceSettingsDialog) -> None:
    assert pages(dialog) == ["Tools", "Environment variables", "Security", "Alternative agent"]


def test_the_focus_is_on_the_first_tab(dialog: WorkspaceSettingsDialog) -> None:
    assert dialog.FindFocus() is dialog._notebook
    assert dialog._notebook.GetSelection() == 0


def test_the_alternative_agent_tab_shows_a_complete_agent_with_no_unset_entry(
    wx_app: wx.App, workspace: Path
) -> None:
    agent = Agent(provider="claude", model="haiku", effort="low", permission_mode="plan")
    window = open_dialog(workspace, with_security=False, alternative=agent)
    try:
        agent_panel = page(window, AgentPanel)
        assert isinstance(agent_panel, AgentPanel)
        assert window.alternative_agent == agent
        assert list(agent_panel._provider.GetStrings()) == ["Claude"]
        assert agent_panel._effort.GetString(0) == "Low"
        agent_panel._effort.SetSelection(2)
        assert window.alternative_agent == Agent(
            provider="claude", model="haiku", effort="high", permission_mode="plan"
        )
    finally:
        window.Destroy()
        wx.SafeYield()


def test_without_an_alternative_agent_there_is_no_such_tab(wx_app: wx.App, workspace: Path) -> None:
    window = open_dialog(workspace, with_security=False)
    try:
        assert pages(window) == ["Tools", "Environment variables"]
        assert window.alternative_agent is None
    finally:
        window.Destroy()
        wx.SafeYield()


def test_without_a_trust_state_there_is_no_security_tab(wx_app: wx.App, workspace: Path) -> None:
    window = open_dialog(workspace, with_security=False)
    try:
        assert pages(window) == ["Tools", "Environment variables"]
    finally:
        window.Destroy()
        wx.SafeYield()


def test_the_variables_are_listed_and_a_flag_is_enabled_in_memory(
    dialog: WorkspaceSettingsDialog,
) -> None:
    env = page(dialog, EnvVarsPage)
    assert isinstance(env, EnvVarsPage)
    lines = list(env._list.GetStrings())
    assert "CLAUDE_CODE_DISABLE_WEB_FETCH, not set" in lines
    env._list.SetSelection(lines.index("CLAUDE_CODE_DISABLE_WEB_FETCH, not set"))
    env.presenter.select(env._list.GetSelection())
    assert "WebFetch" in env._explanation.GetValue()
    assert env._toggle.GetLabel() == "&Enable"
    assert env._toggle.IsEnabled()
    env.confirm_versioned = lambda: True  # type: ignore[method-assign]
    env.presenter.toggle()
    assert "CLAUDE_CODE_DISABLE_WEB_FETCH, enabled" in env._list.GetStrings()
    assert env._toggle.GetLabel() == "&Disable"
    file = dialog.tool_settings.files[Source.SETTINGS]
    assert file.data == {"env": {"CLAUDE_CODE_DISABLE_WEB_FETCH": "1"}}
    assert file.changed  # written by the caller on OK, as for the tab Tools


def test_the_buttons_are_greyed_without_a_selection(dialog: WorkspaceSettingsDialog) -> None:
    env = page(dialog, EnvVarsPage)
    assert isinstance(env, EnvVarsPage)
    assert not env._toggle.IsEnabled()
    assert not env._set.IsEnabled()
    assert not env._remove.IsEnabled()
    assert env._explanation.GetValue() == ""


def test_with_the_preference_only_the_personal_file_is_offered(
    wx_app: wx.App, workspace: Path
) -> None:
    window = open_dialog(workspace, with_security=False, local_only=True)
    try:
        env = page(window, EnvVarsPage)
        assert isinstance(env, EnvVarsPage)
        assert list(env._target.GetStrings()) == ["SettingsLocal"]
    finally:
        window.Destroy()
        wx.SafeYield()


def test_the_security_tab_shows_the_state_and_approves(dialog: WorkspaceSettingsDialog) -> None:
    security = page(dialog, SecurityPage)
    assert isinstance(security, SecurityPage)
    assert not security._trusted.GetValue()
    assert ".claude/settings.json, added" in security._files.GetStrings()
    assert "Restricted folder" in security._explanation.GetValue()
    security.confirm_approval = lambda: True  # type: ignore[method-assign]
    security.presenter.set_trusted(True)
    assert security._trusted.GetValue()
    assert ".claude/settings.json, unchanged" in security._files.GetStrings()
    assert all(security._files.IsChecked(i) for i in range(security._files.GetCount()))


def test_a_file_is_unwatched_by_its_check_box(dialog: WorkspaceSettingsDialog) -> None:
    security = page(dialog, SecurityPage)
    assert isinstance(security, SecurityPage)
    security.confirm_approval = lambda: True  # type: ignore[method-assign]
    security.presenter.set_trusted(True)
    index = list(security._files.GetStrings()).index(".claude/settings.json, unchanged")
    security._files.Check(index, False)
    event = wx.CommandEvent(wx.EVT_CHECKLISTBOX.typeId, security._files.GetId())
    event.SetInt(index)
    security._on_check(event)
    assert ".claude/settings.json, unchanged, not watched" in security._files.GetStrings()
    assert not security._files.IsChecked(index)


def test_the_files_of_the_dialog_are_still_the_ones_of_the_tools_tab(
    dialog: WorkspaceSettingsDialog, workspace: Path
) -> None:
    # The tabs share one ToolSettings: what the tab Tools writes is kept with the variables.
    dialog.set_target(Source.LOCAL)
    dialog.add_rule("Bash", Approval.ALLOW)
    assert dialog.tool_settings.files[Source.LOCAL].data == {"permissions": {"allow": ["Bash"]}}

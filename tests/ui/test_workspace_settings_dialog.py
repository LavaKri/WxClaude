import json
from collections.abc import Iterator
from pathlib import Path

import pytest
import wx

from wxclaude.core.claude.claude_settings import Approval, Source, ToolSettings
from wxclaude.ui.workspace_settings_dialog import WorkspaceSettingsDialog

pytestmark = pytest.mark.ui


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "work"


def _dialog(workspace: Path, *, local_only: bool = False) -> WorkspaceSettingsDialog:
    settings = ToolSettings.load(workspace, workspace.parent / "config")
    return WorkspaceSettingsDialog(None, settings, local_only=local_only)


@pytest.fixture
def dialog(wx_app: wx.App, workspace: Path) -> Iterator[WorkspaceSettingsDialog]:
    dialog = _dialog(workspace)
    errors: list[str] = []
    dialog._show_error = errors.append  # type: ignore[assignment]
    dialog.errors = errors
    yield dialog
    dialog.Destroy()
    wx.SafeYield()


def _items(dialog: WorkspaceSettingsDialog) -> list[str]:
    return list(dialog._tools.GetStrings())


def test_the_target_files_and_the_initial_state(dialog: WorkspaceSettingsDialog) -> None:
    assert [dialog._target.GetString(i) for i in range(dialog._target.GetCount())] == [
        "Settings (shared, versioned)",
        "SettingsLocal (personal, not versioned)",
    ]
    assert dialog.target is Source.SETTINGS  # the versioned file by default
    assert "PowerShell" in _items(dialog)
    assert dialog._rules_list.GetCount() == 0
    note = dialog._note.GetValue()
    assert str(dialog.target_path) in note
    assert "versioned" in note
    assert "only read" in note


def test_local_only_proposes_the_personal_file_alone(wx_app: wx.App, workspace: Path) -> None:
    dialog = _dialog(workspace, local_only=True)
    try:
        assert dialog._target.GetCount() == 1
        assert dialog.target is Source.LOCAL
        assert "not versioned" in dialog._note.GetValue()
    finally:
        dialog.Destroy()
        wx.SafeYield()


def test_the_buttons_change_the_state_of_the_selected_tool(
    dialog: WorkspaceSettingsDialog,
) -> None:
    dialog.select_tool("PowerShell")
    dialog._deny.Command(wx.CommandEvent(wx.wxEVT_BUTTON))
    assert "PowerShell Deny" in _items(dialog)
    assert dialog.selected_tool == "PowerShell"  # the selection stays on the tool
    dialog.apply_approval(Approval.ASK)
    assert "PowerShell Ask" in _items(dialog)
    dialog.apply_approval(Approval.ALLOW)
    assert "PowerShell Allow" in _items(dialog)
    assert [dialog._rules_list.GetString(i) for i in range(dialog._rules_list.GetCount())] == [
        "Allow, PowerShell"
    ]


def test_the_state_follows_the_target_file(dialog: WorkspaceSettingsDialog) -> None:
    dialog.select_tool("Bash")
    dialog.apply_approval(Approval.DENY)
    dialog.set_target(Source.LOCAL)
    assert "Bash Deny by Settings" in _items(dialog)  # the value of the other file prevails
    assert dialog._rules_list.GetCount() == 0
    dialog.select_tool("Bash")
    dialog.apply_approval(Approval.ALLOW)
    assert "Bash Allow, Deny by Settings" in _items(dialog)


def test_rules_are_listed_sorted_and_can_be_removed(dialog: WorkspaceSettingsDialog) -> None:
    assert dialog.add_rule("Bash(git *)", Approval.ALLOW)
    assert dialog.add_rule("Bash(rm *)", Approval.DENY)
    assert dialog.add_rule("Edit", Approval.ASK)
    rules = [dialog._rules_list.GetString(i) for i in range(dialog._rules_list.GetCount())]
    assert rules == ["Deny, Bash(rm *)", "Allow, Bash(git *)", "Ask, Edit"]
    assert "Bash with rules" in _items(dialog)
    dialog.select_rule(0)
    dialog.remove_selected_rule()
    assert dialog._rules_list.GetCount() == 2
    assert dialog._rules_list.GetSelection() == 0  # the selection moves on
    assert "Bash with rules" in _items(dialog)


def test_an_empty_rule_is_refused_and_the_text_is_kept_when_it_fails(
    dialog: WorkspaceSettingsDialog,
) -> None:
    assert not dialog.add_rule("   ", Approval.ALLOW)
    assert dialog._rules_list.GetCount() == 0


def test_contradictory_rules_are_accepted(dialog: WorkspaceSettingsDialog) -> None:
    assert dialog.add_rule("Bash", Approval.ALLOW)
    assert dialog.add_rule("Bash", Approval.DENY)
    assert dialog._rules_list.GetCount() == 2


def test_a_damaged_file_disables_the_changes_and_says_why(wx_app: wx.App, workspace: Path) -> None:
    shared = workspace / ".claude" / "settings.json"
    shared.parent.mkdir(parents=True)
    shared.write_text("{ not json", encoding="utf-8")
    dialog = _dialog(workspace)
    try:
        assert "cannot be modified" in dialog._note.GetValue()
        assert not dialog._deny.IsEnabled()
        assert not dialog._add.IsEnabled()
        dialog.set_target(Source.LOCAL)
        assert dialog._add.IsEnabled()  # the other file is fine
    finally:
        dialog.Destroy()
        wx.SafeYield()


def test_the_new_rule_fields_add_through_the_button(dialog: WorkspaceSettingsDialog) -> None:
    dialog._new_rule.SetValue("WebFetch")
    dialog._new_approval.SetSelection(0)  # Deny
    dialog._on_add()
    assert dialog._rules_list.GetString(0) == "Deny, WebFetch"
    assert dialog._new_rule.GetValue() == ""

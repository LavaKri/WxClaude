"""Tests of the main window: permission questions of Claude and the Workspace settings."""

import json
from pathlib import Path

import pytest
import wx
from main_window_support import (
    _Errors,
    _send,
)

from wxclaude.core.announcements import RecordingMessageSink
from wxclaude.core.claude_settings import Approval, Source
from wxclaude.core.events import PermissionRequest
from wxclaude.core.permissions import DEFAULT_DENIAL, Choice, Decision
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.workspace_settings_dialog import WorkspaceSettingsDialog

pytestmark = pytest.mark.ui


def _permission_setup(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *decisions: Decision
) -> tuple[list[PermissionRequest], Path, RecordingMessageSink]:
    """Run the fake in its permission scenario; the user answers with ``decisions`` in turn."""
    monkeypatch.setenv("FAKE_CLAUDE", "permission")
    log = tmp_path / "permission-log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    asked: list[PermissionRequest] = []
    answers = list(decisions)

    def ask(request: PermissionRequest) -> Decision:
        asked.append(request)
        return answers.pop(0)

    monkeypatch.setattr(window._run, "_ask_permission", ask)
    sink = RecordingMessageSink()
    window._feedback.announcements.message_sink = sink
    return asked, log, sink


def _response(log: Path) -> dict[str, object]:
    text = Path(str(log) + ".responses").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]  # Windows adds line breaks
    return json.loads(lines[-1])["response"]["response"]


def test_allowing_a_permission_question_lets_the_tool_run(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked, log, sink = _permission_setup(
        conversation, monkeypatch, tmp_path, Decision(Choice.ALLOW)
    )
    _send(conversation, "hello")
    assert [request.tool_name for request in asked] == ["Bash"]
    assert _response(log)["behavior"] == "allow"
    assert "Permission granted for the tool Bash." in sink.messages
    assert not (tmp_path / ".claude" / "settings.local.json").exists()
    assert "Echo: hello" in conversation._conversation.GetValue()


def test_denying_with_an_explanation_tells_claude(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision = Decision(Choice.DENY, "Not in this folder")
    asked, log, sink = _permission_setup(conversation, monkeypatch, tmp_path, decision)
    _send(conversation, "hello")
    assert len(asked) == 1
    assert _response(log) == {"behavior": "deny", "message": "Not in this folder"}
    assert "Permission refused for the tool Bash." in sink.messages


def test_a_denial_without_explanation_has_a_default_message(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _asked, log, _sink = _permission_setup(
        conversation, monkeypatch, tmp_path, Decision(Choice.DENY)
    )
    _send(conversation, "hello")
    assert _response(log) == {"behavior": "deny", "message": DEFAULT_DENIAL}


def _local_file(workspace: Path) -> Path:
    return workspace / ".claude" / "settings.local.json"


def test_always_allow_writes_the_personal_settings_file_of_the_workspace(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked, _log, _sink = _permission_setup(
        conversation, monkeypatch, tmp_path, Decision(Choice.ALLOW_ALWAYS)
    )
    _send(conversation, "first")
    settings = json.loads(_local_file(tmp_path).read_text(encoding="utf-8"))
    assert settings == {"permissions": {"allow": ["Bash(touch fake.txt)"]}}
    _send(conversation, "second")  # the CLI reads the file, so it does not ask again
    assert len(asked) == 1


def test_always_allow_keeps_the_other_keys_of_the_file(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _local_file(tmp_path).parent.mkdir()
    _local_file(tmp_path).write_text('{"model": "opus", "permissions": {"deny": ["X"]}}')
    _permission_setup(conversation, monkeypatch, tmp_path, Decision(Choice.ALLOW_ALWAYS))
    _send(conversation, "first")
    settings = json.loads(_local_file(tmp_path).read_text(encoding="utf-8"))
    assert settings["model"] == "opus"
    assert settings["permissions"] == {"deny": ["X"], "allow": ["Bash(touch fake.txt)"]}


def test_an_unreadable_settings_file_is_reported_and_left_alone(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _local_file(tmp_path).parent.mkdir()
    _local_file(tmp_path).write_text("{ not json", encoding="utf-8")
    _permission_setup(conversation, monkeypatch, tmp_path, Decision(Choice.ALLOW_ALWAYS))
    errors = _Errors(conversation)
    _send(conversation, "first")
    assert any("could not be saved" in message for message in errors.messages)
    assert _local_file(tmp_path).read_text(encoding="utf-8") == "{ not json"


def test_a_rule_allowed_earlier_in_the_message_is_answered_without_a_question(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked, _log, _sink = _permission_setup(conversation, monkeypatch, tmp_path)
    request = PermissionRequest("r", "Bash", "t", {}, "", "", "Bash(touch fake.txt)")
    conversation._run._turn_allowed.add(request.suggested_rule)
    answers: list[PermissionRequest] = []
    monkeypatch.setattr(conversation._run.runner, "allow", answers.append)
    conversation._run._on_permission_request(request)
    assert answers == [request]
    assert asked == []


def _workspace_settings_edit(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, edit, *, result: int = wx.ID_OK
) -> list[WorkspaceSettingsDialog]:
    """Open the workspace settings; ``edit(dialog)`` plays what the user does, then OK/Cancel."""
    seen: list[WorkspaceSettingsDialog] = []

    def modal(dialog: wx.Dialog) -> int:
        assert isinstance(dialog, WorkspaceSettingsDialog)
        seen.append(dialog)
        edit(dialog)
        return result

    monkeypatch.setattr(window._feedback, "modal", modal)
    window._on_workspace_settings(wx.CommandEvent())
    return seen


def test_workspace_settings_deny_a_tool_in_the_shared_file(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink

    def edit(dialog: WorkspaceSettingsDialog) -> None:
        assert dialog.target is Source.SETTINGS  # the versioned file is the default
        dialog.select_tool("PowerShell")
        dialog.apply_approval(Approval.DENY)

    _workspace_settings_edit(conversation, monkeypatch, edit)
    shared = tmp_path / ".claude" / "settings.json"
    assert json.loads(shared.read_text(encoding="utf-8")) == {
        "permissions": {"deny": ["PowerShell"]}
    }
    assert not _local_file(tmp_path).exists()
    assert sink.messages[-1] == "Workspace settings saved."


def test_workspace_settings_cancelled_write_nothing(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def edit(dialog: WorkspaceSettingsDialog) -> None:
        dialog.select_tool("Bash")
        dialog.apply_approval(Approval.ASK)

    _workspace_settings_edit(conversation, monkeypatch, edit, result=wx.ID_CANCEL)
    assert not (tmp_path / ".claude").exists()


def test_local_tools_only_limits_the_target_file(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversation._settings.local_tools_only = True

    def edit(dialog: WorkspaceSettingsDialog) -> None:
        assert dialog.target is Source.LOCAL
        assert dialog._target.GetCount() == 1
        dialog.select_tool("Bash")
        dialog.apply_approval(Approval.ALLOW)

    _workspace_settings_edit(conversation, monkeypatch, edit)
    assert not (tmp_path / ".claude" / "settings.json").exists()
    assert (
        "Bash"
        in json.loads(_local_file(tmp_path).read_text(encoding="utf-8"))["permissions"]["allow"]
    )


def test_the_workspace_settings_item_needs_a_workspace(window: MainWindow) -> None:
    item = next(
        item
        for item in window._menu.needs_workspace
        if item.GetItemLabel() == "Workspace &settings…"
    )
    assert not item.IsEnabled()

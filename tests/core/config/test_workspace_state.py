import json
from pathlib import Path

import pytest

from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspace_state import WorkspaceState, state_file_name
from wxclaude.core.conversation.conversations import new_conversation_id

pytestmark = pytest.mark.unit


def test_the_file_name_is_a_small_hash_of_the_lower_case_path(tmp_path: Path) -> None:
    name = state_file_name(tmp_path / "Work")
    assert name == state_file_name(tmp_path / "WORK")
    assert name != state_file_name(tmp_path / "other")
    stem, suffix = name.split(".")
    assert suffix == "json"
    assert len(stem) == 16
    int(stem, 16)


def test_round_trip(tmp_path: Path) -> None:
    work = tmp_path / "work"
    identifier = new_conversation_id()
    agent = Agent(model="opus", effort="high", permission_mode="plan")
    state = WorkspaceState.load(work, tmp_path / "workspaces")
    state.remember(identifier, "Notes", agent)
    state.save()
    loaded = WorkspaceState.load(work, tmp_path / "workspaces")
    assert loaded.current_conversation == identifier
    assert loaded.conversations[identifier].name == "Notes"
    assert loaded.conversations[identifier].agent == agent
    assert loaded.warning == ""


def test_without_a_directory_the_state_stays_in_memory(tmp_path: Path) -> None:
    state = WorkspaceState.load(tmp_path, None)
    state.remember(new_conversation_id(), "Notes", Agent())
    state.save()
    assert list(tmp_path.iterdir()) == []


def test_a_file_of_another_workspace_is_not_used(tmp_path: Path) -> None:
    directory = tmp_path / "workspaces"
    work = tmp_path / "work"
    state = WorkspaceState.load(work, directory)
    state.remember(new_conversation_id(), "Notes", Agent())
    state.save()
    assert state.store is not None
    data = json.loads(state.store.read_text(encoding="utf-8"))
    data["workspace"] = str(tmp_path / "somewhere else")
    state.store.write_text(json.dumps(data), encoding="utf-8")
    loaded = WorkspaceState.load(work, directory)
    assert loaded.conversations == {}
    assert "another workspace" in loaded.warning


def test_missing_conversations_are_forgotten(tmp_path: Path) -> None:
    kept, gone = new_conversation_id(), new_conversation_id()
    state = WorkspaceState.load(tmp_path, None)
    state.remember(kept, "Kept", Agent())
    state.remember(gone, "Gone", Agent())
    state.forget_missing({kept})
    assert list(state.conversations) == [kept]
    assert state.current_conversation == ""

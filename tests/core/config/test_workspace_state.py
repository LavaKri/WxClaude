import json
from pathlib import Path

import pytest

from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspace_state import WatchRecord, WorkspaceState, state_file_name
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
    state.remember(identifier, agent)
    state.save()
    loaded = WorkspaceState.load(work, tmp_path / "workspaces")
    assert loaded.current_conversation == identifier
    assert loaded.conversations[identifier].agent == agent
    assert loaded.warning == ""


def test_without_a_directory_the_state_stays_in_memory(tmp_path: Path) -> None:
    state = WorkspaceState.load(tmp_path, None)
    state.remember(new_conversation_id(), Agent())
    state.save()
    assert list(tmp_path.iterdir()) == []


def test_a_file_of_another_workspace_is_not_used(tmp_path: Path) -> None:
    directory = tmp_path / "workspaces"
    work = tmp_path / "work"
    state = WorkspaceState.load(work, directory)
    state.remember(new_conversation_id(), Agent())
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
    state.remember(kept, Agent())
    state.remember(gone, Agent())
    state.forget_missing({kept})
    assert list(state.conversations) == [kept]
    assert state.current_conversation == ""


def test_a_name_in_an_older_file_is_ignored(tmp_path: Path) -> None:
    work = tmp_path / "work"
    identifier = new_conversation_id()
    state = WorkspaceState.load(work, tmp_path / "workspaces")
    state.remember(identifier, Agent(model="opus"))
    state.save()
    assert state.store is not None
    data = json.loads(state.store.read_text(encoding="utf-8"))
    data["conversations"][identifier]["name"] = "Old name"  # the names now belong to the CLI
    state.store.write_text(json.dumps(data), encoding="utf-8")
    loaded = WorkspaceState.load(work, tmp_path / "workspaces")
    assert loaded.conversations[identifier].agent == Agent(model="opus")
    loaded.save()
    assert (
        "name"
        not in json.loads(state.store.read_text(encoding="utf-8"))["conversations"][identifier]
    )


def test_trust_and_watch_records_round_trip(tmp_path: Path) -> None:
    work = tmp_path / "work"
    state = WorkspaceState.load(work, tmp_path / "workspaces")
    assert not state.trusted
    assert state.watch == {}
    state.trusted = True
    state.watch[".mcp.json"] = WatchRecord(watched=False, sha256="ab12")
    state.watch[".claude/settings.json"] = WatchRecord()
    state.save()
    loaded = WorkspaceState.load(work, tmp_path / "workspaces")
    assert loaded.trusted
    assert loaded.watch == {
        ".mcp.json": WatchRecord(watched=False, sha256="ab12"),
        ".claude/settings.json": WatchRecord(watched=True, sha256=""),
    }


def test_the_alternative_agent_of_the_workspace_round_trips(tmp_path: Path) -> None:
    work = tmp_path / "work"
    state = WorkspaceState.load(work, tmp_path / "workspaces")
    assert state.alternative_agent == Agent()
    state.alternative_agent = Agent(provider="deepseek", model="deepseek-chat", effort="low")
    state.save()
    loaded = WorkspaceState.load(work, tmp_path / "workspaces")
    assert loaded.alternative_agent == Agent(
        provider="deepseek", model="deepseek-chat", effort="low"
    )


def test_the_alternative_agent_starts_from_the_preferences_then_the_conversation() -> None:
    state = WorkspaceState(Path("work"))
    state.start_alternative_agent(
        Agent(provider="deepseek", model="flash", effort="low"),
        Agent(provider="claude", model="sonnet", effort="high", permission_mode="plan"),
    )
    assert state.alternative_agent == Agent(
        provider="deepseek", model="flash", effort="low", permission_mode="plan"
    )


def test_an_alternative_agent_that_is_set_is_kept() -> None:
    state = WorkspaceState(Path("work"))
    mine = Agent(provider="claude", model="opus", effort="max", permission_mode="auto")
    state.alternative_agent = mine
    state.start_alternative_agent(Agent(model="haiku"), Agent(provider="deepseek", effort="low"))
    assert state.alternative_agent == mine


def test_a_file_without_an_alternative_agent_is_still_read(tmp_path: Path) -> None:
    work = tmp_path / "work"
    state = WorkspaceState.load(work, tmp_path / "workspaces")
    state.save()
    assert state.store is not None
    data = json.loads(state.store.read_text(encoding="utf-8"))
    del data["alternative_agent"]
    state.store.write_text(json.dumps(data), encoding="utf-8")
    assert WorkspaceState.load(work, tmp_path / "workspaces").alternative_agent == Agent()


def test_a_file_without_trust_or_watch_is_still_read(tmp_path: Path) -> None:
    work = tmp_path / "work"
    state = WorkspaceState.load(work, tmp_path / "workspaces")
    state.remember(new_conversation_id(), Agent(model="opus"))
    state.save()
    assert state.store is not None
    data = json.loads(state.store.read_text(encoding="utf-8"))
    del data["trusted"], data["watch"]
    state.store.write_text(json.dumps(data), encoding="utf-8")
    loaded = WorkspaceState.load(work, tmp_path / "workspaces")
    assert not loaded.trusted
    assert loaded.watch == {}
    assert len(loaded.conversations) == 1


def test_a_watch_entry_that_is_not_well_formed_is_left_out(tmp_path: Path) -> None:
    work = tmp_path / "work"
    state = WorkspaceState.load(work, tmp_path / "workspaces")
    state.save()
    assert state.store is not None
    data = json.loads(state.store.read_text(encoding="utf-8"))
    data["trusted"] = "yes"
    data["watch"] = {"a": "text", "b": {"sha256": 3}, "c": {"sha256": "ff"}}
    state.store.write_text(json.dumps(data), encoding="utf-8")
    loaded = WorkspaceState.load(work, tmp_path / "workspaces")
    assert not loaded.trusted
    assert loaded.watch == {"c": WatchRecord(watched=True, sha256="ff")}


def test_the_copies_of_the_watched_files_go_beside_the_state_file(tmp_path: Path) -> None:
    state = WorkspaceState.load(tmp_path / "work", tmp_path / "workspaces")
    assert state.store is not None
    assert state.watch_dir == state.store.with_name(state.store.stem + ".watch")
    assert WorkspaceState.load(tmp_path / "work", None).watch_dir is None

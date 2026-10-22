"""The presenter of the current conversation, with a fake window: no wx, no window."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from wxclaude.core.agents import Agent
from wxclaude.core.announcements import Announce
from wxclaude.core.messages import Message
from wxclaude.core.settings import Settings
from wxclaude.core.usage import UsageTracker
from wxclaude.presenters.conversation_presenter import ConversationPresenter
from wxclaude.presenters.workspace_presenter import WorkspaceLinks, WorkspacePresenter

pytestmark = pytest.mark.unit


class FakeScreen:
    """Records what the window would show; answers the questions with what the test set."""

    def __init__(self) -> None:
        self.name: str | None = None
        self.agent: Agent | None = None
        self.index: int | None = None
        self.messages: list[Message] = []
        self.title = ""
        self.said: list[Announce] = []
        self.errors: list[str] = []
        self.calls: list[str] = []

    def ask_name(self, title: str, proposal: str) -> str | None:
        self.calls.append(f"ask {proposal}")
        return self.name

    def ask_agent(self, agent: Agent) -> Agent | None:
        return self.agent

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        self.calls.append(f"choose {len(labels)}")
        return self.index

    def show_messages(self, messages: list[Message]) -> None:
        self.messages = list(messages)

    def clear_messages(self) -> None:
        self.messages = []

    def shown_count(self) -> int:
        return len(self.messages)

    def focus_last_prompt(self) -> None:
        self.calls.append("focus view")

    def clear_prompt(self) -> None:
        self.calls.append("clear prompt")

    def focus_prompt(self) -> None:
        self.calls.append("focus prompt")

    def show_title(self, title: str) -> None:
        self.title = title

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append(announce)

    def show_error(self, message: str) -> None:
        self.errors.append(message)


class FakeWorkspaceView:
    def choose_folder(self, default: Path | None) -> Path | None:
        return None

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        return None

    def show_error(self, message: str) -> None:
        raise AssertionError(message)

    def show_file_warning(self, details: str) -> None:
        raise AssertionError(details)


@pytest.fixture(autouse=True)
def claude_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "claude-config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    return folder


def _session(claude_config: Path, workspace: Path, identifier: str, prompt: str) -> None:
    folder = claude_config / "projects" / "folder"
    folder.mkdir(parents=True, exist_ok=True)
    entry = {
        "type": "user",
        "cwd": str(workspace),
        "uuid": f"u-{identifier}",
        "timestamp": datetime.now(UTC).isoformat(),
        "message": {"role": "user", "content": prompt},
    }
    (folder / f"{identifier}.jsonl").write_text(json.dumps(entry), encoding="utf-8")


def _presenters(
    tmp_path: Path,
) -> tuple[ConversationPresenter, FakeScreen, WorkspacePresenter, Settings]:
    settings = Settings.load(tmp_path / "config" / "settings.json")
    screen = FakeScreen()
    holder: list[ConversationPresenter] = []
    links = WorkspaceLinks(
        close_conversation=lambda: holder[0].close(),
        select_conversation=lambda folder: holder[0].select_in_workspace(folder),
        changed=lambda: holder[0].update_title(),
        save_settings=lambda: None,
    )
    workspaces = WorkspacePresenter(FakeWorkspaceView(), settings, links)
    conversations = ConversationPresenter(
        screen, settings, workspaces, UsageTracker(), lambda: None
    )
    holder.append(conversations)
    return conversations, screen, workspaces, settings


def test_a_workspace_without_conversation_says_so_and_creates_none(tmp_path: Path) -> None:
    conversations, screen, workspaces, _settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    assert conversations.conversation_id == ""
    assert screen.said == [Announce.NO_CONVERSATION]
    assert screen.title == f"{tmp_path.name} - WxClaude"


def test_a_new_conversation_takes_the_proposed_name_and_the_default_agent(
    tmp_path: Path,
) -> None:
    conversations, screen, workspaces, settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    screen.name = "Notes"
    conversations.agent = Agent(model="opus")
    conversations.new()
    assert conversations.conversation_id
    assert conversations.agent == settings.default_agent
    assert settings.conversation_counter == 2
    assert screen.title == f"Notes - {tmp_path.name} - WxClaude"
    assert screen.calls[-1] == "focus prompt"
    assert workspaces.state is not None
    assert workspaces.state.current_conversation == conversations.conversation_id


def test_a_cancelled_name_changes_nothing(tmp_path: Path) -> None:
    conversations, _screen, workspaces, settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    conversations.new()
    conversations.rename()
    assert conversations.conversation_id == ""
    assert settings.conversation_counter == 1


def test_the_most_recent_conversation_is_selected_and_refreshed(
    tmp_path: Path, claude_config: Path
) -> None:
    identifier = "d278c1fc-1d73-4c16-a899-5bdb1831fe5c"
    _session(claude_config, tmp_path, identifier, "Hello")
    conversations, screen, workspaces, _settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    assert conversations.conversation_id == identifier
    assert [message.text for message in screen.messages] == ["Hello"]
    conversations.refresh()
    assert screen.said[-1] is Announce.CONVERSATION_REFRESHED


def test_resume_lists_the_conversations_of_the_workspace(
    tmp_path: Path, claude_config: Path
) -> None:
    conversations, screen, workspaces, _settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    conversations.resume()
    assert screen.errors == ["This workspace has no conversation yet."]
    _session(claude_config, tmp_path, "aaaaaaaa-1d73-4c16-a899-5bdb1831fe5c", "One")
    screen.index = 0
    conversations.resume()
    assert screen.calls[-2:] == ["clear prompt", "focus view"]
    assert conversations.conversation_id.startswith("aaaaaaaa")


def test_a_branch_proposes_a_numbered_name_and_starts_a_new_identifier(tmp_path: Path) -> None:
    conversations, screen, workspaces, _settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    conversations.start_new("Notes")
    first = conversations.conversation_id
    screen.name = "Notes, branch"
    conversations.new_branch()
    assert screen.calls[-1].startswith("ask Notes")
    assert conversations.conversation_id != first
    assert conversations.name == "Notes, branch"


def test_the_agent_is_remembered_and_the_alternative_one_goes_over_it(tmp_path: Path) -> None:
    conversations, screen, workspaces, settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    conversations.start_new("Notes")
    screen.agent = Agent(model="haiku", effort="low", permission_mode="plan")
    conversations.choose_agent()
    assert workspaces.state is not None
    record = workspaces.state.conversations[conversations.conversation_id]
    assert record.agent == screen.agent
    settings.alternative_agent = Agent(effort="max")
    assert conversations.agent_for(alternative=True).effort == "max"
    assert conversations.agent_for(alternative=True).model == "haiku"

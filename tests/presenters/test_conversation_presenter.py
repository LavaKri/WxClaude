"""The presenter of the current conversation, with a fake window: no wx, no window."""

from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.conversation.messages import Message
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.conversation_presenter import ConversationLinks, ConversationPresenter
from wxclaude.presenters.shared import Shared
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


def _presenters(
    tmp_path: Path, files: FakeClaudeFiles | None = None, busy: list[bool] | None = None
) -> tuple[ConversationPresenter, FakeScreen, WorkspacePresenter, Settings]:
    files = files or FakeClaudeFiles()
    settings = Settings.load(tmp_path / "config" / "settings.json")
    screen = FakeScreen()
    holder: list[ConversationPresenter] = []
    links = WorkspaceLinks(
        close_conversation=lambda: holder[0].close(),
        select_conversation=lambda folder: holder[0].select_in_workspace(folder),
        changed=lambda: holder[0].update_title(),
        save_settings=lambda: None,
    )
    workspaces = WorkspacePresenter(FakeWorkspaceView(), settings, links, files)
    shared = Shared(settings, UsageTracker(), files)
    window = ConversationLinks(state_changed=lambda: None, is_busy=lambda: bool(busy))
    conversations = ConversationPresenter(screen, shared, workspaces, window)
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


def test_the_most_recent_conversation_is_selected_and_refreshed(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "older", "Before")
    identifier = files.add_session(tmp_path, "newer", "Hello").id
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    assert conversations.conversation_id == identifier
    assert [message.text for message in screen.messages] == ["Hello"]
    conversations.refresh()
    assert screen.said[-1] is Announce.CONVERSATION_REFRESHED


def test_resume_lists_the_conversations_of_the_workspace(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    conversations.resume()
    assert screen.errors == ["This workspace has no conversation yet."]
    files.add_session(tmp_path, "one", "One")
    files.add_session(tmp_path, "two", "Two")
    screen.index = 1  # the list is the most recent first: "one"
    conversations.resume()
    assert screen.calls[-2:] == ["clear prompt", "focus view"]
    assert conversations.conversation_id == "one"


def test_a_session_that_cannot_be_read_is_reported(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    info = files.add_session(tmp_path, "broken", "x")
    del files.contents[info.path]
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    assert conversations.conversation_id == ""
    assert screen.errors == ["Cannot read the conversation.\nCannot read broken.jsonl"]


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


def test_the_name_of_a_conversation_is_the_title_of_its_session(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "d278c1fc-1d73", "Hello", title="My notes")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    assert conversations.name == "My notes"
    assert screen.title == f"My notes - {tmp_path.name} - WxClaude"


def test_a_session_without_a_title_is_named_by_the_start_of_its_identifier(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "d278c1fc-1d73", "Hello")
    conversations, _screen, workspaces, settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    assert conversations.name == "d278c1fc"
    assert settings.conversation_counter == 1  # opening a conversation uses no number


def test_a_conversation_with_a_session_is_renamed_by_the_cli(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "one", "Hello", title="Before")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    screen.name = "After"
    conversations.rename()
    assert files.renamed == [("one", "After")]
    assert conversations.name == "After"
    assert screen.title == f"After - {tmp_path.name} - WxClaude"


def test_a_conversation_without_a_session_is_only_named_here(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    conversations.start_new("Notes")
    screen.name = "Other"
    conversations.rename()  # no session yet: the first message gives the name to the CLI
    assert files.renamed == []
    assert conversations.name == "Other"


def test_a_rename_that_fails_keeps_the_name_and_says_why(tmp_path: Path) -> None:
    files = FakeClaudeFiles(rename_error="No such session")
    files.add_session(tmp_path, "one", "Hello", title="Before")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    screen.name = "After"
    conversations.rename()
    assert conversations.name == "Before"
    assert screen.errors == ["The conversation could not be renamed.\nNo such session"]


def test_a_conversation_is_not_renamed_while_claude_answers(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "one", "Hello", title="Before")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files, busy=[True])
    workspaces.open(tmp_path)
    screen.name = "After"
    conversations.rename()
    assert files.renamed == []
    assert conversations.name == "Before"
    assert screen.errors == ["Wait for Claude to finish before renaming the conversation."]
    assert not any(call.startswith("ask") for call in screen.calls)


def test_refreshing_takes_a_name_given_elsewhere(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    info = files.add_session(tmp_path, "one", "Hello", title="Before")
    conversations, _screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    files.contents[info.path].title = "Renamed in the CLI"
    conversations.refresh()
    assert conversations.name == "Renamed in the CLI"

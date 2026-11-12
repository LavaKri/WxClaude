"""The presenter of the current conversation, with a fake window: no wx, no window."""

from collections.abc import Callable
from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.config.workspace_state import WorkspaceState
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
        self.status = ""
        self.said: list[Announce] = []
        self.errors: list[str] = []
        self.calls: list[str] = []
        self.confirmed = True  # the answer to a Yes / No question
        self.recycle_works = True
        self.recycled: list[Path] = []

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

    def set_status(self, text: str) -> None:
        self.status = text

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def confirm(self, title: str, message: str) -> bool:
        self.calls.append(f"confirm {message}")
        return self.confirmed

    def move_to_recycle_bin(self, paths: list[Path]) -> bool:
        if self.recycle_works:
            self.recycled.extend(paths)
        return self.recycle_works


class FakeWorkspaceView:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def choose_folder(self, default: Path | None) -> Path | None:
        return None

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        return None

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def show_file_warning(self, details: str) -> None:
        raise AssertionError(details)


def _presenters(
    tmp_path: Path,
    files: FakeClaudeFiles | None = None,
    busy: list[bool] | None = None,
    entered: list[str] | None = None,
    start: Callable[[str, Agent], bool] = lambda text, agent: True,
) -> tuple[ConversationPresenter, FakeScreen, WorkspacePresenter, Settings]:
    """``entered`` collects the workspaces and conversations that became the current one;
    ``start`` is what starting Claude on a message does."""
    files = files or FakeClaudeFiles()
    settings = Settings.load(tmp_path / "config" / "settings.json")
    screen = FakeScreen()
    holder: list[ConversationPresenter] = []
    log = entered if entered is not None else []
    links = WorkspaceLinks(
        close_conversation=lambda: holder[0].close(),
        select_conversation=lambda folder: holder[0].select_in_workspace(folder),
        changed=lambda: holder[0].update_title(),
        save_settings=lambda: None,
        entered=lambda name: log.append(f"workspace {name}"),
    )
    workspaces = WorkspacePresenter(FakeWorkspaceView(), settings, links, files)
    shared = Shared(settings, UsageTracker(), files)
    window = ConversationLinks(
        state_changed=lambda: None,
        is_busy=lambda: bool(busy),
        start=start,
        entered=lambda name: log.append(f"conversation {name}"),
    )
    conversations = ConversationPresenter(screen, shared, workspaces, window)
    holder.append(conversations)
    return conversations, screen, workspaces, settings


def test_a_new_workspace_then_its_conversation_are_told_in_that_order(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "one", "Hello", title="Fix")
    entered: list[str] = []
    _conversations, _screen, workspaces, _settings = _presenters(tmp_path, files, entered=entered)
    workspaces.open(tmp_path)
    assert entered == [f"workspace {tmp_path.name}", "conversation Fix"]


def test_the_same_workspace_or_conversation_again_is_not_a_change(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "one", "Hello", title="Fix")
    entered: list[str] = []
    conversations, _screen, workspaces, _settings = _presenters(tmp_path, files, entered=entered)
    workspaces.open(tmp_path)
    workspaces.open(tmp_path)  # already the current one
    conversations.refresh()  # the same conversation read again
    assert entered == [f"workspace {tmp_path.name}", "conversation Fix"]


def test_a_new_conversation_is_told(tmp_path: Path) -> None:
    entered: list[str] = []
    conversations, _screen, workspaces, _settings = _presenters(tmp_path, entered=entered)
    workspaces.open(tmp_path)
    conversations.start_new("Notes")
    assert entered[-1] == "conversation Notes"


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
    # It was also left out of the statistics of the workspace, which said so.
    assert workspaces._view.errors == [  # type: ignore[attr-defined]
        "1 conversation could not be read and is not in the statistics."
    ]


def test_a_branch_keeps_the_text_and_copies_the_history_with_its_first_message(
    tmp_path: Path,
) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "parent", "Hello", title="Notes")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    screen.name = "Notes, other way"
    conversations.new_branch()
    assert screen.calls[-2:] == ["ask Notes branch 1", "focus view"]
    assert conversations.conversation_id not in ("", "parent")
    assert (conversations.name, conversations.fork_from) == ("Notes, other way", "parent")
    assert [message.text for message in screen.messages] == ["Hello"]  # the text stays
    assert screen.title == f"Notes, other way - {tmp_path.name} - WxClaude"


def test_what_the_cli_already_counted_is_known_to_the_usage_of_each_conversation(
    tmp_path: Path,
) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "parent", "Hello", title="Notes", total_cost=0.40)
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    usage = conversations._usage
    assert usage.session_total is None  # nothing is open
    workspaces.open(tmp_path)
    assert usage.session_total == 0.40  # the total of the session file
    screen.name = "Branch"
    conversations.new_branch()
    assert usage.session_total == 0.40  # the branch goes on from the one it copies
    assert usage.conversation_turns == 0
    screen.name = "Fresh"
    conversations.new()
    assert usage.session_total == 0.0  # a session that does not exist yet
    conversations.close()
    assert usage.session_total is None


def test_refreshing_takes_the_total_the_cli_reached_elsewhere(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    info = files.add_session(tmp_path, "one", "Hello", title="One", total_cost=0.40)
    conversations, _screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    files.contents[info.path].total_cost_usd = 0.90  # a terminal went on with the session
    conversations.refresh()
    assert conversations._usage.session_total == 0.90


def test_a_cancelled_branch_changes_nothing(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "parent", "Hello", title="Notes")
    conversations, _screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    conversations.new_branch()  # the name dialog is cancelled
    assert (conversations.conversation_id, conversations.fork_from) == ("parent", "")


def test_a_conversation_without_any_message_has_nothing_to_branch(tmp_path: Path) -> None:
    conversations, screen, workspaces, _settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    conversations.start_new("Notes")
    first = conversations.conversation_id
    conversations.new_branch()
    assert screen.errors == ["This conversation has no message yet: there is nothing to branch."]
    assert not any(call.startswith("ask") for call in screen.calls)
    assert conversations.conversation_id == first


def test_another_conversation_is_no_longer_a_branch(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "parent", "Hello", title="Notes")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    screen.name = "Branch"
    conversations.new_branch()
    screen.name = "Fresh"
    conversations.new()
    assert conversations.fork_from == ""


def test_deleting_moves_the_files_to_the_recycle_bin_and_selects_the_most_recent(
    tmp_path: Path,
) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "older", "Before", title="Older")
    files.add_session(tmp_path, "newer", "Hello", title="Newer")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    assert conversations.conversation_id == "newer"
    files.sessions[tmp_path].pop(0)  # what the Recycle Bin takes away, as seen by the next listing
    conversations.delete()
    assert 'confirm Move the conversation "Newer" to the Recycle Bin?' in screen.calls
    assert screen.recycled == [Path("newer.jsonl"), Path("newer")]
    assert Announce.CONVERSATION_DELETED in screen.said
    assert conversations.conversation_id == "older"
    assert screen.calls[-1] == "focus view"


def test_deleting_the_last_conversation_leaves_the_workspace_without_any(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "only", "Hello", title="Only")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    files.sessions[tmp_path].clear()
    conversations.delete()
    assert conversations.conversation_id == ""
    assert screen.said[-2:] == [Announce.CONVERSATION_DELETED, Announce.NO_CONVERSATION]
    assert workspaces.state is not None
    assert "only" not in workspaces.state.conversations


def test_a_deletion_that_is_refused_or_fails_keeps_the_conversation(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "one", "Hello", title="One")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files)
    workspaces.open(tmp_path)
    screen.confirmed = False
    conversations.delete()
    assert (screen.recycled, screen.errors) == ([], [])
    screen.confirmed, screen.recycle_works = True, False
    conversations.delete()
    assert screen.errors == ["The conversation could not be moved to the Recycle Bin."]
    assert conversations.conversation_id == "one"
    assert Announce.CONVERSATION_DELETED not in screen.said


def test_a_conversation_is_not_deleted_while_claude_answers(tmp_path: Path) -> None:
    files = FakeClaudeFiles()
    files.add_session(tmp_path, "one", "Hello", title="One")
    conversations, screen, workspaces, _settings = _presenters(tmp_path, files, busy=[True])
    workspaces.open(tmp_path)
    conversations.delete()
    assert screen.errors == ["Wait for Claude to finish before deleting the conversation."]
    assert not any(call.startswith("confirm") for call in screen.calls)
    assert conversations.conversation_id == "one"


def test_the_agent_of_a_conversation_is_remembered_and_not_the_alternative_one(
    tmp_path: Path,
) -> None:
    conversations, screen, workspaces, _settings = _presenters(tmp_path)
    workspaces.open(tmp_path)
    conversations.start_new("Notes")
    screen.agent = Agent(model="haiku", effort="low", permission_mode="plan")
    conversations.choose_agent()
    assert workspaces.state is not None
    record = workspaces.state.conversations[conversations.conversation_id]
    assert record.agent == screen.agent
    assert conversations.agent_for(alternative=False) == screen.agent
    assert conversations.agent_for(alternative=True) == workspaces.state.alternative_agent


def test_the_alternative_agent_of_the_workspace_is_the_one_used_and_is_remembered(
    tmp_path: Path,
) -> None:
    conversations, _screen, workspaces, settings = _presenters(tmp_path)
    settings.alternative_agent = Agent(provider="claude", effort="low", model="haiku")
    workspaces.open(tmp_path)
    conversations.start_new("Notes")
    assert conversations.workspace_alternative_agent.model == "haiku"  # taken at its creation
    chosen = Agent(provider="deepseek", model="flash", effort="max", permission_mode="plan")
    conversations.set_workspace_alternative_agent(chosen)
    settings.alternative_agent = Agent(effort="medium")  # the Preferences change: no effect
    assert conversations.agent_for(alternative=True) == chosen
    assert conversations.agent_for(alternative=False) == conversations.agent
    reloaded = WorkspaceState.load(tmp_path, settings.workspaces_dir)
    assert reloaded.alternative_agent == chosen


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


def _sending(
    tmp_path: Path, *, busy: bool = False, started: bool = True
) -> tuple[ConversationPresenter, FakeScreen, list[tuple[str, Agent]]]:
    """A presenter with a conversation, and the messages that Claude was started on."""
    sent: list[tuple[str, Agent]] = []

    def start(text: str, agent: Agent) -> bool:
        sent.append((text, agent))
        return started

    conversations, screen, _workspaces, _settings = _presenters(
        tmp_path, busy=[True] if busy else None, start=start
    )
    conversations.start_new("Notes")
    screen.calls.clear()
    return conversations, screen, sent


def test_a_message_can_be_sent_with_a_conversation_when_claude_is_not_answering(
    tmp_path: Path,
) -> None:
    conversations, _screen, _workspaces, _settings = _presenters(tmp_path)
    assert not conversations.can_send  # no conversation yet
    conversations.start_new("Notes")
    assert conversations.can_send
    busy, _screen, _workspaces, _settings = _presenters(tmp_path, busy=[True])
    busy.start_new("Notes")
    assert not busy.can_send


def test_the_text_is_trimmed_and_sent_with_the_agent_of_the_conversation(tmp_path: Path) -> None:
    conversations, _screen, sent = _sending(tmp_path)
    conversations.send("  Hello there \n", alternative=False)
    assert sent == [("Hello there", conversations.agent_for(alternative=False))]


def test_the_alternative_agent_is_used_when_asked(tmp_path: Path) -> None:
    conversations, _screen, sent = _sending(tmp_path)
    conversations.send("Hello", alternative=True)
    ((_text, agent),) = sent
    assert agent == conversations.agent_for(alternative=True)
    assert agent != conversations.agent_for(alternative=False)


def test_once_claude_is_started_the_prompt_is_emptied_and_the_sent_message_focused(
    tmp_path: Path,
) -> None:
    conversations, screen, _sent = _sending(tmp_path)
    conversations.send("Hello", alternative=False)
    assert screen.calls == ["clear prompt", "focus view"]


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_a_blank_text_is_not_sent(tmp_path: Path, text: str) -> None:
    conversations, screen, sent = _sending(tmp_path)
    conversations.send(text, alternative=False)
    assert sent == []
    assert screen.calls == []


def test_nothing_is_sent_while_claude_answers_and_the_prompt_keeps_its_text(
    tmp_path: Path,
) -> None:
    conversations, screen, sent = _sending(tmp_path, busy=True)
    conversations.send("Hello", alternative=False)
    assert sent == []
    assert screen.calls == []


def test_nothing_is_sent_without_a_conversation(tmp_path: Path) -> None:
    sent: list[tuple[str, Agent]] = []

    def start(text: str, agent: Agent) -> bool:
        sent.append((text, agent))
        return True

    conversations, screen, _workspaces, _settings = _presenters(tmp_path, start=start)
    conversations.send("Hello", alternative=False)
    assert sent == []
    assert screen.calls == []


def test_a_message_that_could_not_be_started_keeps_the_prompt(tmp_path: Path) -> None:
    conversations, screen, sent = _sending(tmp_path, started=False)
    conversations.send("Hello", alternative=False)
    assert len(sent) == 1  # it was tried
    assert screen.calls == []  # but the text stays where it is, to be sent again


def test_there_is_a_conversation_once_one_is_started_and_no_more_once_it_is_closed(
    tmp_path: Path,
) -> None:
    conversations, _screen, _workspaces, _settings = _presenters(tmp_path)
    assert not conversations.has_conversation
    conversations.start_new("Notes")
    assert conversations.has_conversation
    conversations.close()
    assert not conversations.has_conversation

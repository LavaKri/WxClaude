"""A message sent to Claude: starting it, following its events, the permission questions, its end.

The runner works in threads; its events are handed over to the interface thread by the view
(``RunView.call_after``) and followed here (see ``docs/architecture.md``, "A turn"). Nothing here
touches wx: what is shown or asked goes through ``RunView``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from wxclaude.core.claude.events import (
    ApiRetry,
    AssistantText,
    Compacted,
    PermissionExpired,
    PermissionRequest,
    RateLimit,
    RunEvent,
    SessionInit,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.launch import launch_for
from wxclaude.core.claude.permissions import (
    Decision,
)
from wxclaude.core.claude.progress import (
    Outcome,
    Progress,
    compaction_progress,
    progress_for,
    retry_progress,
    turn_outcome,
)
from wxclaude.core.claude.questions import Question
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.conversation.messages import Message, Role
from wxclaude.core.errors import (
    ClaudeNotFoundError,
    KeyVaultError,
    ProviderError,
    RunnerError,
)
from wxclaude.core.security.restricted import restricted_permission_mode
from wxclaude.core.speech.announcements import DEFAULT_SPEAKER, Announce, AnnouncementCenter
from wxclaude.i18n import _
from wxclaude.presenters.gauge_reader import GaugeLinks, GaugeReader
from wxclaude.presenters.permission_handler import PermissionHandler, PermissionLinks
from wxclaude.presenters.progress_announcer import ProgressAnnouncer, ProgressLinks
from wxclaude.presenters.shared import Shared, read_session
from wxclaude.presenters.stats_recorder import StatsRecorder


class RunView(Protocol):
    """What the presenter asks of the interface while a message is answered."""

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        """Call ``function(event)`` later on the interface thread (from any thread)."""
        ...

    def append_message(self, message: Message) -> None:
        """Add a message at the end of the conversation."""
        ...

    def show_session(self, messages: list[Message]) -> None:
        """The messages of the session file, the reference once the turn is over."""
        ...

    def ask_permission(self, request: PermissionRequest, wait_text: str = "") -> Decision:
        """Ask the user; ``wait_text`` tells until when the CLI waits (hook channel, else '').
        Closing the question without answering is a denial."""
        ...

    def ask_questions(self, questions: list[Question]) -> dict[str, list[str]] | None:
        """Ask the structured questions of Claude: the labels chosen for each question (by its
        text), None if the user refused to answer."""
        ...

    def close_permission(self, request_id: str) -> None:
        """Close the question ``request_id`` if it is still open (the CLI stopped waiting)."""
        ...

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, where the category of ``announce`` says."""
        ...

    def set_status(self, text: str) -> None:
        """The message field of the status bar."""
        ...

    def show_step(self, text: str) -> None:
        """The step field of the status bar ('' when there is none)."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


@dataclass(frozen=True, slots=True)
class RunLinks:
    """What the presenter asks of the window: where it works, which conversation and its name,
    whether the window is closing, and a call when the busy state changes (to grey what must be)."""

    workspace: Callable[[], Path | None]
    conversation_id: Callable[[], str]
    conversation_name: Callable[[], str]
    fork_from: Callable[[], str]
    is_closing: Callable[[], bool]
    state_changed: Callable[[], None]
    stats: Callable[[], WorkspaceStats | None] = lambda: None  # the statistics of the workspace


class RunPresenter:
    """Runs one message at a time and shows what Claude does through ``view``."""

    def __init__(
        self,
        view: RunView,
        runner: ClaudeRunner,
        shared: Shared,
        links: RunLinks,
    ) -> None:
        self._view = view
        self.runner = runner
        self._settings = shared.settings
        self._usage = shared.usage
        self._files = shared.files
        self._security = shared.security
        self._providers = shared.providers
        self._relay = shared.relay
        self._links = links
        self._busy = False  # True while Claude is answering
        self._turn_agent = shared.settings.default_agent  # the agent of the message being answered
        self._turn_result: TurnResult | None = None
        self._refused: ApiRetry | None = None  # the server refused the credentials: stopped
        self._gauges = GaugeReader(
            view,
            runner,
            shared.usage,
            GaugeLinks(
                links.workspace,
                links.is_closing,
                links.state_changed,
                lambda: self._restricted,
            ),
        )
        self._local_messages = 0  # messages added by this run, for their identifiers
        self._stats = StatsRecorder(links.stats, lambda message: self._view.show_error(message))
        self._permissions = PermissionHandler(
            view,
            runner,
            shared,
            self._stats,
            PermissionLinks(self._say, lambda: self._turn_agent.permission_mode, links.workspace),
        )
        self._turn_model = ""  # the model that really answers the message (SessionInit)
        self._turn_conversation = ""  # the conversation the message belongs to
        self._turn_mode = ""  # the permission mode the CLI was given for the message
        self._turn_masked = False  # the credentials are hidden from the tools: mode forced
        self._progress = ProgressAnnouncer(
            view,
            shared.files,
            ProgressLinks(self._say, lambda: self._speaker, links.conversation_id),
        )

    @property
    def busy(self) -> bool:
        """True while Claude is answering or the gauges are being read."""
        return self._busy or self._gauges.refreshing

    @property
    def answering(self) -> bool:
        """True while a message is answered (not while the gauges are read)."""
        return self._busy

    @property
    def refreshing(self) -> bool:
        """True while the gauges are being read: what they would show is not known yet."""
        return self._gauges.refreshing

    def refresh_gauges_if_due(self, now: datetime) -> bool:
        """Read the gauges with ``/usage`` when they are not known or out of date (``GaugeReader``).
        Nothing is read while a message is answered or the gauges are already being read. True if
        a reading started."""
        return not self.busy and self._gauges.refresh_if_due(now)

    @property
    def _restricted(self) -> bool:
        """Is the folder not trusted? The CLI is then launched so that it ignores the project."""
        return self._security is not None and self._security.restricted

    @property
    def _max_turns(self) -> int:
        """The limit of turns of the workspace (0: none)."""
        state = None if self._security is None else self._security.state
        return 0 if state is None else state.max_turns

    def start(self, text: str, agent: Agent) -> bool:
        """Start Claude on ``text``; False (with the error shown) if it cannot be started."""
        workspace = self._links.workspace()
        if workspace is None:
            return False
        conversation_id = self._links.conversation_id()
        try:
            provider = launch_for(
                agent.provider,
                self._providers,
                transmission=self._settings.key_transmission,
                relay=self._relay,
            )
        except (ProviderError, KeyVaultError) as error:
            self._view.show_error(_("Claude cannot be started.\n{error}").format(error=error))
            return False
        request = RunRequest(
            text,
            agent,
            conversation_id,
            self._files.find_session(conversation_id) is not None,
            workspace,
            self._links.conversation_name(),  # given to the CLI by the first message only
            self._links.fork_from(),  # a branch: its first message copies that history
            restricted=self._restricted,
            provider=provider,
            max_turns=self._max_turns,
        )
        self.runner.permission_channel = self._settings.permission_channel
        self.runner.hook_timeout_seconds = self._settings.hook_timeout_minutes * 60
        try:
            self.runner.start(request, self._post_event)
        except (ClaudeNotFoundError, RunnerError) as error:
            self._view.show_error(_("Claude cannot be started.\n{error}").format(error=error))
            return False
        self._busy = True
        self._view.show_step("")
        self._turn_agent = agent
        self._turn_result = None
        self._refused = None
        self._turn_model = ""
        self._turn_conversation = conversation_id
        self._turn_mode = self._mode_sent(agent)
        self._turn_masked = provider is not None and provider.active and provider.scrub
        self._stats.start_message()
        self._progress.reset()
        self._permissions.start_message()
        self._links.state_changed()
        self._view.append_message(Message(self._local_id(), Role.USER, text))
        self._progress.show(Progress(Announce.CLAUDE_THINKING))
        return True

    def _mode_sent(self, agent: Agent) -> str:
        """The permission mode the CLI is given for ``agent``: a folder that is not trusted
        keeps only the strict modes, the others become manual (``RunRequest.restricted``)."""
        mode = agent.permission_mode or ""
        return restricted_permission_mode(mode) if self._restricted else mode

    def interrupt(self) -> None:
        """Stop the message being answered, or the reading of the gauges (nothing happens if
        neither is going on; the reading is stopped without a word)."""
        if self.busy:
            if not self._gauges.refreshing:
                self._say(Announce.CLAUDE_INTERRUPTING)
            self.runner.interrupt()

    def stop(self) -> None:
        """Stop what Claude is doing, without a word: the window is closing."""
        self.runner.interrupt()

    @property
    def claude_path(self) -> str:
        """The claude program that is started ('' looks for it in the PATH)."""
        return self.runner.claude_path

    @claude_path.setter
    def claude_path(self, path: str) -> None:
        self.runner.claude_path = path

    @property
    def _speaker(self) -> str:
        """Who answers the message under way: the name of the provider of its agent."""
        if self._providers is None:
            return DEFAULT_SPEAKER
        return self._providers.get(self._turn_agent.provider).name

    def _say(self, announce: Announce, **values: object) -> None:
        """Say ``announce`` naming who answers (Claude, or the provider of the agent)."""
        self._view.say(announce, name=self._speaker, **values)

    def _local_id(self) -> str:
        self._local_messages += 1
        return f"local-{self._local_messages}"

    def _post_event(self, event: RunEvent) -> None:
        """Called by the threads of the runner: hand the event over to the interface thread."""
        self._view.call_after(self.on_event, event)

    def on_event(self, event: RunEvent) -> None:
        """An event of the run, on the interface thread."""
        if self._links.is_closing():
            return
        if isinstance(event, AssistantText):
            self._view.append_message(
                Message(
                    self._local_id(),
                    Role.ASSISTANT,
                    event.text.strip(),
                    model=event.model,
                    effort=self._turn_agent.effort if event.model else None,
                )
            )
        elif isinstance(event, ToolUsed) and self._progress.show_step(event):
            return
        elif isinstance(event, PermissionRequest | PermissionExpired | ApiRetry):
            self._on_question_or_retry(event)
            return
        elif isinstance(event, RateLimit):
            self._usage.record_rate_limit(event, datetime.now())
            self._gauges.alert(event.windows)
        elif isinstance(event, SessionInit | TurnResult):
            self._on_turn_data(event)
        elif isinstance(event, Compacted):
            self._progress.announce(compaction_progress(event))
            return
        elif isinstance(event, TurnEnded):
            self._finish_turn(event)
            return
        progress = progress_for(event)
        if progress is not None:
            self._progress.show(progress)

    def _on_question_or_retry(
        self, event: PermissionRequest | PermissionExpired | ApiRetry
    ) -> None:
        """The events that say nothing in the progress: a question to answer, one that expired, a
        retry of the CLI."""
        if isinstance(event, PermissionRequest):
            self._permissions.request(event)
        elif isinstance(event, PermissionExpired):
            self._permissions.expired(event)
        else:
            self._on_retry(event)

    def _on_retry(self, event: ApiRetry) -> None:
        """The CLI will ask the server again. A refusal of the credentials is retried ten times
        with growing waits and cannot get better: stop the run at the first one, and tell why when
        it ends (``_finish_turn``). Any other error is retried by the CLI for a long time without
        a word: say it, so that the user knows and may interrupt."""
        if event.refused:
            if self._refused is None:
                self._refused = event
                self.runner.interrupt()
            return
        self._progress.announce(retry_progress(event))

    def _on_turn_data(self, event: SessionInit | TurnResult) -> None:
        """What the CLI tells about the message: the model that really answers, then its result
        (the usage and the statistics of the workspace)."""
        if isinstance(event, SessionInit):
            self._turn_model = event.model
            self._progress.announce_start(event, self._turn_mode, masked=self._turn_masked)
            return
        result = event
        self._turn_result = result
        self._usage.record_result(result)
        self._stats.record(
            result,
            conversation_id=self._turn_conversation,
            model=self._turn_model or self._turn_agent.model or "",
            cost=self._usage.last_cost,
        )

    def _finish_turn(self, ended: TurnEnded) -> None:
        self._busy = False
        self._view.show_step("")  # waiting for the next prompt
        self._links.state_changed()
        outcome = turn_outcome(self._turn_result, ended, self._refused)
        self._turn_result = None
        self._refused = None
        self._reconcile_with_session_file()
        if outcome.outcome is Outcome.DONE:
            self._say(Announce.CLAUDE_DONE)
        elif outcome.outcome is Outcome.INTERRUPTED:
            self._say(Announce.CLAUDE_INTERRUPTED)
        if outcome.outcome is not Outcome.FAILED:
            self._view.set_status(self._usage.ready_line())  # waiting for the next prompt
        else:
            first_line = outcome.details.splitlines()[0] if outcome.details else ""
            # The dialog below tells it to the screen reader: the status bar is enough here.
            self._view.set_status(
                AnnouncementCenter.text(
                    Announce.CLAUDE_FAILED, name=self._speaker, details=first_line
                )
            )
            self._view.show_error(
                _("{name} could not answer.\n{details}").format(
                    name=self._speaker, details=outcome.details
                )
            )

    def _reconcile_with_session_file(self) -> None:
        """The session file of the CLI is the reference: the view shows it."""
        path = self._files.find_session(self._links.conversation_id())
        if path is None:
            return
        session = read_session(self._files, path, self._view.show_error)
        if session is not None:
            self._view.show_session(session.messages)

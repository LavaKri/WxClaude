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
    AssistantText,
    GaugesRead,
    PermissionExpired,
    PermissionRequest,
    RateLimit,
    RateWindow,
    RunEvent,
    SessionInit,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.gauge_schedule import GaugeSchedule
from wxclaude.core.claude.permission_channel import HOOK
from wxclaude.core.claude.permissions import Choice, Decision, hook_wait_text
from wxclaude.core.claude.progress import Outcome, Progress, progress_for, turn_outcome
from wxclaude.core.claude.questions import Question, is_question, parse_questions
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest
from wxclaude.core.claude.tasks import started_task_id, step_of
from wxclaude.core.claude.usage import GaugeAlerts
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.conversation.messages import Message, Role
from wxclaude.core.errors import (
    ClaudeNotFoundError,
    ClaudeSettingsError,
    RunnerError,
    SessionReadError,
    TaskReadError,
)
from wxclaude.core.speech.announcements import Announce, AnnouncementCenter
from wxclaude.i18n import _
from wxclaude.presenters.shared import Shared
from wxclaude.presenters.stats_recorder import StatsRecorder

#: The announcement of each gauge that has an alert.
_GAUGE_ALERTS = {"five_hour": Announce.GAUGE_FIVE_HOUR, "seven_day": Announce.GAUGE_WEEKLY}


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
        self._links = links
        self._busy = False  # True while Claude is answering
        self._turn_agent = shared.settings.default_agent  # the agent of the message being answered
        self._turn_result: TurnResult | None = None
        self._last_progress = ""  # the last progress shown, not repeated
        self._turn_allowed: set[str] = set()  # rules always allowed during this message
        self._expired: set[str] = set()  # questions the CLI stopped waiting for (hook channel)
        self._alerts = GaugeAlerts()  # which gauges were announced, for as long as the window lives
        self._schedule = GaugeSchedule()  # when the gauges are read again
        self._refreshing = False  # True while the gauges are read (busy too)
        self._local_messages = 0  # messages added by this run, for their identifiers
        self._stats = StatsRecorder(links.stats, lambda message: self._view.show_error(message))
        self._turn_model = ""  # the model that really answers the message (SessionInit)
        self._turn_conversation = ""  # the conversation the message belongs to

    @property
    def busy(self) -> bool:
        """True while Claude is answering or the gauges are being read."""
        return self._busy

    @property
    def refreshing(self) -> bool:
        """True while the gauges are being read: what they would show is not known yet."""
        return self._refreshing

    def refresh_gauges_if_due(self, now: datetime) -> bool:
        """Read the gauges with ``/usage`` when they are not known or out of date.

        It is handled like a message: the send buttons are greyed and the status bar says so until
        the end, and nothing is announced. Nothing is read without a workspace, while a message is
        answered, or when the CLI cannot be started (the next try waits longer). True if started.
        """
        workspace = self._links.workspace()
        if self._busy or workspace is None:
            return False
        if not self._schedule.due(self._usage.windows.values(), now):
            return False
        try:
            self.runner.read_usage(workspace, self._post_reading)
        except ClaudeNotFoundError, RunnerError:
            self._schedule.finished(self._usage.windows.values(), now, ok=False)
            return False
        self._busy = self._refreshing = True
        self._view.set_status(_("Refreshing the gauges"))
        self._links.state_changed()
        return True

    def _post_reading(self, event: RunEvent) -> None:
        """Called by the thread of the reading: hand the end of it over to the interface thread."""
        self._view.call_after(self._finish_gauge_refresh, event)

    def _finish_gauge_refresh(self, read: RunEvent) -> None:
        """The reading ended (or failed): the gauges are kept if it gave any, nothing is said."""
        if self._links.is_closing() or not isinstance(read, GaugesRead):
            return
        self._busy = self._refreshing = False
        now = datetime.now()
        if read.windows:
            self._usage.record_windows(read.windows, now)
        self._schedule.finished(self._usage.windows.values(), now, ok=bool(read.windows))
        self._links.state_changed()
        self._view.set_status(self._usage.ready_line())
        self._alert_gauges(read.windows)

    def start(self, text: str, agent: Agent) -> bool:
        """Start Claude on ``text``; False (with the error shown) if it cannot be started."""
        workspace = self._links.workspace()
        if workspace is None:
            return False
        conversation_id = self._links.conversation_id()
        request = RunRequest(
            text,
            agent,
            conversation_id,
            self._files.find_session(conversation_id) is not None,
            workspace,
            self._links.conversation_name(),  # given to the CLI by the first message only
            self._links.fork_from(),  # a branch: its first message copies that history
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
        self._turn_model = ""
        self._turn_conversation = conversation_id
        self._stats.start_message()
        self._last_progress = ""
        self._turn_allowed = set()
        self._expired = set()
        self._links.state_changed()
        self._view.append_message(Message(self._local_id(), Role.USER, text))
        self._show_progress(Progress(Announce.CLAUDE_THINKING))
        return True

    def interrupt(self) -> None:
        """Stop the message being answered, or the reading of the gauges (nothing happens if
        neither is going on; the reading is stopped without a word)."""
        if self._busy:
            if not self._refreshing:
                self._view.say(Announce.CLAUDE_INTERRUPTING)
            self.runner.interrupt()

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
        elif isinstance(event, ToolUsed) and self._show_step(event):
            return
        elif isinstance(event, PermissionRequest):
            self._on_permission_request(event)
            return
        elif isinstance(event, PermissionExpired):
            self._on_permission_expired(event)
            return
        elif isinstance(event, RateLimit):
            self._usage.record_rate_limit(event, datetime.now())
            self._alert_gauges(event.windows)
        elif isinstance(event, SessionInit | TurnResult):
            self._on_turn_data(event)
        elif isinstance(event, TurnEnded):
            self._finish_turn(event)
            return
        progress = progress_for(event)
        if progress is not None:
            self._show_progress(progress)

    def _on_turn_data(self, event: SessionInit | TurnResult) -> None:
        """What the CLI tells about the message: the model that really answers, then its result
        (the usage and the statistics of the workspace)."""
        if isinstance(event, SessionInit):
            self._turn_model = event.model
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

    def _alert_gauges(self, windows: tuple[RateWindow, ...]) -> None:
        """Announce the gauges that just reached their alert threshold (once per crossing)."""
        for window in self._alerts.update(windows):
            announce = _GAUGE_ALERTS.get(window.name)
            if announce is not None and window.utilization is not None:
                self._view.say(announce, percent=round(window.utilization * 100))

    def _show_step(self, tool: ToolUsed) -> bool:
        """Claude puts a task of its list in progress: say which step, and keep it in the status
        bar. False when the call is not that (or the task is not in the list): normal progress."""
        task_id = started_task_id(tool.name, tool.input)
        if task_id is None:
            return False
        try:
            tasks = self._files.load_tasks(self._links.conversation_id())
        except TaskReadError as error:
            self._view.show_error(_("Cannot read the tasks.\n{error}").format(error=error))
            return False
        step = step_of(task_id, tasks)
        if step is None:
            return False
        values = {"number": step.number, "total": step.total, "subject": step.subject}
        self._view.show_step(AnnouncementCenter.text(Announce.STEP_STARTED, **values))
        self._view.say(Announce.STEP_STARTED, **values)
        self._last_progress = ""  # what comes next is said again, it is about another step
        return True

    def _on_permission_request(self, request: PermissionRequest) -> None:
        """Claude asks before running a tool: a rule allowed earlier in this message, else ask.
        Its structured questions have a dialog of their own."""
        if is_question(request):
            questions = parse_questions(request)
            if questions:
                self._on_questions(request, questions)
                return
        rule = request.suggested_rule
        if rule and rule in self._turn_allowed:
            decision = Decision(Choice.ALLOW)
        else:
            self._view.say(Announce.PERMISSION_ASKED, tool=request.tool_name)
            with self._stats.waiting():
                decision = self._view.ask_permission(request, self._wait_text())
            if request.request_id in self._expired:
                return  # the CLI stopped waiting while the question was open: nothing to answer
        try:
            if decision.choice is Choice.DENY:
                self.runner.deny(request, decision.denial_message())
                self._view.say(Announce.PERMISSION_REFUSED, tool=request.tool_name)
                return
            if decision.choice is Choice.ALLOW_ALWAYS and rule:
                self._remember_always_allowed(rule)
            self.runner.allow(request)
            self._view.say(Announce.PERMISSION_GRANTED, tool=request.tool_name)
        except RunnerError as error:
            self._view.show_error(_("Claude could not be answered.\n{error}").format(error=error))

    def _on_questions(self, request: PermissionRequest, questions: list[Question]) -> None:
        """Claude has questions: ask them, give the answers back (or refuse to answer)."""
        self._view.say(Announce.QUESTION_ASKED)
        with self._stats.waiting():
            answers = self._view.ask_questions(questions)
        if request.request_id in self._expired:
            return  # the CLI stopped waiting while the questions were open
        try:
            if answers is None:
                self.runner.deny(request, Decision(Choice.DENY).denial_message())
                self._view.say(Announce.PERMISSION_REFUSED, tool=request.tool_name)
                return
            self.runner.answer_questions(request, answers)
            self._view.say(Announce.QUESTION_ANSWERED)
        except RunnerError as error:
            self._view.show_error(_("Claude could not be answered.\n{error}").format(error=error))

    def _wait_text(self) -> str:
        """With the hook channel the CLI stops waiting after a while: say when."""
        if self.runner.permission_channel != HOOK:
            return ""
        return hook_wait_text(datetime.now(), self.runner.hook_timeout_seconds // 60)

    def _remember_always_allowed(self, rule: str) -> None:
        """Write the rule in the personal settings file, and keep it for the rest of the message."""
        self._turn_allowed.add(rule)
        workspace = self._links.workspace()
        if workspace is None:
            return
        try:
            self._files.allow_always(workspace, rule)
        except ClaudeSettingsError as error:
            self._view.show_error(_("The rule could not be saved.\n{error}").format(error=error))

    def _on_permission_expired(self, expired: PermissionExpired) -> None:
        """The CLI stopped waiting and denied the tool: close the question if it is still open."""
        self._expired.add(expired.request_id)
        self._view.close_permission(expired.request_id)
        self._view.say(Announce.PERMISSION_EXPIRED, tool=expired.tool_name)

    def _show_progress(self, progress: Progress) -> None:
        """Progress goes where the category of its announcement says; the same text twice in a
        row is said once."""
        text = AnnouncementCenter.text(progress.announce, **progress.values)
        if text == self._last_progress:
            return
        self._last_progress = text
        self._view.say(progress.announce, **progress.values)

    def _finish_turn(self, ended: TurnEnded) -> None:
        self._busy = False
        self._view.show_step("")  # waiting for the next prompt
        self._links.state_changed()
        outcome = turn_outcome(self._turn_result, ended)
        self._turn_result = None
        self._reconcile_with_session_file()
        if outcome.outcome is Outcome.DONE:
            self._view.say(Announce.CLAUDE_DONE)
        elif outcome.outcome is Outcome.INTERRUPTED:
            self._view.say(Announce.CLAUDE_INTERRUPTED)
        if outcome.outcome is not Outcome.FAILED:
            self._view.set_status(self._usage.ready_line())  # waiting for the next prompt
        else:
            first_line = outcome.details.splitlines()[0] if outcome.details else ""
            # The dialog below tells it to the screen reader: the status bar is enough here.
            self._view.set_status(
                AnnouncementCenter.text(Announce.CLAUDE_FAILED, details=first_line)
            )
            self._view.show_error(
                _("Claude could not answer.\n{details}").format(details=outcome.details)
            )

    def _reconcile_with_session_file(self) -> None:
        """The session file of the CLI is the reference: the view shows it."""
        path = self._files.find_session(self._links.conversation_id())
        if path is None:
            return
        try:
            session = self._files.read_session(path)
        except SessionReadError as error:
            self._view.show_error(_("Cannot read the conversation.\n{error}").format(error=error))
            return
        self._view.show_session(session.messages)

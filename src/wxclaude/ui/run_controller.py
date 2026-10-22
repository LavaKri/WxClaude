"""A message sent to Claude: starting it, following its events, the permission questions, its end.

The runner works in threads; its events are handed over to the interface thread with
``wx.CallAfter`` and followed here (see ``docs/architecture.md``, "A turn").
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import wx

from wxclaude.core.agents import Agent
from wxclaude.core.announcements import Announce
from wxclaude.core.claude_projects import find_session_file
from wxclaude.core.claude_settings import allow_always
from wxclaude.core.errors import (
    ClaudeNotFoundError,
    ClaudeSettingsError,
    RunnerError,
)
from wxclaude.core.events import (
    AssistantText,
    PermissionRequest,
    RateLimit,
    RunEvent,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.messages import Message, Role
from wxclaude.core.permissions import Choice, Decision
from wxclaude.core.progress import Outcome, Progress, progress_for, turn_outcome
from wxclaude.core.runner import ClaudeRunner, RunRequest
from wxclaude.core.settings import Settings
from wxclaude.core.usage import UsageTracker
from wxclaude.i18n import _
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.permission_dialog import PermissionDialog


@dataclass(frozen=True, slots=True)
class RunLinks:
    """What the controller asks of the window: where it works, which conversation, whether the
    window is closing, and a call when the busy state changes (to grey what must be)."""

    workspace: Callable[[], Path | None]
    conversation_id: Callable[[], str]
    is_closing: Callable[[], bool]
    state_changed: Callable[[], None]


class RunController:
    """Runs one message at a time and shows what Claude does in the conversation view."""

    def __init__(
        self,
        parent: wx.Window,
        runner: ClaudeRunner,
        view: ConversationView,
        feedback: Feedback,
        settings: Settings,
        usage: UsageTracker,
        links: RunLinks,
    ) -> None:
        self._parent = parent
        self.runner = runner
        self._view = view
        self._feedback = feedback
        self._settings = settings
        self._usage = usage
        self._links = links
        self._busy = False  # True while Claude is answering
        self._turn_agent = settings.default_agent  # the agent of the message being answered
        self._turn_result: TurnResult | None = None
        self._last_progress = ""  # the last progress shown, not repeated
        self._turn_allowed: set[str] = set()  # rules always allowed during this message
        self._local_messages = 0  # messages added by this run, for their identifiers

    @property
    def busy(self) -> bool:
        """True while Claude is answering."""
        return self._busy

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
            find_session_file(conversation_id) is not None,
            workspace,
        )
        try:
            self.runner.start(request, self._post_event)
        except (ClaudeNotFoundError, RunnerError) as error:
            self._feedback.show_error(_("Claude cannot be started.\n{error}").format(error=error))
            return False
        self._busy = True
        self._turn_agent = agent
        self._turn_result = None
        self._last_progress = ""
        self._turn_allowed = set()
        self._links.state_changed()
        self._view.append_message(Message(self._local_id(), Role.USER, text))
        self._show_progress(Progress(Announce.CLAUDE_THINKING))
        return True

    def interrupt(self) -> None:
        """Stop the message being answered (nothing happens if none is)."""
        if self._busy:
            self._feedback.say(Announce.CLAUDE_INTERRUPTING)
            self.runner.interrupt()

    def _local_id(self) -> str:
        self._local_messages += 1
        return f"local-{self._local_messages}"

    def _post_event(self, event: RunEvent) -> None:
        """Called by the threads of the runner: hand the event over to the interface thread."""
        wx.CallAfter(self._on_run_event, event)

    def _on_run_event(self, event: RunEvent) -> None:
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
        elif isinstance(event, PermissionRequest):
            self._on_permission_request(event)
            return
        elif isinstance(event, RateLimit):
            self._usage.record_rate_limit(event, datetime.now())
        elif isinstance(event, TurnResult):
            self._turn_result = event
            self._usage.record_result(event)
        elif isinstance(event, TurnEnded):
            self._finish_turn(event)
            return
        progress = progress_for(event)
        if progress is not None:
            self._show_progress(progress)

    def _on_permission_request(self, request: PermissionRequest) -> None:
        """Claude asks before running a tool: a rule allowed earlier in this message, else ask."""
        rule = request.suggested_rule
        if rule and rule in self._turn_allowed:
            decision = Decision(Choice.ALLOW)
        else:
            self._feedback.set_status(
                self._feedback.announcements.text(Announce.PERMISSION_ASKED, tool=request.tool_name)
            )
            decision = self._ask_permission(request)
        try:
            if decision.choice is Choice.DENY:
                self.runner.deny(request, decision.denial_message())
                self._feedback.say(Announce.PERMISSION_REFUSED, tool=request.tool_name)
                return
            if decision.choice is Choice.ALLOW_ALWAYS and rule:
                self._remember_always_allowed(rule)
            self.runner.allow(request)
            self._feedback.say(Announce.PERMISSION_GRANTED, tool=request.tool_name)
        except RunnerError as error:
            self._feedback.show_error(
                _("Claude could not be answered.\n{error}").format(error=error)
            )

    def _remember_always_allowed(self, rule: str) -> None:
        """Write the rule in the personal settings file, and keep it for the rest of the message."""
        self._turn_allowed.add(rule)
        workspace = self._links.workspace()
        if workspace is None:
            return
        try:
            allow_always(workspace, rule)
        except ClaudeSettingsError as error:
            self._feedback.show_error(
                _("The rule could not be saved.\n{error}").format(error=error)
            )

    def _ask_permission(self, request: PermissionRequest) -> Decision:
        """Show the question; closing the dialog without answering is a denial."""
        with PermissionDialog(self._parent, request) as dialog:
            self._feedback.modal(dialog)
            decision: Decision = dialog.decision
        return decision

    def _show_progress(self, progress: Progress) -> None:
        """Progress goes to the status bar, and to the screen reader if the option is on."""
        text = self._feedback.announcements.text(progress.announce, **progress.values)
        if text == self._last_progress:
            return
        self._last_progress = text
        if self._settings.announce_progress:
            self._feedback.say(progress.announce, **progress.values)
        else:
            self._feedback.set_status(text)

    def _finish_turn(self, ended: TurnEnded) -> None:
        self._busy = False
        self._links.state_changed()
        outcome = turn_outcome(self._turn_result, ended)
        self._turn_result = None
        self._reconcile_with_session_file()
        if outcome.outcome is Outcome.DONE:
            self._feedback.say(Announce.CLAUDE_DONE)
        elif outcome.outcome is Outcome.INTERRUPTED:
            self._feedback.say(Announce.CLAUDE_INTERRUPTED)
        else:
            first_line = outcome.details.splitlines()[0] if outcome.details else ""
            self._feedback.say(Announce.CLAUDE_FAILED, details=first_line)
            self._feedback.show_error(
                _("Claude could not answer.\n{details}").format(details=outcome.details)
            )

    def _reconcile_with_session_file(self) -> None:
        """The session file of the CLI is the reference: show it if it differs from the view."""
        path = find_session_file(self._links.conversation_id())
        if path is None:
            return
        session = self._feedback.read_session(path)
        if session is None:
            return
        view = self._view
        if view.shows(session.messages):
            view.adopt_details(session.messages)  # the messages shown live have no tools yet
        else:
            caret = view.GetInsertionPoint()
            view.set_messages(session.messages)
            view.SetInsertionPoint(min(caret, view.GetLastPosition()))

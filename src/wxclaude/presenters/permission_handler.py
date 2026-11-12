"""The questions Claude asks while it answers a message: a permission to use a tool, its structured
questions, and the questions the CLI stopped waiting for.

Taken out of ``RunPresenter`` so that it keeps the course of a message; the state kept here (the
rules allowed for the message, the questions that expired) lives as long as the message.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from wxclaude.core.claude.events import PermissionExpired, PermissionRequest
from wxclaude.core.claude.permission_channel import HOOK
from wxclaude.core.claude.permissions import (
    PLAN_QUESTIONS_REFUSAL,
    PLAN_REFUSAL,
    Choice,
    Decision,
    hook_wait_text,
    is_plan_request,
)
from wxclaude.core.claude.questions import Question, is_question, parse_questions
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.errors import ClaudeSettingsError, RunnerError
from wxclaude.core.security.watch import ExternalChangeError
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _
from wxclaude.presenters.shared import Shared
from wxclaude.presenters.stats_recorder import StatsRecorder


class PermissionView(Protocol):
    """What the handler asks of the interface (``RunView`` gives it)."""

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

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


@dataclass(frozen=True, slots=True)
class PermissionLinks:
    """What the handler asks of the presenter of the message: to say something naming who
    answers (Claude, or the provider), the permission mode of its agent, and the workspace."""

    say: Callable[..., None]
    turn_mode: Callable[[], str | None]
    workspace: Callable[[], Path | None]


class PermissionHandler:
    """Answers the questions of Claude during one message."""

    def __init__(
        self,
        view: PermissionView,
        runner: ClaudeRunner,
        shared: Shared,
        stats: StatsRecorder,
        links: PermissionLinks,
    ) -> None:
        self._view = view
        self._runner = runner
        self._settings = shared.settings
        self._files = shared.files
        self._security = shared.security
        self._stats = stats
        self._links = links
        self._allowed: set[str] = set()  # rules always allowed during this message
        self._expired: set[str] = set()  # questions the CLI stopped waiting for (hook channel)

    def start_message(self) -> None:
        """A new message: what was allowed or expired for the last one is forgotten."""
        self._allowed = set()
        self._expired = set()

    def request(self, request: PermissionRequest) -> None:
        """Claude asks before running a tool: a rule allowed earlier in this message, else ask.
        Its structured questions have a dialog of their own. In the mode Plan the plan and the
        questions are refused for the user when the setting says so (``refuse_plan_mode_exit``)."""
        refusal = self._plan_mode_refusal(request)
        if refusal is not None:
            self._refuse(request, *refusal)
            return
        if is_question(request):
            questions = parse_questions(request)
            if questions:
                self._questions(request, questions)
                return
        rule = request.suggested_rule
        if rule and rule in self._allowed:
            decision = Decision(Choice.ALLOW)
        else:
            if is_plan_request(request):
                self._links.say(Announce.PLAN_PROPOSED)
            else:
                self._links.say(Announce.PERMISSION_ASKED, tool=request.tool_name)
            with self._stats.waiting():
                decision = self._view.ask_permission(request, self._wait_text())
            if request.request_id in self._expired:
                return  # the CLI stopped waiting while the question was open: nothing to answer
        try:
            if decision.choice is Choice.DENY:
                self._runner.deny(request, decision.denial_message())
                self._view.say(Announce.PERMISSION_REFUSED, tool=request.tool_name)
                return
            if decision.choice is Choice.ALLOW_ALWAYS and rule:
                self._remember_always_allowed(rule)
            self._runner.allow(request)
            self._view.say(Announce.PERMISSION_GRANTED, tool=request.tool_name)
        except RunnerError as error:
            self._view.show_error(_("Claude could not be answered.\n{error}").format(error=error))

    def expired(self, expired: PermissionExpired) -> None:
        """The CLI stopped waiting and denied the tool: close the question if it is still open."""
        self._expired.add(expired.request_id)
        self._view.close_permission(expired.request_id)
        self._links.say(Announce.PERMISSION_EXPIRED, tool=expired.tool_name)

    # -- inside ---------------------------------------------------------------------------

    def _plan_mode_refusal(self, request: PermissionRequest) -> tuple[str, Announce] | None:
        """What Claude is told and what the user hears when the setting refuses this request: its
        plan (it asks to leave the mode Plan), or its structured questions while the agent of the
        message is in the mode Plan. None when the request is not refused."""
        if not self._settings.refuse_plan_mode_exit:
            return None
        if is_plan_request(request):
            return PLAN_REFUSAL, Announce.PLAN_REFUSED
        if is_question(request) and self._links.turn_mode() == "plan":
            return PLAN_QUESTIONS_REFUSAL, Announce.PLAN_QUESTIONS_REFUSED
        return None

    def _refuse(self, request: PermissionRequest, message: str, announce: Announce) -> None:
        """Tell Claude why the request is refused, and the user that it was."""
        try:
            self._runner.deny(request, message)
        except RunnerError as error:
            self._view.show_error(_("Claude could not be answered.\n{error}").format(error=error))
            return
        self._links.say(announce)

    def _questions(self, request: PermissionRequest, questions: list[Question]) -> None:
        """Claude has questions: ask them, give the answers back (or refuse to answer)."""
        self._links.say(Announce.QUESTION_ASKED)
        with self._stats.waiting():
            answers = self._view.ask_questions(questions)
        if request.request_id in self._expired:
            return  # the CLI stopped waiting while the questions were open
        try:
            if answers is None:
                self._runner.deny(request, Decision(Choice.DENY).denial_message())
                self._view.say(Announce.PERMISSION_REFUSED, tool=request.tool_name)
                return
            self._runner.answer_questions(request, answers)
            self._links.say(Announce.QUESTION_ANSWERED)
        except RunnerError as error:
            self._view.show_error(_("Claude could not be answered.\n{error}").format(error=error))

    def _wait_text(self) -> str:
        """With the hook channel the CLI stops waiting after a while: say when."""
        if self._runner.permission_channel != HOOK:
            return ""
        return hook_wait_text(datetime.now(), self._runner.hook_timeout_seconds // 60)

    def _remember_always_allowed(self, rule: str) -> None:
        """Write the rule in the personal settings file, and keep it for the rest of the message."""
        self._allowed.add(rule)
        workspace = self._links.workspace()
        if workspace is None:
            return
        try:
            self._files.allow_always(
                workspace, rule, self._security.guard if self._security is not None else None
            )
        except ClaudeSettingsError as error:
            if isinstance(error, ExternalChangeError) and self._security is not None:
                self._security.refused(error)  # the user decides what to do with the change
            self._view.show_error(_("The rule could not be saved.\n{error}").format(error=error))

"""The wx side of a message sent to Claude: the view of ``presenters/run_presenter.py``."""

from collections.abc import Callable

import wx

from wxclaude.core.claude.events import PermissionRequest, RunEvent
from wxclaude.core.claude.permissions import Decision
from wxclaude.core.claude.questions import Question
from wxclaude.core.conversation.messages import Message
from wxclaude.core.speech.announcements import Announce
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.permission_dialog import PermissionDialog
from wxclaude.ui.question_dialog import QuestionDialog


class WxRunView:
    """Shows a run in the conversation view and the status bar, asks with the permission dialog.

    ``parent`` is the window of the dialogs.
    """

    def __init__(self, parent: wx.Window, view: ConversationView, feedback: Feedback) -> None:
        self._parent = parent
        self._view = view
        self._feedback = feedback
        self._open_question: tuple[PermissionRequest, wx.Dialog] | None = None

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        """Hand the event over to the interface thread."""
        wx.CallAfter(function, event)

    def append_message(self, message: Message) -> None:
        self._view.append_message(message)

    def show_session(self, messages: list[Message]) -> None:
        """Show the messages of the session file if they differ from the view; the caret stays."""
        view = self._view
        if view.shows(messages):
            view.adopt_details(messages)  # the messages shown live have no tools yet
        else:
            view.replace_messages(messages)

    def ask_permission(self, request: PermissionRequest, wait_text: str = "") -> Decision:
        """Show the question; closing the dialog without answering is a denial."""
        with PermissionDialog(self._parent, request, wait_text) as dialog:
            self._open_question = (request, dialog)
            try:
                self._feedback.modal(dialog)
            finally:
                self._open_question = None
            decision: Decision = dialog.decision
        return decision

    def ask_questions(self, questions: list[Question]) -> dict[str, list[str]] | None:
        """Show the questions of Claude; None if the user refused to answer."""
        with QuestionDialog(self._parent, questions) as dialog:
            self._feedback.modal(dialog)
            if not dialog.sent:
                return None
            answers: dict[str, list[str]] = dialog.answers
        return answers

    def close_permission(self, request_id: str) -> None:
        question = self._open_question
        if question is not None and question[0].request_id == request_id:
            question[1].EndModal(wx.ID_NO)

    def say(self, announce: Announce, **values: object) -> None:
        self._feedback.say(announce, **values)

    def set_status(self, text: str) -> None:
        self._feedback.set_status(text)

    def show_step(self, text: str) -> None:
        self._feedback.show_step(text)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)

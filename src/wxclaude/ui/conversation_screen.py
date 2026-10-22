"""The wx side of the current conversation: the view of ``presenters/conversation_presenter.py``
(the conversation view, the prompt field, the title of the window and the dialogs)."""

import wx

from wxclaude.core.config.agents import Agent
from wxclaude.core.conversation.messages import Message
from wxclaude.core.speech.announcements import Announce
from wxclaude.ui.agent_dialog import AgentDialog
from wxclaude.ui.conversation_name_dialog import ConversationNameDialog
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback


class WxConversationScreen:
    """What the main window shows of the conversation; ``frame`` is the window of the dialogs."""

    def __init__(
        self,
        frame: wx.Frame,
        view: ConversationView,
        prompt: wx.TextCtrl,
        feedback: Feedback,
    ) -> None:
        self._frame = frame
        self._view = view
        self._prompt = prompt
        self._feedback = feedback

    def ask_name(self, title: str, proposal: str) -> str | None:
        with ConversationNameDialog(self._frame, title, proposal) as dialog:
            return dialog.name if self._feedback.modal(dialog) == wx.ID_OK else None

    def ask_agent(self, agent: Agent) -> Agent | None:
        with AgentDialog(self._frame, agent) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return None
            chosen: Agent = dialog.agent
        return chosen

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        return self._feedback.choose(title, prompt, labels)

    def show_messages(self, messages: list[Message]) -> None:
        self._view.set_messages(messages)

    def clear_messages(self) -> None:
        self._view.clear_messages()

    def shown_count(self) -> int:
        return len(self._view.document.spans)

    def focus_last_prompt(self) -> None:
        self._view.focus_last_prompt()

    def clear_prompt(self) -> None:
        self._prompt.Clear()

    def focus_prompt(self) -> None:
        self._prompt.SetFocus()

    def show_title(self, title: str) -> None:
        self._frame.SetTitle(title)

    def say(self, announce: Announce, **values: object) -> None:
        self._feedback.say(announce, **values)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)

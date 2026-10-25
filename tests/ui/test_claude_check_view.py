import pytest

from wxclaude.ui.claude_check_view import WxClaudeCheckView

pytestmark = pytest.mark.unit


class FakeFeedback:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.status: list[str] = []
        self.asked: list[tuple[str, str, str, str]] = []

    def set_status(self, text: str) -> None:
        self.status.append(text)

    def confirm(self, title: str, message: str, yes_label: str = "", no_label: str = "") -> bool:
        self.asked.append((title, message, yes_label, no_label))
        return self.answer


def test_the_message_tells_what_to_do_and_yes_opens_the_preferences() -> None:
    feedback, opened = FakeFeedback(True), []
    view = WxClaudeCheckView(feedback, lambda: opened.append("preferences"))  # type: ignore[arg-type]
    view.claude_not_found()
    ((title, message, yes, no),) = feedback.asked
    assert title == "Claude Code not found"
    assert "Claude Code was not found on this computer." in message
    assert "File > Preferences > Claude" in message
    assert (yes, no) == ("&Open the Preferences", "&Close")
    assert opened == ["preferences"]


def test_no_leaves_the_preferences_closed() -> None:
    feedback, opened = FakeFeedback(False), []
    WxClaudeCheckView(feedback, lambda: opened.append("preferences")).claude_not_found()  # type: ignore[arg-type]
    assert opened == []


def test_the_status_goes_to_the_status_bar() -> None:
    feedback = FakeFeedback(False)
    WxClaudeCheckView(feedback, lambda: None).set_status("Claude Code not found")  # type: ignore[arg-type]
    assert feedback.status == ["Claude Code not found"]

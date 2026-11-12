import pytest

from wxclaude.ui.claude_check_view import WxClaudeCheckView

pytestmark = pytest.mark.ui


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


def _view(answer: bool) -> tuple[WxClaudeCheckView, FakeFeedback, list[str]]:
    feedback, opened = FakeFeedback(answer), []
    view = WxClaudeCheckView(
        feedback,  # type: ignore[arg-type]
        lambda: opened.append("preferences"),
        lambda: opened.append("sign in"),
    )
    return view, feedback, opened


def test_the_message_tells_what_to_do_and_yes_opens_the_preferences() -> None:
    view, feedback, opened = _view(True)
    view.claude_not_found()
    ((title, message, yes, no),) = feedback.asked
    assert title == "Claude Code not found"
    assert "Claude Code was not found on this computer." in message
    assert "File > Preferences > Claude" in message
    assert (yes, no) == ("&Open the Preferences", "&Close")
    assert opened == ["preferences"]


def test_no_leaves_the_preferences_closed() -> None:
    view, _feedback, opened = _view(False)
    view.claude_not_found()
    assert opened == []


def test_the_message_about_the_login_says_what_to_do_and_yes_opens_the_sign_in() -> None:
    view, feedback, opened = _view(True)
    view.not_logged_in()
    ((title, message, yes, no),) = feedback.asked
    assert title == "Not logged in to Claude Code"
    assert "not logged in" in message
    assert "Tools > Sign in to Claude…" in message  # the way to do it later
    assert (yes, no) == ("&Sign in…", "&Close")
    assert opened == ["sign in"]


def test_no_leaves_the_sign_in_closed() -> None:
    view, _feedback, opened = _view(False)
    view.not_logged_in()
    assert opened == []


def test_the_status_goes_to_the_status_bar() -> None:
    view, feedback, _opened = _view(False)
    view.set_status("Claude Code not found")
    assert feedback.status == ["Claude Code not found"]

import sys
import threading
from pathlib import Path

import pytest

from wxclaude.core.claude.auth import ClaudeLogin, LoginEnded, LoginEvent, LoginUrl
from wxclaude.core.errors import ClaudeLoginError

pytestmark = pytest.mark.unit

SCRIPT = """
import sys, time
args = sys.argv[1:]
mode = open(sys.argv[0] + ".mode").read().strip()
open(sys.argv[0] + ".args", "w").write(" ".join(args))
print("Opening browser to sign in...", flush=True)
print("If the browser didn't open, visit: https://claude.example/authorize?code=true", flush=True)
sys.stdout.write("Paste code here if prompted > ")
sys.stdout.flush()
if mode == "slow":
    time.sleep(60)
elif mode == "fail":
    print("Login failed.", file=sys.stderr)
    sys.exit(1)
else:
    print("Login successful.")
"""


def _fake(tmp_path: Path, mode: str) -> list[str]:
    script = tmp_path / "fake_claude.py"
    script.write_text(SCRIPT, encoding="utf-8")
    Path(str(script) + ".mode").write_text(mode, encoding="utf-8")
    return [sys.executable, str(script)]


def _run(login: ClaudeLogin, email: str = "") -> list[LoginEvent]:
    events: list[LoginEvent] = []
    ended = threading.Event()

    def on_event(event: LoginEvent) -> None:
        events.append(event)
        if isinstance(event, LoginEnded):
            ended.set()

    login.start(on_event, email)
    assert ended.wait(20)
    return events


def test_a_sign_in_that_works_gives_the_address_then_ends_well(tmp_path: Path) -> None:
    events = _run(ClaudeLogin(_fake(tmp_path, "ok")))
    assert events[0] == LoginUrl("https://claude.example/authorize?code=true")
    ended = events[-1]
    assert isinstance(ended, LoginEnded)
    assert ended.succeeded
    assert not ended.cancelled
    assert "Login successful." in ended.output


def test_only_the_subscription_sign_in_is_asked_for(tmp_path: Path) -> None:
    command = _fake(tmp_path, "ok")
    _run(ClaudeLogin(command))
    assert Path(command[1] + ".args").read_text(encoding="utf-8") == "auth login --claudeai"


def test_the_address_of_the_user_is_given_to_the_command(tmp_path: Path) -> None:
    command = _fake(tmp_path, "ok")
    _run(ClaudeLogin(command), email="  someone@example.com ")
    args = Path(command[1] + ".args").read_text(encoding="utf-8")
    assert args == "auth login --claudeai --email someone@example.com"


def test_a_sign_in_that_fails_says_what_was_printed(tmp_path: Path) -> None:
    ended = _run(ClaudeLogin(_fake(tmp_path, "fail")))[-1]
    assert isinstance(ended, LoginEnded)
    assert not ended.succeeded
    assert not ended.cancelled
    assert "Login failed." in ended.output


def test_a_cancelled_sign_in_ends_and_is_not_a_success(tmp_path: Path) -> None:
    login = ClaudeLogin(_fake(tmp_path, "slow"))
    seen = threading.Event()
    ended = threading.Event()
    events: list[LoginEvent] = []

    def on_event(event: LoginEvent) -> None:
        events.append(event)
        if isinstance(event, LoginUrl):
            seen.set()
        else:
            ended.set()

    login.start(on_event)
    assert seen.wait(20)
    assert login.is_running
    login.cancel()
    assert ended.wait(20)
    last = events[-1]
    assert isinstance(last, LoginEnded)
    assert last.cancelled
    assert not last.succeeded
    assert not login.is_running


def test_a_second_sign_in_is_refused_while_one_runs(tmp_path: Path) -> None:
    login = ClaudeLogin(_fake(tmp_path, "slow"))
    seen = threading.Event()
    login.start(lambda event: seen.set() if isinstance(event, LoginUrl) else None)
    assert seen.wait(20)
    try:
        with pytest.raises(ClaudeLoginError):
            login.start(lambda _event: None)
    finally:
        login.cancel()


def test_a_missing_program_is_an_error_of_sign_in(tmp_path: Path) -> None:
    with pytest.raises(ClaudeLoginError, match="does not exist"):
        ClaudeLogin(claude_path=str(tmp_path / "missing.exe")).start(lambda _event: None)
    with pytest.raises(ClaudeLoginError, match="Cannot start"):
        ClaudeLogin([str(tmp_path / "nothing.exe")]).start(lambda _event: None)

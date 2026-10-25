import sys
from pathlib import Path

import pytest

from wxclaude.core.claude import status as status_module
from wxclaude.core.claude.status import ClaudeStatus, describe_status, read_status

pytestmark = pytest.mark.unit

SCRIPT = """
import sys, time
args = sys.argv[1:]
if args == ["--version"]:
    print("2.1.286 (Claude Code)")
elif args == ["auth", "status"]:
    mode = open(sys.argv[0] + ".mode").read().strip()
    if mode == "in":
        print('{"loggedIn": true, "authMethod": "claude.ai", "subscriptionType": "pro", '
              '"email": "someone@example.com", "orgName": "Secret"}')
    elif mode == "out":
        print('{"loggedIn": false, "authMethod": "none"}')
        sys.exit(1)
    elif mode == "slow":
        time.sleep(30)
    else:
        print("not json")
"""


def _fake(tmp_path: Path, mode: str) -> list[str]:
    script = tmp_path / "fake_claude.py"
    script.write_text(SCRIPT, encoding="utf-8")
    Path(str(script) + ".mode").write_text(mode, encoding="utf-8")
    return [sys.executable, str(script)]


def test_a_logged_in_claude_gives_its_version_and_connection(tmp_path: Path) -> None:
    status = read_status(command=_fake(tmp_path, "in"))
    assert status == ClaudeStatus(
        found=True,
        path=sys.executable,
        version="2.1.286",
        logged_in=True,
        auth_method="claude.ai",
        subscription="pro",
    )
    text = describe_status(status)
    assert "Version: 2.1.286" in text
    assert "Connection: logged in (claude.ai, pro)" in text
    assert "someone@example.com" not in text  # the address is never read
    assert "Secret" not in text


def test_a_claude_that_is_not_logged_in_says_so(tmp_path: Path) -> None:
    status = read_status(command=_fake(tmp_path, "out"))
    assert status.found
    assert status.logged_in is False
    assert "Connection: not logged in" in describe_status(status)


def test_an_answer_that_is_not_json_leaves_the_connection_unknown(tmp_path: Path) -> None:
    status = read_status(command=_fake(tmp_path, "garbage"))
    assert status.version == "2.1.286"
    assert status.logged_in is None
    assert "Connection: unknown" in describe_status(status)


def test_a_claude_that_does_not_answer_in_time_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(status_module, "_TIMEOUT_SECONDS", 1)
    status = read_status(command=_fake(tmp_path, "slow"))
    assert status.found
    assert status.problem
    assert status.logged_in is None
    assert status.problem in describe_status(status)


def test_a_program_that_cannot_be_started_is_reported(tmp_path: Path) -> None:
    status = read_status(command=[str(tmp_path / "nothing.exe")])
    assert status.found  # a command was given, so it is not looked for
    assert status.problem


def test_a_missing_claude_is_said_with_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    status = read_status(str(tmp_path / "missing.exe"))
    assert not status.found
    text = describe_status(status)
    assert text.startswith("Claude Code was not found.")
    assert "does not exist" in text
    monkeypatch.setattr("wxclaude.core.claude.runner.shutil.which", lambda _name: None)
    assert "not found in the PATH" in describe_status(read_status())


def test_the_description_of_a_found_claude_without_details() -> None:
    text = describe_status(ClaudeStatus(found=True, path="C:/x/claude.exe"))
    assert text == ("Claude Code found: C:/x/claude.exe\nVersion: unknown\nConnection: unknown")

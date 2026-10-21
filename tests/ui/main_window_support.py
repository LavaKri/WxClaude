"""What the tests of the main window share: settings, the fake runner, sessions, helpers.

The fixtures ``window`` and ``conversation`` are in ``conftest.py``.
"""

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import wx

from wxclaude.core.agents import Agent
from wxclaude.core.conversations import new_conversation_id
from wxclaude.core.runner import ClaudeRunner
from wxclaude.core.settings import Settings
from wxclaude.ui.main_window import MainWindow

FAKE = Path(__file__).resolve().parent.parent / "fakes" / "fake_claude.py"
OPUS = Agent(model="opus", effort="high", permission_mode="manual")


def _settings(store: Path | None = None) -> Settings:
    settings = Settings.load(store)
    settings.default_agent = OPUS
    settings.screen_reader_output = "none"  # UI Automation is tested on its own below
    return settings


def _runner() -> ClaudeRunner:
    return ClaudeRunner([sys.executable, str(FAKE)])


def _enabled(items: list[wx.MenuItem]) -> list[bool]:
    return [item.IsEnabled() for item in items]


def _session(
    claude_config: Path,
    workspace: Path,
    age: int = 0,
    prompt: str = "Hello",
    title: str = "",
    identifier: str = "",
    effort: str = "",
) -> str:
    """Write a session file of ``workspace``; ``age`` seconds old; return its identifier."""
    identifier = identifier or new_conversation_id()
    folder = claude_config / "projects" / "folder"
    folder.mkdir(parents=True, exist_ok=True)
    when = datetime.now(UTC) - timedelta(seconds=age)
    entries: list[dict[str, object]] = [
        {
            "type": "user",
            "cwd": str(workspace),
            "permissionMode": "plan",
            "uuid": "u",
            "timestamp": when.isoformat(),
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "assistant",
            "uuid": "a",
            "effort": effort or "low",
            "timestamp": when.isoformat(),
            "message": {
                "role": "assistant",
                "model": "claude-haiku-4-5",
                "content": [{"type": "text", "text": "Hi"}],
            },
        },
    ]
    if title:
        entries.append({"type": "custom-title", "customTitle": title})
    (folder / f"{identifier}.jsonl").write_text(
        "\n".join(json.dumps(entry) for entry in entries), encoding="utf-8"
    )
    return identifier


def _wait_until_idle(window: MainWindow, timeout: float = 30) -> None:
    """Let the events of the runner reach the window until Claude is done."""
    deadline = time.monotonic() + timeout
    while window._busy:
        assert time.monotonic() < deadline, "Claude did not finish"
        wx.Yield()
        time.sleep(0.02)
    wx.Yield()


class _Errors:
    def __init__(self, window: MainWindow) -> None:
        self.messages: list[str] = []
        window._show_error = self.messages.append  # type: ignore[method-assign]


def _use_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    log = tmp_path / "fake-log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    return log


def _send(window: MainWindow, text: str) -> None:
    window._prompt.SetValue(text)
    window.send_prompt(alternative=False)
    _wait_until_idle(window)

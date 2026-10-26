"""Signing in to Claude Code with its own command (``claude auth login``), without a terminal.

The CLI opens the browser by itself and ends by itself once the user has allowed it there (verified,
see ``docs/claude-cli.md``). It must stay alive until then: the browser comes back to a port it
listens on. Only the subscription sign-in (``--claudeai``) is started.
"""

import re
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import IO

from wxclaude.core.claude.runner import find_claude, kill_tree
from wxclaude.core.errors import ClaudeLoginError, ClaudeNotFoundError

_URL = re.compile(r"https://\S+")


@dataclass(frozen=True, slots=True)
class LoginUrl:
    """The address the CLI prints for a browser that did not open by itself."""

    url: str


@dataclass(frozen=True, slots=True)
class LoginEnded:
    """The command ended. ``succeeded`` is false when it was cancelled or failed; ``output`` is
    what it printed (for the error message)."""

    succeeded: bool
    cancelled: bool
    output: str


LoginEvent = LoginUrl | LoginEnded


class ClaudeLogin:
    """One sign-in at a time. ``command`` replaces the ``claude`` executable (tests)."""

    def __init__(self, command: Sequence[str] | None = None, claude_path: str = "") -> None:
        self._command = list(command) if command is not None else None
        self.claude_path = claude_path  # the claude executable chosen by hand; '' looks in the PATH
        self._process: subprocess.Popen[str] | None = None
        self._cancelled = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None

    def start(self, on_event: Callable[[LoginEvent], None], email: str = "") -> None:
        """Start the sign-in; ``on_event`` is called from a worker thread.

        ``email`` is put in the field of the sign-in page when it is not empty. Raises
        ``ClaudeLoginError`` if the program is not found or cannot be started, or if a sign-in is
        already running.
        """
        try:
            command = self._command if self._command is not None else find_claude(self.claude_path)
        except ClaudeNotFoundError as error:
            raise ClaudeLoginError(str(error)) from error
        argv = [*command, "auth", "login", "--claudeai"]
        if email.strip():
            argv += ["--email", email.strip()]
        with self._lock:
            if self._process is not None:
                raise ClaudeLoginError("A sign-in is already running.")
            try:
                process = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                raise ClaudeLoginError(f"Cannot start {argv[0]}: {error}") from error
            self._process = process
            self._cancelled = False
        threading.Thread(target=self._watch, args=(process, on_event), daemon=True).start()

    def cancel(self) -> None:
        """End the running sign-in; its ``LoginEnded`` says it was cancelled."""
        with self._lock:
            process = self._process
            if process is None:
                return
            self._cancelled = True
        kill_tree(process)

    def _watch(
        self, process: subprocess.Popen[str], on_event: Callable[[LoginEvent], None]
    ) -> None:
        output = _read_lines(process.stdout, on_event)
        exit_code = process.wait()
        with self._lock:
            cancelled = self._cancelled
            self._process = None
        on_event(LoginEnded(exit_code == 0 and not cancelled, cancelled, output))


def _read_lines(stream: IO[str] | None, on_event: Callable[[LoginEvent], None]) -> str:
    """Pass on the first address printed; give back everything that was printed."""
    lines: list[str] = []
    told = False
    for line in stream or ():
        lines.append(line)
        found = _URL.search(line)
        if found and not told:
            told = True
            on_event(LoginUrl(found.group()))
    return "".join(lines).strip()

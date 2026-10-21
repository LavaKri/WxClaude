"""Running ``claude -p`` for one message and reporting what it does.

One process per message. Its input is ``stream-json``: the prompt is one JSON line, and stdin stays
open while Claude works so the answers to its permission questions can be written (the CLI is
started with ``--permission-prompt-tool stdio``); stdin is closed when the result line has been
read, which ends the process. Three threads read and supervise it, so the interface never waits:
one reads stdout (the ``stream-json`` lines), one reads stderr, and one writes the prompt, waits for
the end of the process and sends the last event (``TurnEnded``). The callback ``on_event`` is called
from those threads; the interface must hand the event over to its own thread (``wx.CallAfter``).
This module never imports ``wx``.
"""

import json
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from wxclaude.core.agents import Agent
from wxclaude.core.errors import ClaudeNotFoundError, RunnerError, StreamParseError
from wxclaude.core.events import PermissionRequest, RunEvent, TurnEnded, TurnResult
from wxclaude.core.stream import parse_stream_line

_KILL_WAIT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class RunRequest:
    """One message to send: the prompt, the agent, and the conversation it belongs to.

    ``resume`` is False for the first message of a conversation (the session is created with
    ``--session-id``) and True afterwards (``--resume``).
    """

    prompt: str
    agent: Agent
    session_id: str
    resume: bool
    cwd: Path


def build_arguments(request: RunRequest) -> list[str]:
    """The arguments of ``claude`` for ``request`` (the prompt goes through stdin)."""
    agent = request.agent
    if not (agent.model and agent.effort and agent.permission_mode):
        raise RunnerError("The agent must have a model, an effort and a permission mode.")
    return [
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-prompt-tool",
        "stdio",
        "--model",
        agent.model,
        "--effort",
        agent.effort,
        "--permission-mode",
        agent.permission_mode,
        "--resume" if request.resume else "--session-id",
        request.session_id,
    ]


def find_claude(path: str = "") -> list[str]:
    """The command that starts the CLI; raises ``ClaudeNotFoundError``.

    Without ``path`` the ``claude`` command is looked for in the PATH; with it, that file is used.
    """
    if path:
        if not Path(path).is_file():
            raise ClaudeNotFoundError(f"The file {path} does not exist.")
        return [path]
    found = shutil.which("claude")
    if found is None:
        raise ClaudeNotFoundError("The claude command was not found in the PATH.")
    return [found]


class _Stdin:
    """The standard input of the process: JSON lines written from several threads, closed once."""

    def __init__(self, stream: IO[str] | None) -> None:
        self._stream = stream
        self._lock = threading.Lock()
        self._closed = stream is None

    def write(self, entry: dict[str, object]) -> None:
        """Write ``entry`` as a line; raises ``RunnerError`` if the input is closed or broken."""
        with self._lock:
            if self._closed or self._stream is None:
                raise RunnerError("Claude is not waiting for an answer.")
            try:
                self._stream.write(json.dumps(entry) + "\n")
                self._stream.flush()
            except OSError as error:
                raise RunnerError(f"Claude cannot be reached: {error}") from error

    def close(self) -> None:
        """Close the input (the CLI then ends); harmless the second time or if it is broken."""
        with self._lock:
            if self._closed or self._stream is None:
                return
            self._closed = True
            try:
                self._stream.close()
            except OSError:
                return  # the process is gone: there is nothing left to close


@dataclass(slots=True)
class _Run:
    """What one message needs while it runs: its process, what it says and what it prints."""

    process: subprocess.Popen[str]
    stdin: _Stdin
    prompt: str
    on_event: Callable[[RunEvent], None]
    diagnostics: list[str] = field(default_factory=list)  # lines that are not stream lines
    stderr_lines: list[str] = field(default_factory=list)
    readers: list[threading.Thread] = field(default_factory=list)


class ClaudeRunner:
    """Runs one message at a time. ``command`` replaces the ``claude`` executable (tests)."""

    def __init__(self, command: Sequence[str] | None = None) -> None:
        self._command = list(command) if command is not None else None
        self.claude_path = ""  # the claude executable chosen by hand; '' looks in the PATH
        self._process: subprocess.Popen[str] | None = None
        self._stdin: _Stdin | None = None
        self._interrupted = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None

    def start(self, request: RunRequest, on_event: Callable[[RunEvent], None]) -> None:
        """Start ``claude`` for ``request``; events then come through ``on_event``.

        Raises ``ClaudeNotFoundError`` or ``RunnerError`` if it cannot be started, or if a
        message is already running.
        """
        command = self._command if self._command is not None else find_claude(self.claude_path)
        argv = [*command, *build_arguments(request)]
        with self._lock:
            if self._process is not None:
                raise RunnerError("Claude is already answering.")
            try:
                process = subprocess.Popen(
                    argv,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=request.cwd,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                raise RunnerError(f"Cannot start {argv[0]}: {error}") from error
            self._process = process
            self._stdin = stdin = _Stdin(process.stdin)
            self._interrupted = False
        run = _Run(process, stdin, request.prompt, on_event)
        run.readers = [
            threading.Thread(
                target=self._read_stdout,
                args=(process.stdout, stdin, on_event, run.diagnostics),
                daemon=True,
            ),
            threading.Thread(
                target=self._read_stderr, args=(process.stderr, run.stderr_lines), daemon=True
            ),
        ]
        for reader in run.readers:
            reader.start()
        threading.Thread(target=self._supervise, args=(run,), daemon=True).start()

    def allow(self, request: PermissionRequest) -> None:
        """Let the tool of ``request`` run. Raises ``RunnerError`` if Claude is no longer there."""
        self._answer(request, {"behavior": "allow", "updatedInput": request.input})

    def deny(self, request: PermissionRequest, message: str) -> None:
        """Refuse the tool of ``request``; ``message`` is what Claude is told (the explanation)."""
        self._answer(request, {"behavior": "deny", "message": message})

    def _answer(self, request: PermissionRequest, body: dict[str, object]) -> None:
        with self._lock:
            stdin = self._stdin
        if stdin is None:
            raise RunnerError("Claude is not waiting for an answer.")
        stdin.write(
            {
                "type": "control_response",
                "response": {
                    "subtype": "success",
                    "request_id": request.request_id,
                    "response": body,
                },
            }
        )

    def interrupt(self) -> None:
        """Stop the running message (nothing happens if none runs)."""
        with self._lock:
            process = self._process
            if process is None:
                return
            self._interrupted = True
        _kill_tree(process)

    @staticmethod
    def _read_stdout(
        stream: IO[str] | None,
        stdin: _Stdin,
        on_event: Callable[[RunEvent], None],
        diagnostics: list[str],
    ) -> None:
        for line in stream or ():
            if not line.strip():
                continue
            try:
                events = parse_stream_line(line)
            except StreamParseError as error:
                diagnostics.append(str(error))
                continue
            for event in events:
                on_event(event)
                if isinstance(event, TurnResult):
                    stdin.close()  # nothing more to say: the CLI can end

    @staticmethod
    def _read_stderr(stream: IO[str] | None, lines: list[str]) -> None:
        lines.extend(stream or ())

    def _supervise(self, run: _Run) -> None:
        try:
            run.stdin.write({"type": "user", "message": {"role": "user", "content": run.prompt}})
        except RunnerError as error:  # the process ended before reading the prompt
            run.diagnostics.append(str(error))
        for reader in run.readers:
            reader.join()
        run.stdin.close()
        exit_code = run.process.wait()
        with self._lock:
            interrupted = self._interrupted
            self._process = None
            self._stdin = None
        stderr = "".join(run.stderr_lines).strip()
        run.on_event(TurnEnded(exit_code, interrupted, stderr, run.diagnostics))


def _kill_tree(process: subprocess.Popen[str]) -> None:
    """End the process and the processes it started."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=_KILL_WAIT_SECONDS,
            )
        except OSError, subprocess.TimeoutExpired:
            process.kill()
    else:
        process.terminate()

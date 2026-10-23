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
from datetime import datetime
from pathlib import Path
from typing import IO

from wxclaude.core.claude.events import (
    GaugesRead,
    PermissionRequest,
    RateWindow,
    RunEvent,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.permission_channel import (
    DEFAULT_HOOK_TIMEOUT_SECONDS,
    STDIO,
    PermissionChannel,
    make_channel,
)
from wxclaude.core.claude.process_input import ProcessInput
from wxclaude.core.claude.stream import parse_stream_line
from wxclaude.core.claude.usage_text import parse_usage
from wxclaude.core.config.agents import Agent
from wxclaude.core.errors import ClaudeNotFoundError, RunnerError, StreamParseError

_KILL_WAIT_SECONDS = 5
_RENAME_WAIT_SECONDS = 30
_USAGE_WAIT_SECONDS = 15  # ``/usage`` answers in under a second: longer means the CLI is stuck


@dataclass(frozen=True, slots=True)
class RunRequest:
    """One message to send: the prompt, the agent, and the conversation it belongs to.

    ``resume`` is False for the first message of a conversation (the session is created with
    ``--session-id``) and True afterwards (``--resume``). ``name`` is the name of the session, given
    with ``--name`` to the first message (a later rename goes through ``rename_session``).
    """

    prompt: str
    agent: Agent
    session_id: str
    resume: bool
    cwd: Path
    name: str = ""


def build_arguments(request: RunRequest, channel: PermissionChannel) -> list[str]:
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
        *channel.arguments(),
        "--model",
        agent.model,
        "--effort",
        agent.effort,
        "--permission-mode",
        agent.permission_mode,
        "--resume" if request.resume else "--session-id",
        request.session_id,
        *(["--name", request.name] if request.name and not request.resume else []),
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


@dataclass(slots=True)
class _Run:
    """What one message needs while it runs: its process, what it says and what it prints."""

    process: subprocess.Popen[str]
    stdin: ProcessInput
    channel: PermissionChannel
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
        self.permission_channel = STDIO  # how the permission questions travel, per message
        self.hook_timeout_seconds = DEFAULT_HOOK_TIMEOUT_SECONDS  # the CLI's wait, hook channel
        self._process: subprocess.Popen[str] | None = None
        self._channel: PermissionChannel | None = None
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
        channel = make_channel(self.permission_channel, on_event, self.hook_timeout_seconds)
        try:
            process, stdin = self._spawn(command, request, channel)
        except RunnerError:
            channel.close()  # a hook server was started for nothing
            raise
        run = _Run(process, stdin, channel, request.prompt, on_event)
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

    def _spawn(
        self, command: Sequence[str], request: RunRequest, channel: PermissionChannel
    ) -> tuple[subprocess.Popen[str], ProcessInput]:
        """Start the process and give its input to the channel."""
        argv = [*command, *build_arguments(request, channel)]
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
            self._channel = channel
            stdin = ProcessInput(process.stdin)
            channel.bind(stdin)
            self._interrupted = False
        return process, stdin

    def rename_session(self, session_id: str, name: str, cwd: Path) -> None:
        """Give the session ``session_id`` of the folder ``cwd`` the name ``name``.

        It is the ``/rename`` command of the CLI, run as the prompt of ``claude -p --resume``: the
        CLI writes the name in the session file itself, sends nothing to the model and answers at
        once. Raises ``ClaudeNotFoundError`` or ``RunnerError``.
        """
        command = self._command if self._command is not None else find_claude(self.claude_path)
        argv = [
            *command,
            "-p",
            f"/rename {name}",
            "--resume",
            session_id,
            "--output-format",
            "json",
        ]
        try:
            done = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                cwd=cwd,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_RENAME_WAIT_SECONDS,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as error:
            raise RunnerError(f"Cannot start {argv[0]}: {error}") from error
        except subprocess.TimeoutExpired as error:
            raise RunnerError("Claude did not answer in time.") from error
        reply = _last_json_object(done.stdout)
        if done.returncode != 0 or reply.get("is_error"):
            detail = str(
                reply.get("result") or done.stderr.strip() or f"exit code {done.returncode}"
            )
            raise RunnerError(detail)

    def read_usage(self, cwd: Path, on_event: Callable[[RunEvent], None]) -> None:
        """Read the gauges with the ``/usage`` command of the CLI, without waiting.

        ``claude -p /usage`` sends nothing to the model and answers at once; without a session
        file (``--no-session-persistence``) it adds no conversation to the user's list. The
        process is the running one (``interrupt`` stops it, no message can start meanwhile) and
        is killed after ``_USAGE_WAIT_SECONDS``. ``on_event`` receives one ``GaugesRead`` from a
        thread, with no windows when the reading failed for any reason. Raises
        ``ClaudeNotFoundError`` or ``RunnerError`` if the CLI cannot be started.
        """
        command = self._command if self._command is not None else find_claude(self.claude_path)
        argv = [*command, "-p", "/usage", "--no-session-persistence", "--output-format", "json"]
        with self._lock:
            if self._process is not None:
                raise RunnerError("Claude is already answering.")
            try:
                process = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                raise RunnerError(f"Cannot start {argv[0]}: {error}") from error
            self._process = process
            self._interrupted = False
        threading.Thread(target=self._finish_usage, args=(process, on_event), daemon=True).start()

    def _finish_usage(
        self, process: subprocess.Popen[str], on_event: Callable[[RunEvent], None]
    ) -> None:
        """Wait for ``/usage`` (at most ``_USAGE_WAIT_SECONDS``) and report the gauges it gave."""
        windows: tuple[RateWindow, ...] = ()
        try:
            stdout, _stderr = process.communicate(timeout=_USAGE_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            process.communicate()
        else:
            reply = _last_json_object(stdout)
            if process.returncode == 0 and not reply.get("is_error"):
                windows = parse_usage(str(reply.get("result") or ""), datetime.now())
        with self._lock:
            self._process = None
        on_event(GaugesRead(windows))

    def allow(self, request: PermissionRequest) -> None:
        """Let the tool of ``request`` run. Raises ``RunnerError`` if Claude is no longer there."""
        self._answer(request, {"behavior": "allow", "updatedInput": request.input})

    def deny(self, request: PermissionRequest, message: str) -> None:
        """Refuse the tool of ``request``; ``message`` is what Claude is told (the explanation)."""
        self._answer(request, {"behavior": "deny", "message": message})

    def _answer(self, request: PermissionRequest, body: dict[str, object]) -> None:
        with self._lock:
            channel = self._channel
        if channel is None:
            raise RunnerError("Claude is not waiting for an answer.")
        channel.answer(request.request_id, body)

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
        stdin: ProcessInput,
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
            self._channel = None
        run.channel.close()
        stderr = "".join(run.stderr_lines).strip()
        run.on_event(TurnEnded(exit_code, interrupted, stderr, run.diagnostics))


def _last_json_object(text: str) -> dict[str, object]:
    """The last line of ``text`` that is a JSON object ({} if there is none)."""
    for line in reversed(text.splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return {}


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

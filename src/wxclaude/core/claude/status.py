"""The state of Claude Code on this computer: found or not, its version, whether it is logged in.

Asked of the program itself (``claude --version`` and ``claude auth status``, see
``docs/claude-cli.md``), never from its files. The address and the organization that
``auth status`` also gives are not read.
"""

import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from wxclaude.core.claude.runner import find_claude
from wxclaude.core.errors import ClaudeNotFoundError
from wxclaude.i18n import _

_TIMEOUT_SECONDS = 20
_VERSION = re.compile(r"\d+(?:\.\d+)+")


@dataclass(frozen=True, slots=True)
class ClaudeStatus:
    """What was found out. ``logged_in`` is None when it could not be told; ``problem`` says what
    could not be read (or, without ``found``, why the program was not found)."""

    found: bool
    path: str = ""
    version: str = ""
    logged_in: bool | None = None
    auth_method: str = ""
    subscription: str = ""
    problem: str = ""


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def _parse_auth(output: str) -> tuple[bool | None, str, str]:
    """(logged in or None if unknown, method, subscription) from the JSON of ``auth status``."""
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None, "", ""
    if not isinstance(data, dict):
        return None, "", ""
    logged_in = data.get("loggedIn")
    return (
        logged_in if isinstance(logged_in, bool) else None,
        str(data.get("authMethod") or ""),
        str(data.get("subscriptionType") or ""),
    )


def read_status(path: str = "", command: Sequence[str] | None = None) -> ClaudeStatus:
    """Ask Claude Code its state. ``path`` is the file chosen by hand ('' looks in the PATH);
    ``command`` replaces the program (tests)."""
    try:
        base = list(command) if command is not None else find_claude(path)
    except ClaudeNotFoundError as error:
        return ClaudeStatus(found=False, problem=str(error))
    try:
        version_output = _run([*base, "--version"]).stdout
        auth_output = _run([*base, "auth", "status"]).stdout
    except (OSError, subprocess.TimeoutExpired) as error:
        return ClaudeStatus(found=True, path=base[0], problem=str(error))
    match = _VERSION.search(version_output)
    logged_in, method, subscription = _parse_auth(auth_output)
    return ClaudeStatus(
        found=True,
        path=base[0],
        version=match.group() if match else "",
        logged_in=logged_in,
        auth_method=method,
        subscription=subscription,
    )


def describe_status(status: ClaudeStatus) -> str:
    """The state as lines of text, for a read-only field."""
    if not status.found:
        lines = [_("Claude Code was not found.")]
        return "\n".join([*lines, status.problem] if status.problem else lines)
    lines = [_("Claude Code found: {path}").format(path=status.path)]
    if status.version:
        lines.append(_("Version: {version}").format(version=status.version))
    else:
        lines.append(_("Version: unknown"))
    if status.logged_in is True:
        details = ", ".join(part for part in (status.auth_method, status.subscription) if part)
        if details:
            lines.append(_("Connection: logged in ({details})").format(details=details))
        else:
            lines.append(_("Connection: logged in"))
    elif status.logged_in is False:
        lines.append(_("Connection: not logged in"))
    else:
        lines.append(_("Connection: unknown"))
    if status.problem:
        lines.append(status.problem)
    return "\n".join(lines)

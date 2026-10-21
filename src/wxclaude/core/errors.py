"""Exceptions raised by the application logic."""


class WxClaudeError(Exception):
    """Base class of all errors raised on purpose by WxClaude."""


class SettingsError(WxClaudeError):
    """The settings file cannot be read or written."""


class ExportError(WxClaudeError):
    """A conversation cannot be exported."""


class JsonStoreError(WxClaudeError):
    """A JSON file of the application cannot be written."""


class ClaudeSettingsError(WxClaudeError):
    """A settings file of Claude Code cannot be modified or written."""


class SessionReadError(WxClaudeError):
    """A session file of the Claude Code CLI cannot be read."""


class TaskReadError(WxClaudeError):
    """The folder holding the tasks of a session cannot be read."""


class ScreenReaderOutputError(WxClaudeError):
    """A message cannot be sent to the screen reader (or its output cannot be set up)."""


class ClaudeNotFoundError(WxClaudeError):
    """The ``claude`` command cannot be found."""


class RunnerError(WxClaudeError):
    """Claude cannot be started, or a request cannot be turned into a command."""


class StreamParseError(WxClaudeError):
    """A line of the ``stream-json`` output is not valid JSON."""

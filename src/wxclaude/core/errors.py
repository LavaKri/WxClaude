"""Exceptions raised by the application logic."""


class WxClaudeError(Exception):
    """Base class of all errors raised on purpose by WxClaude."""


class SettingsError(WxClaudeError):
    """The settings file cannot be read or written."""


class ExportError(WxClaudeError):
    """A conversation cannot be exported."""


class JsonStoreError(WxClaudeError):
    """A JSON file of the application cannot be written."""


class SessionReadError(WxClaudeError):
    """A session file of the Claude Code CLI cannot be read."""


class ScreenReaderOutputError(WxClaudeError):
    """A message cannot be sent to the screen reader (or its output cannot be set up)."""

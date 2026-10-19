"""Exceptions raised by the application logic."""


class WxClaudeError(Exception):
    """Base class of all errors raised on purpose by WxClaude."""


class SettingsError(WxClaudeError):
    """The settings file cannot be read or written."""

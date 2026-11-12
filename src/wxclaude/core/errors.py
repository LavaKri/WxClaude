"""Exceptions raised by the application logic."""


class WxClaudeError(Exception):
    """Base class of all errors raised on purpose by WxClaude."""


class SettingsError(WxClaudeError):
    """The settings file cannot be read or written."""


class ExportError(WxClaudeError):
    """A conversation cannot be exported."""


class HelpError(WxClaudeError):
    """The help page is missing or cannot be written."""


class JsonStoreError(WxClaudeError):
    """A JSON file of the application cannot be written."""


class ClaudeSettingsError(WxClaudeError):
    """A settings file of Claude Code cannot be modified or written."""


class WatchError(WxClaudeError):
    """A watched file of a workspace cannot be read, or its approved copy cannot be written."""


class KeyVaultError(WxClaudeError):
    """A key cannot be encrypted, or cannot be decrypted (another account, another computer)."""


class ProviderError(WxClaudeError):
    """A provider is not valid, or the one asked for cannot be changed or does not exist."""


class ModelListError(WxClaudeError):
    """The list of models of a provider cannot be fetched from its server; the message says why."""


class BalanceError(WxClaudeError):
    """The credit left with a provider cannot be asked; the message says why."""


class SessionReadError(WxClaudeError):
    """A session file of the Claude Code CLI cannot be read."""


class TaskReadError(WxClaudeError):
    """The folder holding the tasks of a session cannot be read."""


class PlanReadError(WxClaudeError):
    """The session file that names the plans of a conversation cannot be read."""


class ScreenReaderOutputError(WxClaudeError):
    """A message cannot be sent to the screen reader (or its output cannot be set up)."""


class ClaudeNotFoundError(WxClaudeError):
    """The ``claude`` command cannot be found."""


class RunnerError(WxClaudeError):
    """Claude cannot be started, or a request cannot be turned into a command."""


class ClaudeLoginError(WxClaudeError):
    """The sign-in of Claude Code cannot be started, or one is already running."""


class StreamParseError(WxClaudeError):
    """A line of the ``stream-json`` output is not valid JSON."""


class RemoteError(WxClaudeError):
    """The remote control cannot start (the pipe cannot be created, or the system has no pipes)."""


class RemoteRequestError(WxClaudeError):
    """A request of the remote control is refused; ``code`` is the error given to the client."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

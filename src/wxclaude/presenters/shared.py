"""What several presenters share: the settings, the usage of Claude and the files of Claude Code."""

from dataclasses import dataclass

from wxclaude.core.claude_files import ClaudeFiles
from wxclaude.core.settings import Settings
from wxclaude.core.usage import UsageTracker


@dataclass(frozen=True, slots=True)
class Shared:
    """The objects of the model the presenters of one window work on together."""

    settings: Settings
    usage: UsageTracker
    files: ClaudeFiles

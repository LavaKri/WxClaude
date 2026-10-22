"""What several presenters share: the settings, the usage of Claude and the files of Claude Code."""

from dataclasses import dataclass

from wxclaude.core.claude.claude_files import ClaudeFiles
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.settings import Settings


@dataclass(frozen=True, slots=True)
class Shared:
    """The objects of the model the presenters of one window work on together."""

    settings: Settings
    usage: UsageTracker
    files: ClaudeFiles

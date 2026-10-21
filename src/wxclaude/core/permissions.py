"""Permission questions of Claude: how a request is shown, and the answer given.

Claude asks before it runs a tool the permission mode does not allow (see ``docs/claude-cli.md``).
The user allows it once, always allows it (a rule remembered for the workspace and given to the CLI
with ``--allowedTools``), or denies it, with an explanation that Claude is told.
"""

import enum
import json
from dataclasses import dataclass

from wxclaude.core.events import PermissionRequest
from wxclaude.i18n import _

DEFAULT_DENIAL = "The user denied this action."


class Choice(enum.Enum):
    """What the user decided."""

    ALLOW = "allow"
    ALLOW_ALWAYS = "allow_always"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class Decision:
    """The answer to a permission question; ``explanation`` is only used when denying."""

    choice: Choice
    explanation: str = ""

    def denial_message(self) -> str:
        """What Claude is told when the tool is refused."""
        return self.explanation.strip() or DEFAULT_DENIAL


def _value_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def describe_request(request: PermissionRequest) -> str:
    """The request as lines of text for the dialog: the tool, what it is for, its arguments."""
    lines = [_("Tool: {tool}").format(tool=request.tool_name)]
    if request.description:
        lines.append(_("Description: {description}").format(description=request.description))
    if request.blocked_path:
        lines.append(_("Path: {path}").format(path=request.blocked_path))
    for name, value in request.input.items():
        if name == "description" and value == request.description:
            continue  # already said above
        lines.append(_("{name}: {value}").format(name=name, value=_value_text(value)))
    return "\n".join(lines)

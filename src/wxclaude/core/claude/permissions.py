"""Permission questions of Claude: how a request is shown, and the answer given.

Claude asks before it runs a tool the permission mode does not allow (see ``docs/claude-cli.md``).
The user allows it once, always allows it (a rule remembered for the workspace and given to the CLI
with ``--allowedTools``), or denies it, with an explanation that Claude is told.
"""

import enum
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from wxclaude.core.claude.events import PermissionRequest
from wxclaude.i18n import _

DEFAULT_DENIAL = "The user denied this action."
PLAN_TOOL = "ExitPlanMode"  # in the mode plan, Claude submits its plan by asking to leave it
PLAN_REFUSAL = (  # what Claude is told when the setting refuses to leave the mode plan for the user
    "The user does not approve plans through this tool. Stay in plan mode: present the plan in "
    "your answer and wait for the user to change the mode."
)
PLAN_QUESTIONS_REFUSAL = (  # the same setting, for the structured questions of the mode plan
    "The user does not answer structured questions in plan mode. Ask your questions in your "
    "answer, as plain text, and wait for the reply."
)


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


def hook_wait_text(now: datetime, minutes: int) -> str:
    """What the dialog says of the waiting time of the hook channel: the time at which the CLI
    stops waiting and denies the tool, and the time it waits (``13:59 (10 min)``)."""
    deadline = now + timedelta(minutes=minutes)
    return _("Without an answer by {time} ({minutes} min), Claude denies the tool.").format(
        time=deadline.strftime("%H:%M"), minutes=minutes
    )


def is_plan_request(request: PermissionRequest) -> bool:
    """Is the request the proposal of a plan (and not the permission to run a tool)?"""
    return request.tool_name == PLAN_TOOL and isinstance(request.input.get("plan"), str)


def _describe_plan(request: PermissionRequest) -> str:
    """The plan as text for the dialog: what to answer, then the plan as Claude wrote it."""
    lines = [
        _("Claude proposes this plan. Allow approves it; Deny asks for changes (explain below)."),
        "",
        str(request.input["plan"]).strip(),
    ]
    for name, value in request.input.items():
        if name != "plan":
            lines.append(_("{name}: {value}").format(name=name, value=_value_text(value)))
    return "\n".join(lines)


def describe_request(request: PermissionRequest) -> str:
    """The request as lines of text for the dialog: the tool, what it is for, its arguments.

    A plan is shown as its own text (see ``is_plan_request``).
    """
    if is_plan_request(request):
        return _describe_plan(request)
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

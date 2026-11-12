"""The restricted launch of a folder that is not trusted (``docs/security.md``, "Restricted mode").

Three elements: the CLI reads only the settings of the user (``RESTRICTED_ARGUMENTS``), so no hook,
``env`` or ``.mcp.json`` server of the project runs; the ``deny`` and ``ask`` rules of the two
project files are still given, in the inline settings (``restricted_settings``); and the permission
mode of the message is ``manual`` unless the agent's own mode is already stricter (``plan``,
``dontAsk``).
"""

from pathlib import Path

from wxclaude.core.claude.claude_settings import Approval, SettingsFile, Source

RESTRICTED_ARGUMENTS = ("--setting-sources", "user")
RESTRICTED_PERMISSION_MODE = "manual"
# These modes already keep Claude from acting without the user (it reads, and it plans or is
# refused what would ask), so the user can have the project examined before approving it.
_STRICT_MODES = frozenset({"plan", "dontAsk"})

# The two settings files of the project. The general file is the user's and is read by the CLI.
_PROJECT_FILES = ((Source.SETTINGS, "settings.json"), (Source.LOCAL, "settings.local.json"))
# Only rules that restrict are carried over: the CLI itself applies them before the trust.
_KEPT = (Approval.DENY, Approval.ASK)


def restricted_permission_mode(mode: str) -> str:
    """The permission mode of a restricted message: the agent's own if it is ``plan`` or
    ``dontAsk``, which let Claude read but not act, else ``manual`` (it asks before acting)."""
    return mode if mode in _STRICT_MODES else RESTRICTED_PERMISSION_MODE


def restricted_settings(workspace: Path) -> dict[str, object]:
    """The inline settings of a restricted launch: the ``deny`` and ``ask`` rules of the project.

    A file that does not exist or cannot be read gives no rule. The ``allow`` rules of the project
    are left out. Empty when the project has no rule to carry over.
    """
    rules: dict[Approval, list[str]] = {approval: [] for approval in _KEPT}
    for source, name in _PROJECT_FILES:
        for rule in SettingsFile.load(source, workspace / ".claude" / name).rules():
            if rule.approval in rules and rule.pattern not in rules[rule.approval]:
                rules[rule.approval].append(rule.pattern)
    permissions = {approval.value: patterns for approval, patterns in rules.items() if patterns}
    return {"permissions": permissions} if permissions else {}

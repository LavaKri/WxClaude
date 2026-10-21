"""The permission rules of the settings files of Claude Code.

Three files take part (see ``docs/settings.md``): the general file of the user, which is only read,
``<workspace>/.claude/settings.json`` (shared, versioned) and
``<workspace>/.claude/settings.local.json`` (personal). Each holds ``permissions.allow``,
``permissions.ask`` and ``permissions.deny``: lists of rules written ``Tool`` or
``Tool(specifier)``. The CLI merges the three files and applies deny, then ask, then allow. Other
keys of the files are kept untouched when a file is written.
"""

import enum
import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from wxclaude.core.claude_projects import claude_config_dir
from wxclaude.core.errors import ClaudeSettingsError, JsonStoreError
from wxclaude.core.jsonstore import write_json
from wxclaude.i18n import N_, _


class Approval(enum.Enum):
    """What a rule does. The order is the order of precedence: the first one that applies wins."""

    DENY = "deny"
    ASK = "ask"
    ALLOW = "allow"


class Source(enum.Enum):
    """A settings file. The general one is never written."""

    GENERAL = "general"
    SETTINGS = "settings"
    LOCAL = "local"


_APPROVAL_LABELS = {
    Approval.DENY: N_("Deny"),
    Approval.ASK: N_("Ask"),
    Approval.ALLOW: N_("Allow"),
}
_SOURCE_LABELS = {
    Source.GENERAL: N_("general"),
    Source.SETTINGS: N_("Settings"),
    Source.LOCAL: N_("SettingsLocal"),
}
_APPROVAL_ORDER = {approval: index for index, approval in enumerate(Approval)}


def approval_label(approval: Approval) -> str:
    """The name of an approval for the user (Allow, Ask, Deny)."""
    return _(_APPROVAL_LABELS[approval])


def source_label(source: Source) -> str:
    """The name of a settings file for the user (general, Settings, SettingsLocal)."""
    return _(_SOURCE_LABELS[source])


@dataclass(frozen=True, slots=True)
class Rule:
    """One rule: ``Bash``, ``Bash(git *)``, ``Edit(./src/**)``, with what it does."""

    approval: Approval
    pattern: str

    @property
    def tool(self) -> str:
        """The name of the tool the rule is about (``Bash`` for ``Bash(git *)``)."""
        return self.pattern.split("(", 1)[0].strip()

    @property
    def is_bare(self) -> bool:
        """Does the rule cover the whole tool (``Bash`` and ``Bash(*)``)?"""
        return "(" not in self.pattern or self.pattern.strip().endswith("(*)")

    def text(self) -> str:
        """The rule as a line of a list: ``Deny, Bash(git *)``."""
        return _("{approval}, {rule}").format(
            approval=approval_label(self.approval), rule=self.pattern
        )


def _sorted(rules: list[Rule]) -> list[Rule]:
    return sorted(rules, key=lambda r: (r.tool.casefold(), _APPROVAL_ORDER[r.approval], r.pattern))


@dataclass(slots=True)
class SettingsFile:
    """A settings file as read. ``error`` says why it cannot be modified ('' if it can)."""

    source: Source
    path: Path
    data: dict[str, object] = field(default_factory=dict)
    error: str = ""
    changed: bool = False

    @classmethod
    def load(cls, source: Source, path: Path) -> SettingsFile:
        """Read ``path``; a missing file is an empty one. A damaged file is never overwritten."""
        loaded = cls(source, path)
        if not path.exists():
            return loaded
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            loaded.error = f"Cannot read {path}: {error}"
            return loaded
        if not isinstance(data, dict):
            loaded.error = f"{path} does not hold a JSON object."
            return loaded
        loaded.data = data
        permissions = data.get("permissions")
        if permissions is not None and not isinstance(permissions, dict):
            loaded.error = f"The permissions of {path} are not a JSON object."
        return loaded

    @property
    def writable(self) -> bool:
        """Can the application modify this file?"""
        return self.source is not Source.GENERAL and not self.error

    def _list(self, approval: Approval, *, create: bool) -> list[object] | None:
        permissions = self.data.get("permissions")
        if not isinstance(permissions, dict):
            if not create:
                return None
            permissions = {}
            self.data["permissions"] = permissions
        entries = permissions.get(approval.value)
        if not isinstance(entries, list):
            if not create:
                return None
            entries = []
            permissions[approval.value] = entries
        return entries

    def rules(self) -> list[Rule]:
        """The rules of the file (entries that are not text are ignored)."""
        found: list[Rule] = []
        for approval in Approval:
            for entry in self._list(approval, create=False) or []:
                if isinstance(entry, str) and entry.strip():
                    found.append(Rule(approval, entry.strip()))
        return found

    def add(self, rule: Rule) -> None:
        """Add ``rule`` unless the file already has it."""
        entries = self._list(rule.approval, create=True)
        assert entries is not None
        if rule.pattern not in entries:
            entries.append(rule.pattern)
            self.changed = True

    def remove(self, rule: Rule) -> None:
        """Remove ``rule`` from the file (the list stays, possibly empty)."""
        entries = self._list(rule.approval, create=False)
        if entries is not None and rule.pattern in entries:
            entries.remove(rule.pattern)
            self.changed = True


@dataclass(frozen=True, slots=True)
class ToolState:
    """What the files say about a tool (rules without specifier only), and rules with one."""

    target: Approval | None  # in the target file
    prevailing: Approval | None  # across the three files: deny, then ask, then allow
    origin: Source | None  # the first file that says ``prevailing``
    has_specific_rules: bool

    def text(self, tool: str) -> str:
        """The line of the list of tools: ``Bash Allow, Deny by general, with rules``."""
        parts: list[str] = []
        if self.target is not None:
            parts.append(approval_label(self.target))
        if self.prevailing is not None and self.prevailing is not self.target:
            assert self.origin is not None
            parts.append(
                _("{approval} by {origin}").format(
                    approval=approval_label(self.prevailing), origin=source_label(self.origin)
                )
            )
        if self.has_specific_rules:
            parts.append(_("with rules"))
        return _("{tool} {details}").format(tool=tool, details=", ".join(parts)) if parts else tool


def known_tools() -> list[str]:
    """The tools of the list that ships with the application (``data/tools.txt``)."""
    text = resources.files("wxclaude").joinpath("data", "tools.txt").read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class ToolSettings:
    """The three settings files of a workspace, edited in memory, written by ``save``."""

    def __init__(self, files: dict[Source, SettingsFile]) -> None:
        self.files = files

    @classmethod
    def load(cls, workspace: Path, config_dir: Path | None = None) -> ToolSettings:
        """Read the files of ``workspace`` (``config_dir``: the folder of the general file)."""
        folder = workspace / ".claude"
        paths = {
            Source.GENERAL: (config_dir or claude_config_dir()) / "settings.json",
            Source.SETTINGS: folder / "settings.json",
            Source.LOCAL: folder / "settings.local.json",
        }
        return cls({source: SettingsFile.load(source, path) for source, path in paths.items()})

    def rules(self, source: Source) -> list[Rule]:
        """The rules of a file, sorted by tool, then by approval."""
        return _sorted(self.files[source].rules())

    def tools(self) -> list[str]:
        """The known tools plus those the files name, sorted."""
        names = dict.fromkeys(known_tools())
        for source in Source:
            for rule in self.files[source].rules():
                if rule.tool:
                    names.setdefault(rule.tool, None)
        return sorted(names, key=str.casefold)

    def state(self, tool: str, target: Source) -> ToolState:
        """What the files say about ``tool``, the file ``target`` being the one to edit."""
        bare: dict[Source, set[Approval]] = {source: set() for source in Source}
        specific = False
        for source in Source:
            for rule in self.files[source].rules():
                if rule.tool != tool:
                    continue
                if rule.is_bare:
                    bare[source].add(rule.approval)
                else:
                    specific = True
        in_target = min(bare[target], key=_APPROVAL_ORDER.__getitem__, default=None)
        prevailing: Approval | None = None
        origin: Source | None = None
        for approval in Approval:
            holders = [source for source in Source if approval in bare[source]]
            if holders:
                prevailing, origin = approval, holders[0]
                break
        return ToolState(in_target, prevailing, origin, specific)

    def set_approval(self, source: Source, tool: str, approval: Approval) -> None:
        """Give ``tool`` one rule without specifier in ``source``, replacing those it had there."""
        self._check_writable(source)
        file = self.files[source]
        for rule in file.rules():
            if rule.tool == tool and rule.is_bare:
                file.remove(rule)
        file.add(Rule(approval, tool))

    def add_rule(self, source: Source, rule: Rule) -> None:
        """Add ``rule`` to ``source`` as it is (no check against the other rules)."""
        self._check_writable(source)
        self.files[source].add(rule)

    def remove_rule(self, source: Source, rule: Rule) -> None:
        """Remove ``rule`` from ``source``."""
        self._check_writable(source)
        self.files[source].remove(rule)

    def _check_writable(self, source: Source) -> None:
        file = self.files[source]
        if not file.writable:
            raise ClaudeSettingsError(file.error or f"{file.path} is never modified.")

    def changed_files(self) -> list[SettingsFile]:
        """The files that ``save`` would write."""
        return [file for file in self.files.values() if file.changed]

    def save(self) -> list[Path]:
        """Write the files that changed (atomically, no backup file); return their paths."""
        written: list[Path] = []
        for file in self.changed_files():
            try:
                write_json(file.path, file.data, backup=False)
            except JsonStoreError as error:
                raise ClaudeSettingsError(str(error)) from error
            file.changed = False
            written.append(file.path)
        return written


def allow_always(workspace: Path, pattern: str, config_dir: Path | None = None) -> None:
    """Add an *allow* rule to the personal file of ``workspace`` (what the CLI itself does).

    Raises ``ClaudeSettingsError`` if the file cannot be modified.
    """
    settings = ToolSettings.load(workspace, config_dir)
    settings.add_rule(Source.LOCAL, Rule(Approval.ALLOW, pattern))
    settings.save()

"""The environment variables of Claude Code in the ``env`` key of the settings files.

The variables that are described come from ``data/env_vars.txt`` (one line each, see the top of that
file); those that a file already holds without being described are listed too, with no explanation.
The variables that choose the provider are not offered: WxClaude gives them at launch.
"""

from dataclasses import dataclass
from importlib import resources

from wxclaude.core.claude.claude_settings import SettingsFile
from wxclaude.core.claude.launch import KEY_VARIABLE
from wxclaude.core.config.providers import ALIASES
from wxclaude.core.errors import ClaudeSettingsError
from wxclaude.core.security.sensitive import is_sensitive_name
from wxclaude.i18n import _

FLAG = "flag"
VALUE = "value"
FLAG_ON = "1"
# What the provider decides at each launch: never edited here.
PROVIDER_VARIABLES = frozenset(
    {"ANTHROPIC_BASE_URL", KEY_VARIABLE, "ANTHROPIC_API_KEY"}
    | {f"ANTHROPIC_DEFAULT_{alias.upper()}_MODEL" for alias in ALIASES}
)


@dataclass(frozen=True, slots=True)
class EnvVarInfo:
    """One described variable. ``project_ignored``: a project file does not apply it."""

    name: str
    kind: str  # FLAG or VALUE
    project_ignored: bool
    text: str


@dataclass(frozen=True, slots=True)
class EnvRow:
    """A line of the tab: a variable, what the file holds for it, and what is known of it."""

    name: str
    value: str | None  # None: the file does not set it
    info: EnvVarInfo | None  # None: not described
    sensitive: bool

    @property
    def is_flag(self) -> bool:
        """Is it switched on or off rather than given a value?"""
        return self.info is not None and self.info.kind == FLAG

    @property
    def explanation(self) -> str:
        """What the variable does, or a line saying that it is not described."""
        return self.info.text if self.info else _("This variable is not described.")


def parse_env_vars(text: str) -> list[EnvVarInfo]:
    """The variables of ``text`` (the format of ``env_vars.txt``); a line that is not well formed
    is left out."""
    described: list[EnvVarInfo] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|", 3)]
        if len(parts) != 4 or not parts[0] or parts[1] not in (FLAG, VALUE):
            continue
        name, kind, where, explanation = parts
        if name not in PROVIDER_VARIABLES:
            described.append(EnvVarInfo(name, kind, where == "user", explanation))
    return described


def known_env_vars() -> list[EnvVarInfo]:
    """The variables of the list that ships with the application (``data/env_vars.txt``)."""
    path = resources.files("wxclaude").joinpath("data", "env_vars.txt")
    return parse_env_vars(path.read_text(encoding="utf-8"))


def env_of(file: SettingsFile) -> dict[str, str]:
    """The ``env`` key of a settings file: the variables that have a text value."""
    env = file.data.get("env")
    if not isinstance(env, dict):
        return {}
    return {name: value for name, value in env.items() if isinstance(value, str)}


def env_rows(file: SettingsFile, described: list[EnvVarInfo] | None = None) -> list[EnvRow]:
    """The lines of the tab for ``file``: the described variables, then the others it holds, each
    group sorted by name."""
    infos = {info.name: info for info in (known_env_vars() if described is None else described)}
    held = {name: value for name, value in env_of(file).items() if name not in PROVIDER_VARIABLES}
    names = sorted(infos) + sorted(name for name in held if name not in infos)
    return [
        EnvRow(name, held.get(name), infos.get(name), is_sensitive_name(name)) for name in names
    ]


def _check_writable(file: SettingsFile) -> None:
    if not file.writable:
        raise ClaudeSettingsError(file.error or f"{file.path} is never modified.")


def set_env(file: SettingsFile, name: str, value: str) -> None:
    """Give ``name`` the text ``value`` in ``file`` (written by ``ToolSettings.save``)."""
    _check_writable(file)
    if name in PROVIDER_VARIABLES:
        raise ClaudeSettingsError(
            _("{name} is given by the provider at each launch.").format(name=name)
        )
    env = file.data.get("env")
    if not isinstance(env, dict):
        env = {}
        file.data["env"] = env
    if env.get(name) != value:
        env[name] = value
        file.changed = True


def remove_env(file: SettingsFile, name: str) -> None:
    """Take ``name`` out of ``file``; the rest of the file, ``env`` included, stays."""
    _check_writable(file)
    env = file.data.get("env")
    if isinstance(env, dict) and name in env:
        del env[name]
        file.changed = True

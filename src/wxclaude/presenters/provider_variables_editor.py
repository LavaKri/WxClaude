"""The list *Variable* of the form of a provider: the four models, then the variables of the CLI
the provider can set (``docs/providers.md``).

One line per variable, written ``Small model = deepseek-v4-flash``; the value of the selected line
is edited in a text field next to the list. The editor holds what the form holds until OK: the form
gives the lines to the list, the value and the explanation of the selected one to the field, and
takes ``tiers`` and ``env`` back to make the provider. Nothing here touches wx.
"""

from collections.abc import Callable
from dataclasses import dataclass

from wxclaude.core.claude.env_vars import known_env_vars
from wxclaude.core.config.provider_variables import PROVIDER_VARIABLES
from wxclaude.core.config.providers import MODEL_MAX, TIER_COUNT, Provider
from wxclaude.i18n import _

VARIABLE_VALUE_MAX = 12  # digits of the value of a variable: far more than any real one needs


@dataclass(frozen=True, slots=True)
class _Entry:
    """A line of the list: its label, what it does and how long its value can be. The texts are
    given by functions so that they are translated when shown, not when the module is loaded."""

    label: Callable[[], str]
    explanation: Callable[[], str]
    max_length: int


def _tier_entries() -> list[_Entry]:
    return [
        _Entry(
            lambda: _("Small model"),
            lambda: _(
                "The name of the small model, sent to the server as it is. It answers to the "
                "name haiku. Empty: the weakest model given."
            ),
            MODEL_MAX,
        ),
        _Entry(
            lambda: _("Medium model"),
            lambda: _(
                "The name of the medium model, sent to the server as it is. It answers to the "
                "name sonnet. Empty: the weakest model given."
            ),
            MODEL_MAX,
        ),
        _Entry(
            lambda: _("Large model"),
            lambda: _(
                "The name of the large model, sent to the server as it is. It answers to the "
                "name opus. Empty: the weakest model given."
            ),
            MODEL_MAX,
        ),
        _Entry(
            lambda: _("Largest model"),
            lambda: _(
                "The name of the largest model, sent to the server as it is. It has no alias. "
                "Empty: the weakest model given."
            ),
            MODEL_MAX,
        ),
    ]


def _variable_entry(name: str) -> _Entry:
    """A variable of the closed list: it is called by its name, and explained by the list of the
    variables of Claude Code (``data/env_vars.txt``)."""
    described = {info.name: info.text for info in known_env_vars()}

    def explanation() -> str:
        text = described.get(name, _("This variable is not described."))
        return _("{text} Empty: not set.").format(text=text)

    return _Entry(lambda: name, explanation, VARIABLE_VALUE_MAX)


class ProviderVariablesEditor:
    """The lines of the list *Variable* and their values, for one provider being edited."""

    def __init__(self, provider: Provider) -> None:
        self._entries = [*_tier_entries(), *(_variable_entry(name) for name in PROVIDER_VARIABLES)]
        self._values = [
            *(provider.tiers[i] if i < len(provider.tiers) else "" for i in range(TIER_COUNT)),
            *(provider.env.get(name, "") for name in PROVIDER_VARIABLES),
        ]

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def lines(self) -> list[str]:
        """The items of the list, in order."""
        return [self.line(index) for index in range(len(self))]

    def line(self, index: int) -> str:
        """The item of the list for ``index``: its label, ``=`` and its value ("not set" when
        empty; an empty model takes the weakest one given)."""
        value = self._values[index].strip()
        if not value:
            value = _("(as the weakest model given)") if index < TIER_COUNT else _("(not set)")
        return _("{label} = {value}").format(label=self._entries[index].label(), value=value)

    def label(self, index: int) -> str:
        """The name of the variable at ``index``, for the name of the text field."""
        return self._entries[index].label()

    def value(self, index: int) -> str:
        """The value of the line, as typed."""
        return self._values[index]

    def set_value(self, index: int, text: str) -> None:
        """The user typed ``text`` as the value of the line."""
        self._values[index] = text

    def explanation(self, index: int) -> str:
        """What the variable at ``index`` does."""
        return self._entries[index].explanation()

    def max_length(self, index: int) -> int:
        """The most characters the value of the line can have."""
        return self._entries[index].max_length

    @property
    def tiers(self) -> list[str]:
        """The four model names as typed (``Provider`` fills the empty ones)."""
        return self._values[:TIER_COUNT]

    @property
    def env(self) -> dict[str, str]:
        """The variables as typed (``Provider`` leaves out the empty ones)."""
        return dict(zip(PROVIDER_VARIABLES, self._values[TIER_COUNT:], strict=True))

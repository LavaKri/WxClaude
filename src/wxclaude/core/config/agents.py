"""Agents: the provider, model, effort and permission mode used to talk to Claude."""

from dataclasses import dataclass

DEFAULT_PROVIDER = "claude"  # the id of the built-in provider (``providers.py``)
MODELS = ("haiku", "sonnet", "opus", "fable")  # in ascending order of power
EFFORTS = ("low", "medium", "high", "xhigh", "max")
PERMISSION_MODES = ("manual", "acceptEdits", "plan", "auto", "dontAsk")


def mode_from_cli(name: str) -> str:
    """The mode of ours that the CLI reports as ``name`` in its ``system/init`` line: it calls
    ``manual`` ``default``; the other names are the same."""
    return "manual" if name == "default" else name


@dataclass(slots=True, frozen=True)
class Agent:
    """How a message is sent. A field left to ``None`` is not passed to the CLI (or inherited).

    ``provider`` is the id of a provider. An id that no longer exists is read as the built-in
    provider when the agent is used (``ProviderStore.get``), not here, as only the store knows which
    providers exist.
    """

    model: str | None = None
    effort: str | None = None
    permission_mode: str | None = None
    provider: str | None = None

    def over(self, base: Agent) -> Agent:
        """This agent, with every unset field taken from ``base``."""
        return Agent(
            model=self.model or base.model,
            effort=self.effort or base.effort,
            permission_mode=self.permission_mode or base.permission_mode,
            provider=self.provider or base.provider,
        )

    def to_dict(self) -> dict[str, str]:
        """Only the fields that are set, ready for JSON."""
        data = {
            "provider": self.provider,
            "model": self.model,
            "effort": self.effort,
            "permission_mode": self.permission_mode,
        }
        return {key: value for key, value in data.items() if value}

    @classmethod
    def from_dict(cls, data: object) -> Agent:
        """Build a agent from JSON data; anything invalid is treated as unset."""
        if not isinstance(data, dict):
            return cls()

        def pick(key: str, allowed: tuple[str, ...] | None = None) -> str | None:
            value = data.get(key)
            if not isinstance(value, str) or not value:
                return None
            if allowed is not None and value not in allowed:
                return None
            return value

        return cls(
            model=pick("model"),
            effort=pick("effort", EFFORTS),
            permission_mode=pick("permission_mode", PERMISSION_MODES),
            provider=pick("provider"),
        )


#: The agent of a new conversation until the user chooses another: every field is set, so Claude is
#: never started with a provider, model, effort or permission mode chosen by the CLI settings.
DEFAULT_AGENT = Agent(
    model="sonnet", effort="medium", permission_mode="manual", provider=DEFAULT_PROVIDER
)

"""Agents: the model, effort and permission mode used to talk to Claude."""

from dataclasses import dataclass

MODELS = ("haiku", "sonnet", "opus", "fable")  # in ascending order of power
EFFORTS = ("low", "medium", "high", "xhigh", "max")
PERMISSION_MODES = ("manual", "acceptEdits", "plan", "auto", "dontAsk")


@dataclass(slots=True, frozen=True)
class Agent:
    """How a message is sent. A field left to ``None`` is not passed to the CLI (or inherited)."""

    model: str | None = None
    effort: str | None = None
    permission_mode: str | None = None

    def over(self, base: Agent) -> Agent:
        """This agent, with every unset field taken from ``base``."""
        return Agent(
            model=self.model or base.model,
            effort=self.effort or base.effort,
            permission_mode=self.permission_mode or base.permission_mode,
        )

    def to_dict(self) -> dict[str, str]:
        """Only the fields that are set, ready for JSON."""
        data = {
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
        )


#: The agent of a new conversation until the user chooses another: every field is set, so Claude is
#: never started with a model, an effort or a permission mode chosen by the CLI settings.
DEFAULT_AGENT = Agent(model="sonnet", effort="medium", permission_mode="manual")

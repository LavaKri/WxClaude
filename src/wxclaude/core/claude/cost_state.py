"""The totals the CLI keeps of a session: the ``cost-state`` entries of its file.

Each entry holds what the whole session has cost so far (``docs/claude-cli.md``, "Session files"):
the cost, the time spent by the model and by the tools, and the tokens and the cost of each model.
The time is the time of work: the waits for the answers of the user to a permission question are
not in ``totalAPIDuration`` and ``totalToolDuration`` (they are in ``totalDuration``).
"""

from dataclasses import dataclass, field

from wxclaude.core.conversation.messages import Usage


@dataclass(slots=True)
class ModelTotals:
    """The tokens and the cost of one model."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost: float = 0.0


@dataclass(slots=True)
class CostState:
    """What a session had cost when the entry was written.

    ``after_messages`` is the number of messages the file held before the entry, which places it
    in the history (a branch copies the first messages of another session).
    """

    after_messages: int
    cost: float = 0.0
    activity_ms: int = 0  # the time of the model and of the tools
    models: dict[str, ModelTotals] = field(default_factory=dict)

    def tokens(self) -> Usage:
        """The tokens of all the models."""
        total = Usage()
        for model in self.models.values():
            total.input_tokens += model.input_tokens
            total.output_tokens += model.output_tokens
            total.cache_creation_input_tokens += model.cache_creation_input_tokens
            total.cache_read_input_tokens += model.cache_read_input_tokens
        return total

    def minus(self, earlier: CostState) -> CostState:
        """What came after ``earlier`` (never below zero): the totals without a copied history."""
        models: dict[str, ModelTotals] = {}
        for name, now in self.models.items():
            before = earlier.models.get(name, ModelTotals())
            models[name] = ModelTotals(
                max(0, now.input_tokens - before.input_tokens),
                max(0, now.output_tokens - before.output_tokens),
                max(0, now.cache_creation_input_tokens - before.cache_creation_input_tokens),
                max(0, now.cache_read_input_tokens - before.cache_read_input_tokens),
                max(0.0, now.cost - before.cost),
            )
        return CostState(
            self.after_messages,
            max(0.0, self.cost - earlier.cost),
            max(0, self.activity_ms - earlier.activity_ms),
            models,
        )


def _number(value: object) -> float | None:
    """``value`` as a number; None for anything else (a boolean is not a number here)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _count(value: object) -> int:
    number = _number(value)
    return int(number) if number is not None else 0


def parse_cost_state(entry: dict[str, object], after_messages: int) -> CostState | None:
    """The totals in a ``cost-state`` entry; None if it does not give the cost."""
    cost = _number(entry.get("totalCostUSD"))
    if cost is None:
        return None
    models: dict[str, ModelTotals] = {}
    usage = entry.get("modelUsage")
    if isinstance(usage, dict):
        for name, raw in usage.items():
            if isinstance(raw, dict):
                models[str(name)] = ModelTotals(
                    _count(raw.get("inputTokens")),
                    _count(raw.get("outputTokens")),
                    _count(raw.get("cacheCreationInputTokens")),
                    _count(raw.get("cacheReadInputTokens")),
                    _number(raw.get("costUSD")) or 0.0,
                )
    activity = _count(entry.get("totalAPIDuration")) + _count(entry.get("totalToolDuration"))
    return CostState(after_messages, cost, activity, models)

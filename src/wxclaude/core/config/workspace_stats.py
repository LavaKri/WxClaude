"""The statistics of a workspace: what all its conversations used, the deleted ones included.

The files of Claude Code cannot give that: a conversation that is deleted (or removed by the CLI
after 30 days) takes its totals with it, and a branch holds the totals of the conversation it
copies. So WxClaude keeps a ledger of its own, one file per workspace,
``workspaces/<hash>.stats.json`` next to the state file of the workspace, to which each
finished message is added. The first time a workspace is opened, the conversations that
already exist are counted once (``stats_import.py``).

The time is the time of work of the model and of the tools, without the waits for the answers of
the user to the permission questions. The cost is the list price in dollars, not what the
subscription costs.
"""

from dataclasses import dataclass, field
from pathlib import Path

from wxclaude.core.config.jsonstore import read_json, write_json
from wxclaude.core.config.settings import workspace_key
from wxclaude.core.config.workspace_state import state_file_name
from wxclaude.core.conversation.messages import Usage
from wxclaude.core.numbers import format_tokens
from wxclaude.i18n import _, ngettext

#: The families of models shown by their name; any other model keeps its own name.
_FAMILIES = ("opus", "sonnet", "haiku", "fable")


def stats_file_name(workspace: Path) -> str:
    """The name of the ledger of ``workspace``: the one of its state file, with ``.stats``."""
    return state_file_name(workspace).removesuffix(".json") + ".stats.json"


def model_family(model: str) -> str:
    """How a model is named in the statistics: ``Opus`` for ``claude-opus-5-5``, else as it is."""
    lowered = model.lower()
    for family in _FAMILIES:
        if family in lowered:
            return family.capitalize()
    return model


def format_duration(milliseconds: int) -> str:
    """``2 h 10``, ``35 min`` or ``12 s``: the largest unit that is not zero."""
    seconds = round(milliseconds / 1000)
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours:
        return _("{hours} h {minutes:02d}").format(hours=hours, minutes=minutes)
    if minutes:
        return _("{minutes} min").format(minutes=minutes)
    return _("{seconds} s").format(seconds=seconds)


@dataclass(frozen=True, slots=True)
class CountedMessage:
    """A message that has just ended, as the statistics count it."""

    conversation_id: str
    usage: Usage | None  # its tokens
    activity_ms: int  # the time of work, without the waits for the user
    cost: float | None  # its own cost, None if not known
    model: str
    day: str  # YYYY-MM-DD


@dataclass(slots=True)
class ModelShare:
    """What one model did in the workspace."""

    messages: int = 0
    cost: float = 0.0


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return 0.0
    return float(value)


@dataclass(slots=True)
class WorkspaceStats:
    """The totals of a workspace. Without ``store`` they stay in memory."""

    workspace: Path
    started: str = ""  # the day of the first message counted (YYYY-MM-DD)
    messages: int = 0
    conversations: list[str] = field(default_factory=list)  # every one that had a message
    tokens: Usage = field(default_factory=Usage)
    activity_ms: int = 0
    cost: float = 0.0
    models: dict[str, ModelShare] = field(default_factory=dict)
    includes_past: bool = False  # the conversations that existed at the first use were counted
    store: Path | None = None
    warning: str = ""  # what went wrong while reading the file, for the user
    existed: bool = False  # the file was there when it was loaded

    @classmethod
    def load(cls, workspace: Path, directory: Path | None) -> WorkspaceStats:
        """The statistics of ``workspace`` kept in ``directory`` (None: in memory only)."""
        if directory is None:
            return cls(workspace)
        store = directory / stats_file_name(workspace)
        stats = cls(workspace, store=store)
        result = read_json(store)
        stats.warning = result.warning
        data = result.data
        if data is None:
            return stats
        if str(data.get("workspace", "")).lower() != workspace_key(workspace):
            stats.warning = f"The file {store} belongs to another workspace and was not used."
            return stats
        stats.existed = True
        stats._read(data)
        return stats

    def _read(self, data: dict[str, object]) -> None:
        started = data.get("started")
        self.started = started if isinstance(started, str) else ""
        self.messages = _int(data.get("messages"))
        conversations = data.get("conversations")
        if isinstance(conversations, list):
            self.conversations = [item for item in conversations if isinstance(item, str)]
        tokens = data.get("tokens")
        if isinstance(tokens, dict):
            self.tokens = Usage(
                _int(tokens.get("input")),
                _int(tokens.get("output")),
                _int(tokens.get("cache_creation")),
                _int(tokens.get("cache_read")),
            )
        self.activity_ms = _int(data.get("activity_ms"))
        self.cost = _float(data.get("cost"))
        models = data.get("models")
        if isinstance(models, dict):
            for name, raw in models.items():
                if isinstance(raw, dict):
                    self.models[str(name)] = ModelShare(
                        _int(raw.get("messages")), _float(raw.get("cost"))
                    )
        self.includes_past = data.get("includes_past") is True

    def save(self) -> None:
        """Write the ledger; raises ``JsonStoreError``. Nothing is written without a store."""
        if self.store is None:
            return
        data: dict[str, object] = {
            "workspace": str(self.workspace),
            "started": self.started,
            "messages": self.messages,
            "conversations": self.conversations,
            "tokens": {
                "input": self.tokens.input_tokens,
                "output": self.tokens.output_tokens,
                "cache_creation": self.tokens.cache_creation_input_tokens,
                "cache_read": self.tokens.cache_read_input_tokens,
            },
            "activity_ms": self.activity_ms,
            "cost": self.cost,
            "models": {
                name: {"messages": share.messages, "cost": share.cost}
                for name, share in self.models.items()
            },
            "includes_past": self.includes_past,
        }
        write_json(self.store, data)

    # What is counted ----------------------------------------------------------------------------

    def record_message(self, message: CountedMessage) -> None:
        """Count a message that has just ended."""
        if not self.started:
            self.started = message.day
        self.messages += 1
        self.add_conversation(message.conversation_id)
        if message.usage is not None:
            self.add_tokens(message.usage)
        self.activity_ms += max(0, message.activity_ms)
        self.cost += message.cost or 0.0
        self.add_model(message.model, 1, message.cost or 0.0)

    def add_conversation(self, conversation_id: str) -> None:
        """Count a conversation (once, whatever its number of messages)."""
        if conversation_id not in self.conversations:
            self.conversations.append(conversation_id)

    def add_tokens(self, usage: Usage) -> None:
        self.tokens.input_tokens += usage.input_tokens
        self.tokens.output_tokens += usage.output_tokens
        self.tokens.cache_creation_input_tokens += usage.cache_creation_input_tokens
        self.tokens.cache_read_input_tokens += usage.cache_read_input_tokens

    def add_model(self, model: str, messages: int, cost: float) -> None:
        """Count messages and a cost for a model (nothing for a model that is not known)."""
        if not model or not (messages or cost):
            return
        share = self.models.setdefault(model, ModelShare())
        share.messages += messages
        share.cost += cost

    # What is shown ------------------------------------------------------------------------------

    def lines(self) -> list[str]:
        """The statistics, one fact per line; what is unknown or zero is left out."""
        heading = _("Global statistics of the workspace")
        if not self.messages:
            return [heading, _("No message counted yet.")]
        lines = [heading]
        if self.started:
            lines.append(_("Started on {date}").format(date=self.started))
        count = len(self.conversations)
        lines.append(
            _("{messages}, in {conversations}").format(
                messages=ngettext("{count} message", "{count} messages", self.messages).format(
                    count=self.messages
                ),
                conversations=ngettext(
                    "{count} conversation", "{count} conversations", count
                ).format(count=count),
            )
        )
        tokens = self.tokens
        exchanged = tokens.input_tokens + tokens.output_tokens + tokens.cache_creation_input_tokens
        lines.append(
            _("Tokens exchanged: {exchanged}, read from the cache: {cached}").format(
                exchanged=format_tokens(exchanged),
                cached=format_tokens(tokens.cache_read_input_tokens),
            )
        )
        lines.append(
            _("{duration} of activity (model time + tool time)").format(
                duration=format_duration(self.activity_ms)
            )
        )
        if self.cost > 0:
            cost = f"{self.cost:.2f}" if self.cost >= 1 else f"{self.cost:.4f}"
            lines.append(_("Cost: {cost} dollars at list price").format(cost=cost))
        costs = {name: share.cost for name, share in self.models.items()}
        if any(costs.values()):
            lines.append(_("Cost split: {shares}").format(shares=_shares(costs)))
        counts = {name: float(share.messages) for name, share in self.models.items()}
        if any(counts.values()):
            lines.append(_("Messages split: {shares}").format(shares=_shares(counts)))
        if self.includes_past:
            lines.append(
                _(
                    "The conversations that existed at the first use are counted; those deleted "
                    "before are not."
                )
            )
        return lines


def _shares(values: dict[str, float]) -> str:
    """``70 % Sonnet, 30 % Opus``: the share of each family of models, the largest first."""
    by_family: dict[str, float] = {}
    for name, value in values.items():
        family = model_family(name)
        by_family[family] = by_family.get(family, 0.0) + value
    total = sum(by_family.values())
    ordered = sorted(by_family.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(_share(family, value / total) for family, value in ordered if value > 0)


def _share(family: str, fraction: float) -> str:
    """``70 % Sonnet``; ``less than 1 % Haiku`` for a share that would round to nothing."""
    percent = round(fraction * 100)
    if percent == 0:
        return _("less than 1 % {model}").format(model=family)
    return _("{percent} % {model}").format(percent=percent, model=family)

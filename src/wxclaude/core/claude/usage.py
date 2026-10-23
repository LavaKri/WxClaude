"""What is known about the usage of Claude: the gauges of the subscription and the tokens spent.

The data arrives with the answers (``rate_limit_event`` and ``result`` lines of the stream), so
there is nothing to show before the first message. See ``docs/conversation-display.md``.
"""

from dataclasses import dataclass, field
from datetime import datetime

from wxclaude.core.claude.events import RateLimit, RateWindow, TurnResult
from wxclaude.core.conversation.messages import Usage
from wxclaude.i18n import N_, _

_WINDOW_NAMES = {
    "five_hour": N_("5-hour window"),
    "seven_day": N_("weekly window"),
    "seven_day_opus": N_("weekly window of Opus"),
    "seven_day_sonnet": N_("weekly window of Sonnet"),
}


#: A gauge is announced when it reaches or passes one of these fractions (0.9 is 90 %). They are
#: the early-warning thresholds of Claude Code itself (see ``docs/claude-cli.md``).
ALERT_THRESHOLDS: dict[str, tuple[float, ...]] = {
    "five_hour": (0.9,),
    "seven_day": (0.25, 0.5, 0.75),
}


class GaugeAlerts:
    """Tells when a gauge reaches or passes one of its alert thresholds for the first time.

    Each threshold is announced once, and not again until the gauge has gone back under it, so a
    window that starts again at 0 % (every 5 hours, every week) is announced again, even if the
    application stayed open. When several thresholds are passed at once (a gauge seen at 63 % for
    the first time), the window is reported once. ``update`` takes the windows of each
    ``rate_limit_event``.
    """

    def __init__(self, thresholds: dict[str, tuple[float, ...]] | None = None) -> None:
        self._thresholds = ALERT_THRESHOLDS if thresholds is None else thresholds
        self._announced: set[tuple[str, float]] = set()

    def update(self, windows: tuple[RateWindow, ...]) -> list[RateWindow]:
        """The windows that just reached or passed a threshold (the others are not mentioned)."""
        crossed: list[RateWindow] = []
        for window in windows:
            levels = self._thresholds.get(window.name, ())
            if not levels or window.utilization is None:
                continue
            new = []
            for level in levels:
                key = (window.name, level)
                if window.utilization < level:
                    self._announced.discard(key)  # under it again: the next crossing counts
                elif key not in self._announced:
                    self._announced.add(key)
                    new.append(level)
            if new:
                crossed.append(window)
        return crossed


@dataclass(slots=True)
class UsageTracker:
    """The gauges (account wide) and the spending of the current conversation."""

    status: str = ""
    windows: dict[str, RateWindow] = field(default_factory=dict)
    gauges_at: datetime | None = None
    last_turn: TurnResult | None = None
    conversation_usage: Usage = field(default_factory=Usage)
    conversation_cost: float = 0.0
    conversation_turns: int = 0  # messages sent since the conversation was opened here

    def record_rate_limit(self, event: RateLimit, now: datetime) -> None:
        """Keep the gauges of ``event`` (a window not named in it keeps its last value)."""
        self.status = event.status
        self.record_windows(event.windows, now)

    def record_windows(self, windows: tuple[RateWindow, ...], now: datetime) -> None:
        """Keep these gauges (a window not named keeps its last value); the status is left alone."""
        for window in windows:
            self.windows[window.name] = window
        self.gauges_at = now

    def ready_line(self) -> str:
        """ "Ready", with the 5-hour gauge when it is known (``Ready, gauge at 50 %``) and the
        weekly gauge once it reached its last alert threshold (``..., week at 76 %``)."""
        five_hours = _percent(self.windows.get("five_hour"))
        week_window = self.windows.get("seven_day")
        week = _percent(week_window)
        last_threshold = ALERT_THRESHOLDS["seven_day"][-1]
        if week_window is None or (week_window.utilization or 0) < last_threshold:
            week = None  # not worth a look yet: the usage dialog has it
        if five_hours is None and week is None:
            return _("Ready")
        if week is None:
            return _("Ready, gauge at {percent} %").format(percent=five_hours)
        if five_hours is None:
            return _("Ready, week at {week} %").format(week=week)
        return _("Ready, gauge at {percent} %, week at {week} %").format(
            percent=five_hours, week=week
        )

    def record_result(self, result: TurnResult) -> None:
        """Add the tokens and the cost of a finished message to the conversation."""
        self.last_turn = result
        self.conversation_turns += 1
        self.conversation_cost += result.cost_usd or 0.0
        if result.usage is not None:
            total = self.conversation_usage
            total.input_tokens += result.usage.input_tokens
            total.output_tokens += result.usage.output_tokens
            total.cache_creation_input_tokens += result.usage.cache_creation_input_tokens
            total.cache_read_input_tokens += result.usage.cache_read_input_tokens

    def start_conversation(self) -> None:
        """Another conversation is current: its spending starts again (the gauges stay)."""
        self.last_turn = None
        self.conversation_usage = Usage()
        self.conversation_cost = 0.0
        self.conversation_turns = 0

    def lines(self, now: datetime) -> list[str]:
        """The report, one fact per line; what is unknown is not written."""
        return [*self._gauge_lines(now), *self._turn_lines(), *self._conversation_lines()]

    def _gauge_lines(self, now: datetime) -> list[str]:
        if not self.windows:
            return [_("No subscription usage information yet: it arrives with the next answer.")]
        lines = [_window_line(window, now) for window in self.windows.values()]
        if self.status and self.status != "allowed":
            lines.append(_("Limit status: {status}.").format(status=self.status))
        if self.gauges_at is not None:
            when = _when(self.gauges_at, now)
            lines.append(_("Gauges updated at {when}.").format(when=when))
        return lines

    def _turn_lines(self) -> list[str]:
        turn = self.last_turn
        if turn is None:
            return [_("No message sent yet in this conversation since it was opened here.")]
        lines: list[str] = []
        if turn.usage is not None:
            lines.append(_("Last message, tokens: {tokens}.").format(tokens=_tokens(turn.usage)))
        details = _details(turn.cost_usd, turn.duration_ms, turn.num_turns)
        if details:
            lines.append(_("Last message: {details}.").format(details=details))
        return lines

    def _conversation_lines(self) -> list[str]:
        if not self.conversation_turns:
            return []
        return [
            _("Conversation since it was opened here, tokens: {tokens}.").format(
                tokens=_tokens(self.conversation_usage)
            ),
            _("Conversation since it was opened here: {details}.").format(
                details=_details(self.conversation_cost, None, None, self.conversation_turns)
            ),
        ]


def _percent(window: RateWindow | None) -> int | None:
    """How full a gauge is, in whole percent (None when it is not known)."""
    if window is None or window.utilization is None:
        return None
    return round(window.utilization * 100)


def _when(moment: datetime, now: datetime) -> str:
    """A time of the day for today, else the date and the time."""
    if moment.date() == now.date():
        return moment.strftime("%H:%M")
    return moment.strftime("%Y-%m-%d %H:%M")


def _window_line(window: RateWindow, now: datetime) -> str:
    name = _(_WINDOW_NAMES[window.name]) if window.name in _WINDOW_NAMES else window.name
    parts = [name]
    if window.utilization is not None:
        parts.append(_("{percent} % used").format(percent=round(window.utilization * 100)))
    if window.resets_at is not None:
        reset = _when(datetime.fromtimestamp(window.resets_at), now)
        parts.append(_("resets at {when}").format(when=reset))
    return ", ".join(parts) + "."


def _tokens(usage: Usage) -> str:
    return _(
        "{input} in, {output} out, {read} read from the cache, {written} written to the cache"
    ).format(
        input=usage.input_tokens,
        output=usage.output_tokens,
        read=usage.cache_read_input_tokens,
        written=usage.cache_creation_input_tokens,
    )


def _details(
    cost: float | None, duration_ms: int | None, turns: int | None, messages: int | None = None
) -> str:
    """Cost, duration and counts separated by commas; the ones that are unknown are left out."""
    parts: list[str] = []
    if cost is not None:
        parts.append(_("cost {cost} dollars at list price").format(cost=f"{cost:.4f}"))
    if duration_ms is not None:
        parts.append(_("duration {seconds} seconds").format(seconds=f"{duration_ms / 1000:.1f}"))
    if turns is not None:
        parts.append(_("turns: {count}").format(count=turns))
    if messages is not None:
        parts.append(_("messages: {count}").format(count=messages))
    return ", ".join(parts)

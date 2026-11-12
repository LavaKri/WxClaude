"""The usage gauge and the statistics (``docs/interface.md``, Tools and Help).

The gauge dialog shows the gauges of the Claude subscription and, for each provider that has a key
saved and a method to ask its credit (chosen in its form), the credit it has left. The credits
are asked to the servers away from the window thread, once, when the dialog is opened. The
statistics dialog shows the spending of the last message and of the conversation, then the
statistics of the whole workspace.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.provider_methods import credit_method, unavailable_line
from wxclaude.core.config.providers import Provider, ProviderStore
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.errors import KeyVaultError, ProviderError


class UsageView(Protocol):
    """What the presenter asks of the interface."""

    def show_gauges(self, lines: list[str]) -> None:
        """The gauge dialog: one fact per line."""
        ...

    def show_statistics(self, lines: list[str]) -> None:
        """The statistics dialog: one fact per line."""
        ...

    def fetch_balances(
        self, task: Callable[[], list[str]], on_done: Callable[[list[str]], None]
    ) -> None:
        """Run ``task`` away from the window thread, then call ``on_done`` with its lines in the
        window thread. ``task`` never raises."""
        ...


@dataclass(frozen=True, slots=True)
class _Request:
    """A balance to ask: the provider and its key, or why the key cannot be given."""

    provider: Provider
    key: str = field(default="", repr=False)
    problem: str = ""


class UsagePresenter:
    """Opens the gauge dialog and the statistics dialog."""

    def __init__(
        self,
        view: UsageView,
        usage: UsageTracker,
        stats: Callable[[], WorkspaceStats | None],
        providers: ProviderStore | None = None,
    ) -> None:
        self._view = view
        self._usage = usage
        self._stats = stats  # the statistics of the current workspace
        self._providers = providers

    def show_gauges(self) -> None:
        """The gauges of the subscription, then the credit of the providers that tell it. The
        dialog opens when the credits are known (at once if no provider has any to tell)."""
        gauges = self._usage.gauge_lines(datetime.now())
        requests = self._requests()
        if not requests:
            self._view.show_gauges(gauges)
            return
        self._view.fetch_balances(
            lambda: _balances(requests),
            lambda credits: self._view.show_gauges([*gauges, "", *credits]),
        )

    def show_statistics(self) -> None:
        """The spending of the last message and of the conversation, then the workspace."""
        lines = self._usage.statistics_lines()
        stats = self._stats()
        if stats is not None:
            lines += stats.lines()
        self._view.show_statistics(lines)

    # -- inside ---------------------------------------------------------------------------

    def _requests(self) -> list[_Request]:
        """The providers with a key saved and a method to ask their credit. Keys are decrypted
        here, in the window thread, for this request only."""
        store = self._providers
        if store is None:
            return []
        requests: list[_Request] = []
        for provider in store.providers():
            if provider.is_builtin or not provider.needs_key or not store.has_key(provider.id):
                continue
            if not credit_method(provider.credit_method).available:
                continue
            try:
                requests.append(_Request(provider, store.key(provider.id)))
            except (ProviderError, KeyVaultError) as error:
                requests.append(_Request(provider, problem=str(error)))
        return requests


def _balances(requests: list[_Request]) -> list[str]:
    """The lines of the credits (run away from the window thread), a blank line between two
    providers; a failure is a line too."""
    lines: list[str] = []
    for request in requests:
        if lines:
            lines.append("")
        provider = request.provider
        if request.problem:
            lines.append(unavailable_line(provider.name, request.problem))
            continue
        method = credit_method(provider.credit_method)
        lines.extend(method.lines(provider.name, provider.base_url, request.key))
    return lines

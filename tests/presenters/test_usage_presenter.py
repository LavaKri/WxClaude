"""The usage gauge and the statistics, with a fake view: no wx, no window."""

from collections.abc import Callable
from pathlib import Path

import pytest
from fake_vault import FakeVault

from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.provider_methods import DeepSeekCredit
from wxclaude.core.config.providers import KEY_NONE, Provider, ProviderStore
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.errors import BalanceError, KeyVaultError
from wxclaude.presenters.usage_presenter import UsagePresenter

pytestmark = pytest.mark.unit


class FakeView:
    """Records the dialogs; runs the task of the credits at once, as the window would later."""

    def __init__(self) -> None:
        self.gauges: list[list[str]] = []
        self.statistics: list[list[str]] = []
        self.fetches = 0

    def show_gauges(self, lines: list[str]) -> None:
        self.gauges.append(lines)

    def show_statistics(self, lines: list[str]) -> None:
        self.statistics.append(lines)

    def fetch_balances(
        self, task: Callable[[], list[str]], on_done: Callable[[list[str]], None]
    ) -> None:
        self.fetches += 1
        on_done(task())


def deepseek(name: str = "DeepSeek", credit_method: str = "deepseek") -> Provider:
    return Provider(
        id="",
        name=name,
        base_url="https://api.deepseek.com/anthropic",
        tiers=["m"],
        credit_method=credit_method,
    )


def store_with(*providers: Provider, key: str | None = "sk-1") -> ProviderStore:
    store = ProviderStore(FakeVault())
    for index, provider in enumerate(providers):
        provider.id = f"p{index}"
        store.add(provider)
        if key is not None:
            store.set_key(provider.id, key)
    return store


def presenter(
    view: FakeView, store: ProviderStore | None = None, stats: WorkspaceStats | None = None
) -> UsagePresenter:
    return UsagePresenter(view, UsageTracker(), lambda: stats, store)


def test_the_gauge_opens_at_once_when_no_provider_has_a_credit_to_tell() -> None:
    view = FakeView()
    local = Provider(
        id="local", name="LM", base_url="http://127.0.0.1:1234", key_source=KEY_NONE, tiers=["q"]
    )
    for store in (None, ProviderStore(FakeVault()), store_with(local, key=None)):
        presenter(view, store).show_gauges()
    assert view.fetches == 0
    assert len(view.gauges) == 3
    assert view.gauges[0][0].startswith("No subscription usage information yet")
    assert all(lines == view.gauges[0] for lines in view.gauges)


def test_a_provider_without_a_saved_key_is_not_asked() -> None:
    view = FakeView()
    presenter(view, store_with(deepseek(), key=None)).show_gauges()
    assert view.fetches == 0


def test_a_provider_without_a_method_for_the_credit_is_not_in_the_gauge() -> None:
    view = FakeView()
    store = store_with(deepseek(credit_method="none"), deepseek("Other", credit_method="gone"))
    presenter(view, store).show_gauges()
    assert view.fetches == 0
    assert len(view.gauges[0]) == 1  # the gauge of Claude only


def test_the_credit_of_a_provider_with_a_key_follows_the_gauges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake(
        self: DeepSeekCredit, name: str, base_url: str, key: str, **options: object
    ) -> list[str]:
        calls.append((name, base_url, key))
        return [f"{name}: balance 4.99 USD."]

    monkeypatch.setattr(DeepSeekCredit, "credit", fake)
    view = FakeView()
    presenter(view, store_with(deepseek("One"), deepseek("Two"))).show_gauges()
    url = "https://api.deepseek.com/anthropic"
    assert calls == [("One", url, "sk-1"), ("Two", url, "sk-1")]
    (lines,) = view.gauges
    assert lines[0].startswith("No subscription usage information yet")
    # A blank line apart: Claude and each provider are separated.
    assert lines[1:] == ["", "One: balance 4.99 USD.", "", "Two: balance 4.99 USD."]


def test_a_credit_that_cannot_be_asked_is_a_line_not_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake(
        self: DeepSeekCredit, name: str, base_url: str, key: str, **options: object
    ) -> list[str]:
        raise BalanceError("The server refused the key (error 401).")

    monkeypatch.setattr(DeepSeekCredit, "credit", fake)
    view = FakeView()
    presenter(view, store_with(deepseek())).show_gauges()
    assert view.gauges[0][1:] == [
        "",
        "DeepSeek: balance not available. The server refused the key (error 401).",
    ]


def test_a_key_that_cannot_be_read_is_a_line_too(monkeypatch: pytest.MonkeyPatch) -> None:
    store = store_with(deepseek())
    monkeypatch.setattr(store, "key", lambda identifier: (_ for _ in ()).throw(_unreadable()))
    view = FakeView()
    presenter(view, store).show_gauges()
    assert view.gauges[0][1:] == ["", "DeepSeek: balance not available. Enter it again."]


def _unreadable() -> Exception:
    return KeyVaultError("Enter it again.")


def test_the_statistics_are_the_spending_then_the_workspace(tmp_path: Path) -> None:
    view = FakeView()
    presenter(view, stats=WorkspaceStats(tmp_path)).show_statistics()
    (lines,) = view.statistics
    assert lines[0].startswith("No message sent yet")
    assert lines[-2:] == ["Global statistics of the workspace", "No message counted yet."]
    assert view.gauges == []


def test_the_statistics_without_a_workspace_are_the_spending_only() -> None:
    view = FakeView()
    presenter(view).show_statistics()
    assert view.statistics == [
        ["No message sent yet in this conversation since it was opened here."]
    ]

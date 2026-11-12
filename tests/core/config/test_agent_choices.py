"""The models an agent can take depending on its provider."""

import pytest
from fake_vault import FakeVault

from wxclaude.core.config.agent_choices import models_for, with_provider
from wxclaude.core.config.agents import MODELS, Agent
from wxclaude.core.config.providers import CLAUDE, Provider, ProviderStore

pytestmark = pytest.mark.unit


def store() -> ProviderStore:
    providers = ProviderStore(FakeVault())
    providers.add(
        Provider(
            id="deepseek",
            name="DeepSeek",
            base_url="https://api.deepseek.com/anthropic",
            tiers=["deepseek-chat", "haiku"],
        )
    )
    return providers


def test_claude_offers_its_models_and_a_provider_its_own() -> None:
    assert models_for(CLAUDE) == list(MODELS)
    assert models_for(store().get("deepseek")) == ["deepseek-chat", "haiku"]


def test_changing_the_provider_takes_the_first_model_of_the_new_one() -> None:
    agent = Agent(model="opus", effort="high", permission_mode="plan", provider="claude")
    moved = with_provider(agent, "deepseek", store())
    assert moved == Agent(
        model="deepseek-chat", effort="high", permission_mode="plan", provider="deepseek"
    )


def test_the_model_stays_when_the_new_provider_offers_it() -> None:
    moved = with_provider(Agent(model="haiku", provider="claude"), "deepseek", store())
    assert (moved.model, moved.provider) == ("haiku", "deepseek")


def test_going_back_to_claude() -> None:
    moved = with_provider(Agent(model="deepseek-chat", provider="deepseek"), "claude", store())
    assert (moved.model, moved.provider) == (MODELS[0], "claude")


def test_an_unknown_provider_is_claude() -> None:
    moved = with_provider(Agent(model="deepseek-chat", provider="deepseek"), "gone", store())
    assert moved.provider == "claude"
    assert moved.model == MODELS[0]


def test_an_agent_without_a_model_stays_without_one() -> None:
    assert with_provider(Agent(), "deepseek", store()).model is None

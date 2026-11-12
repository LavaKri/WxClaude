import pytest

from wxclaude.core.config.agents import (
    DEFAULT_AGENT,
    DEFAULT_PROVIDER,
    Agent,
    mode_from_cli,
)

pytestmark = pytest.mark.unit


def test_the_cli_calls_manual_default() -> None:
    assert mode_from_cli("default") == "manual"
    assert mode_from_cli("manual") == "manual"
    assert mode_from_cli("acceptEdits") == "acceptEdits"


def test_over_takes_unset_fields_from_base() -> None:
    alternative = Agent(effort="low")
    base = Agent(model="opus", effort="high", permission_mode="plan")
    assert alternative.over(base) == Agent(model="opus", effort="low", permission_mode="plan")


def test_to_dict_keeps_only_set_fields() -> None:
    assert Agent(model="haiku").to_dict() == {"model": "haiku"}


def test_from_dict_round_trip() -> None:
    agent = Agent(model="sonnet", effort="medium", permission_mode="acceptEdits")
    assert Agent.from_dict(agent.to_dict()) == agent


def test_from_dict_ignores_invalid_values() -> None:
    assert Agent.from_dict({"effort": "huge", "permission_mode": 3}) == Agent()
    assert Agent.from_dict("nonsense") == Agent()


def test_the_provider_is_part_of_the_agent() -> None:
    agent = Agent(model="deepseek-chat", provider="deepseek")
    assert agent.to_dict() == {"provider": "deepseek", "model": "deepseek-chat"}
    assert Agent.from_dict(agent.to_dict()) == agent


def test_over_takes_an_unset_provider_from_base() -> None:
    base = Agent(model="opus", provider="deepseek")
    assert Agent(effort="low").over(base).provider == "deepseek"
    assert Agent(provider="claude").over(base).provider == "claude"


def test_an_agent_of_an_older_file_has_no_provider_and_a_default_one_is_claude() -> None:
    assert Agent.from_dict({"model": "haiku"}).provider is None
    assert Agent.from_dict({"model": "haiku"}).over(DEFAULT_AGENT).provider == "claude"
    assert DEFAULT_AGENT.provider == DEFAULT_PROVIDER


def test_a_provider_that_is_not_text_is_ignored() -> None:
    assert Agent.from_dict({"provider": 3}).provider is None
    assert Agent.from_dict({"provider": ""}).provider is None


def test_an_unknown_provider_id_is_kept_by_the_agent() -> None:
    # Only the store knows which providers exist: it reads an unknown id as Claude (test_providers).
    assert Agent.from_dict({"provider": "gone"}).provider == "gone"

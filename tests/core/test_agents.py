import pytest

from wxclaude.core.agents import Agent

pytestmark = pytest.mark.unit


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

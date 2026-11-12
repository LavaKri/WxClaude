"""What an agent can be set to, depending on its provider (``docs/providers.md``, "Where a provider
is chosen"): the models offered are those of the provider, and changing the provider takes the first
model of the new one unless the current model is also one of its models."""

from dataclasses import replace

from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import Provider, ProviderStore


def models_for(provider: Provider) -> list[str]:
    """The model names offered for ``provider`` (the built-in Claude offers its own)."""
    return list(provider.models)


def with_provider(agent: Agent, provider_id: str, providers: ProviderStore) -> Agent:
    """``agent`` moved to the provider ``provider_id`` (Claude if it does not exist).

    The model stays if the new provider offers it, else it becomes the first model of the new
    provider; an agent without a model stays without one. The other fields are not changed.
    """
    provider = providers.get(provider_id)
    models = models_for(provider)
    model = agent.model
    if model is not None and model not in models and models:
        model = models[0]
    return replace(agent, provider=provider.id, model=model)

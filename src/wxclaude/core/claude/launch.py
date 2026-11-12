"""What launching the CLI with a provider other than Claude adds (``docs/providers.md``).

For Claude nothing is added: the CLI is started as it always was. For another provider the key goes
to the environment of the process (never to the command line), the address and the model aliases
go to the inline ``--settings`` (the only place that beats the project files), what is sent to
Anthropic is turned off, and the credentials of the environment can be hidden from the tools of
Claude. With the relay (``core/security/key_relay.py``) the CLI gets the address of the relay and a
token instead of the address of the provider and the key.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from wxclaude.core.config.key_transmission import MASKED, RELAYED
from wxclaude.core.config.provider_variables import PROVIDER_VARIABLES, is_valid_value
from wxclaude.core.config.providers import ALIASES, KEY_NONE, Provider, ProviderStore
from wxclaude.core.security.key_relay import KeyRelay, RelayAccess

KEY_VARIABLE = "ANTHROPIC_AUTH_TOKEN"
SCRUB_VARIABLE = "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"
NO_KEY = "no-key"  # given to the CLI by a provider that needs none (a local server)
# What the CLI sends to Anthropic when the user chose another provider.
TELEMETRY_OFF = {
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}
# The variables of the process that choose a provider or a way to reach one: two providers must
# never mix, so none of them is passed on.
_INHERITED_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_USE_")


@dataclass(frozen=True, slots=True)
class ProviderLaunch:
    """A provider to launch the CLI with, and the key to give it. The key is not in the ``repr``.

    With ``relay`` the CLI is given the address and the token of the relay, not the key.
    """

    provider: Provider
    key: str = field(default="", repr=False)
    scrub: bool = True  # hide the credentials of the environment from the tools of Claude
    relay: RelayAccess | None = None

    @property
    def active(self) -> bool:
        """Does this launch change anything? (Not for Claude.)"""
        return not self.provider.is_builtin


def provider_settings(launch: ProviderLaunch | None) -> dict[str, object]:
    """The inline settings of a provider: its address, the models its aliases stand for and the
    variables it sets (only the known ones, ``provider_variables``). Being inline they apply in a
    restricted folder too, where the files of the project are not read."""
    if launch is None or not launch.active:
        return {}
    provider = launch.provider
    relay = launch.relay
    env = {"ANTHROPIC_BASE_URL": relay.base_url if relay else provider.base_url}
    for alias in ALIASES:
        if alias in provider.aliases:
            env[f"ANTHROPIC_DEFAULT_{alias.upper()}_MODEL"] = provider.aliases[alias]
    for name in PROVIDER_VARIABLES:
        if is_valid_value(provider.env.get(name, "")):  # a file edited by hand may hold anything
            env[name] = provider.env[name]
    return {"env": env}


def provider_environment(
    launch: ProviderLaunch | None, inherited: Mapping[str, str] | None = None
) -> dict[str, str] | None:
    """The environment of the process for ``launch``; None when the process inherits its own
    (Claude), which is what it always did.

    ``inherited`` is the environment of WxClaude (``os.environ`` when it is not given).
    """
    if launch is None or not launch.active:
        return None
    source = os.environ if inherited is None else inherited
    environment = {
        name: value
        for name, value in source.items()
        if not name.upper().startswith(_INHERITED_PREFIXES)
    }
    if launch.provider.key_source == KEY_NONE:
        key = NO_KEY
    else:
        key = launch.relay.token if launch.relay else launch.key
    environment[KEY_VARIABLE] = key
    environment.update(TELEMETRY_OFF)
    if launch.scrub:
        environment[SCRUB_VARIABLE] = "1"
    return environment


def sends_effort(launch: ProviderLaunch | None) -> bool:
    """Is ``--effort`` passed? Always for Claude; for a provider, only if it accepts it."""
    return launch is None or not launch.active or launch.provider.send_effort


def launch_for(
    provider_id: str | None,
    providers: ProviderStore | None,
    *,
    transmission: str = MASKED,
    relay: KeyRelay | None = None,
) -> ProviderLaunch | None:
    """What to launch the CLI with for the agent whose provider is ``provider_id``.

    None for Claude (and without a store): nothing is added. Otherwise the provider with its key,
    decrypted for this launch only, and how it reaches the CLI (``transmission``, see
    ``key_transmission``): *Masked* hides it from the tools of Claude, *Shared* does not, *Relayed*
    gives the CLI the token of ``relay`` instead (the key is then not given to the CLI at all; a
    provider that needs no key has no secret to hide; without a relay *Masked* is used). Raises
    ``ProviderError`` if the provider needs a key and none is saved, ``KeyVaultError`` if the key
    cannot be decrypted here.
    """
    if providers is None:
        return None
    provider = providers.get(provider_id)
    if provider.is_builtin:
        return None
    key = providers.key(provider.id) if provider.needs_key else ""
    if transmission == RELAYED and relay is not None and provider.needs_key:
        return ProviderLaunch(provider, "", False, relay.access(provider, key))
    # Without a relay the safe way is taken. A provider that needs no key has no secret to hide.
    scrub = transmission in (MASKED, RELAYED) and provider.needs_key
    return ProviderLaunch(provider, key, scrub)
